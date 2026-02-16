# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AFL Maven Artifact Runner.

Runs external JVM programs packaged as Maven artifacts. The runner claims
event tasks, resolves and downloads Maven artifacts, launches the JVM
subprocess, and handles step continuation and workflow resumption.

The JVM program receives a step ID, reads step data from MongoDB, does
its work, writes returns back to MongoDB, and exits.

Example usage::

    from afl.runtime import MemoryStore, Evaluator, Telemetry
    from afl.runtime.maven_runner import MavenArtifactRunner, MavenRunnerConfig

    store = MemoryStore()
    evaluator = Evaluator(persistence=store)

    runner = MavenArtifactRunner(
        persistence=store,
        evaluator=evaluator,
        config=MavenRunnerConfig(service_name="my-maven-runner"),
    )

    # Register a handler backed by a Maven artifact
    runner.register_handler(
        facet_name="ns.ProcessData",
        module_uri="mvn:com.example:data-processor:1.0.0",
    )

    runner.start()  # blocks until stopped
"""

import fnmatch
import logging
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .entities import (
    HandlerRegistration,
    ServerDefinition,
    ServerState,
    TaskState,
)
from .evaluator import Evaluator
from .persistence import PersistenceAPI
from .types import generate_id

logger = logging.getLogger(__name__)


def _current_time_ms() -> int:
    """Get current time in milliseconds."""
    return int(time.time() * 1000)


@dataclass
class MavenRunnerConfig:
    """Configuration for the MavenArtifactRunner."""

    service_name: str = "afl-maven-runner"
    server_group: str = "default"
    server_name: str = ""
    task_list: str = "default"
    poll_interval_ms: int = 2000
    max_concurrent: int = 5
    heartbeat_interval_ms: int = 10000
    registry_refresh_interval_ms: int = 30000
    topics: list[str] = field(default_factory=list)
    # Maven-specific
    cache_dir: str = ""
    repository_url: str = "https://repo1.maven.org/maven2"
    java_command: str = "java"
    default_timeout_ms: int = 300000  # 5 min default subprocess timeout

    def __post_init__(self) -> None:
        if not self.server_name:
            self.server_name = socket.gethostname()
        if not self.cache_dir:
            self.cache_dir = str(Path.home() / ".afl" / "maven-cache")


class MavenArtifactRunner:
    """Runner that executes JVM programs packaged as Maven artifacts.

    Claims event tasks, resolves Maven artifacts (downloading and caching
    them locally), launches JVM subprocesses, and handles step continuation
    and workflow resumption after the program completes.
    """

    def __init__(
        self,
        persistence: PersistenceAPI,
        evaluator: Evaluator,
        config: MavenRunnerConfig | None = None,
    ) -> None:
        self._persistence = persistence
        self._evaluator = evaluator
        self._config = config or MavenRunnerConfig()

        self._server_id = generate_id()
        self._running = False
        self._stopping = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._active_futures: list[Future] = []
        self._active_lock = threading.Lock()
        self._ast_cache: dict[str, dict] = {}
        self._program_ast_cache: dict[str, dict] = {}

        # Registry state
        self._registered_names: list[str] = []
        self._registrations: dict[str, HandlerRegistration] = {}
        self._last_refresh: int = 0

        # Download lock to prevent concurrent downloads of the same artifact
        self._download_locks: dict[str, threading.Lock] = {}
        self._download_locks_guard = threading.Lock()

    @property
    def server_id(self) -> str:
        """Get the server's unique ID."""
        return self._server_id

    @property
    def is_running(self) -> bool:
        """Check if the runner is currently running."""
        return self._running

    # =========================================================================
    # Handler Registration
    # =========================================================================

    def register_handler(
        self,
        facet_name: str,
        module_uri: str,
        entrypoint: str = "",
        version: str = "1.0.0",
        checksum: str = "",
        timeout_ms: int = 300000,
        requirements: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a Maven artifact handler in persistence.

        Args:
            facet_name: Qualified event facet name (e.g. "ns.ProcessData")
            module_uri: Maven URI (``mvn:groupId:artifactId:version[:classifier]``)
            entrypoint: Optional main class (empty = executable JAR)
            version: Handler version string
            checksum: Cache-invalidation checksum
            timeout_ms: Subprocess timeout in milliseconds
            requirements: Unused (kept for API compatibility)
            metadata: Optional metadata dict (may contain ``jvm_args`` list)

        Raises:
            ValueError: If module_uri does not use the ``mvn:`` scheme.
        """
        if not module_uri.startswith("mvn:"):
            raise ValueError(
                f"MavenArtifactRunner requires 'mvn:' URI scheme, got: {module_uri}"
            )
        self._parse_maven_uri(module_uri)  # validate early

        now = _current_time_ms()
        reg = HandlerRegistration(
            facet_name=facet_name,
            module_uri=module_uri,
            entrypoint=entrypoint,
            version=version,
            checksum=checksum,
            timeout_ms=timeout_ms,
            requirements=requirements or [],
            metadata=metadata or {},
            created=now,
            updated=now,
        )
        self._persistence.save_handler_registration(reg)
        self._refresh_registry()

    def registered_names(self) -> list[str]:
        """Return the list of registered facet names (mvn: only)."""
        self._maybe_refresh_registry()
        return list(self._registered_names)

    # =========================================================================
    # Maven URI Parsing
    # =========================================================================

    @staticmethod
    def _parse_maven_uri(uri: str) -> tuple[str, str, str, str]:
        """Parse a Maven URI into components.

        Format: ``mvn:groupId:artifactId:version[:classifier]``

        Args:
            uri: The Maven URI string.

        Returns:
            Tuple of (group_id, artifact_id, version, classifier).
            Classifier is empty string if not present.

        Raises:
            ValueError: If the URI is malformed.
        """
        if not uri.startswith("mvn:"):
            raise ValueError(f"Invalid Maven URI scheme: {uri}")

        parts = uri[4:].split(":")
        if len(parts) < 3:
            raise ValueError(
                f"Invalid Maven URI (expected mvn:groupId:artifactId:version[:classifier]): {uri}"
            )
        if len(parts) > 4:
            raise ValueError(
                f"Invalid Maven URI (too many components): {uri}"
            )

        group_id, artifact_id, version = parts[0], parts[1], parts[2]
        classifier = parts[3] if len(parts) == 4 else ""

        if not group_id or not artifact_id or not version:
            raise ValueError(
                f"Invalid Maven URI (empty component): {uri}"
            )

        return group_id, artifact_id, version, classifier

    # =========================================================================
    # Artifact Resolution & Download
    # =========================================================================

    def _resolve_artifact(
        self, group_id: str, artifact_id: str, version: str, classifier: str
    ) -> Path:
        """Resolve a Maven artifact, downloading if not cached.

        Args:
            group_id: Maven group ID (e.g. "com.example")
            artifact_id: Maven artifact ID (e.g. "my-handler")
            version: Maven version (e.g. "1.0.0")
            classifier: Optional classifier (e.g. "jar-with-dependencies")

        Returns:
            Path to the local JAR file.
        """
        jar_name = f"{artifact_id}-{version}"
        if classifier:
            jar_name += f"-{classifier}"
        jar_name += ".jar"

        group_path = group_id.replace(".", os.sep)
        jar_path = Path(self._config.cache_dir) / group_path / artifact_id / version / jar_name

        if jar_path.exists() and jar_path.stat().st_size > 0:
            return jar_path

        return self._download_artifact(group_id, artifact_id, version, classifier)

    def _download_artifact(
        self, group_id: str, artifact_id: str, version: str, classifier: str
    ) -> Path:
        """Download a Maven artifact from the repository.

        Thread-safe: uses a per-artifact lock to prevent concurrent downloads.

        Args:
            group_id: Maven group ID
            artifact_id: Maven artifact ID
            version: Maven version
            classifier: Optional classifier

        Returns:
            Path to the downloaded JAR file.

        Raises:
            ValueError: If the download fails.
        """
        jar_name = f"{artifact_id}-{version}"
        if classifier:
            jar_name += f"-{classifier}"

        # Build URL (group dots → slashes for URL path)
        group_url_path = group_id.replace(".", "/")
        url = (
            f"{self._config.repository_url}/{group_url_path}"
            f"/{artifact_id}/{version}/{jar_name}.jar"
        )

        # Build local cache path (group dots → OS path separators)
        group_fs_path = group_id.replace(".", os.sep)
        jar_path = (
            Path(self._config.cache_dir) / group_fs_path
            / artifact_id / version / f"{jar_name}.jar"
        )

        # Per-artifact lock for thread safety
        lock_key = f"{group_id}:{artifact_id}:{version}:{classifier}"
        with self._download_locks_guard:
            if lock_key not in self._download_locks:
                self._download_locks[lock_key] = threading.Lock()
            artifact_lock = self._download_locks[lock_key]

        with artifact_lock:
            # Re-check after acquiring lock (another thread may have downloaded)
            if jar_path.exists() and jar_path.stat().st_size > 0:
                return jar_path

            jar_path.parent.mkdir(parents=True, exist_ok=True)

            coords = f"{group_id}:{artifact_id}:{version}"
            if classifier:
                coords += f":{classifier}"

            try:
                logger.info("Downloading Maven artifact %s from %s", coords, url)
                with urllib.request.urlopen(url, timeout=60) as response:
                    jar_bytes = response.read()
            except urllib.error.HTTPError as e:
                raise ValueError(
                    f"Failed to download artifact '{coords}': HTTP {e.code}"
                ) from e
            except urllib.error.URLError as e:
                raise ValueError(
                    f"Failed to download artifact '{coords}': {e.reason}"
                ) from e

            jar_path.write_bytes(jar_bytes)
            logger.info(
                "Cached Maven artifact %s (%d bytes) at %s",
                coords,
                len(jar_bytes),
                jar_path,
            )
            return jar_path

    # =========================================================================
    # Registry Refresh
    # =========================================================================

    def _matches_topics(self, facet_name: str) -> bool:
        """Check if a facet name matches any configured topic pattern."""
        return any(fnmatch.fnmatch(facet_name, pattern) for pattern in self._config.topics)

    def _refresh_registry(self) -> None:
        """Reload handler registrations from persistence, filtering to mvn: URIs."""
        registrations = self._persistence.list_handler_registrations()
        # Only pick up mvn: registrations
        mvn_regs = [r for r in registrations if r.module_uri.startswith("mvn:")]

        if self._config.topics:
            mvn_regs = [r for r in mvn_regs if self._matches_topics(r.facet_name)]

        self._registrations = {r.facet_name: r for r in mvn_regs}
        self._registered_names = list(self._registrations.keys())
        self._last_refresh = _current_time_ms()

    def _maybe_refresh_registry(self) -> None:
        """Refresh the registry if the refresh interval has elapsed."""
        now = _current_time_ms()
        if now - self._last_refresh >= self._config.registry_refresh_interval_ms:
            self._refresh_registry()

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> None:
        """Start the runner (blocking).

        Registers the server, starts the heartbeat thread, and enters
        the main poll loop. Blocks until stop() is called.
        """
        self._running = True
        self._stopping.clear()
        self._executor = ThreadPoolExecutor(max_workers=self._config.max_concurrent)

        try:
            self._refresh_registry()
            self._register_server()
            logger.info(
                "MavenArtifactRunner started: server_id=%s, service=%s, handlers=%s",
                self._server_id,
                self._config.service_name,
                self._registered_names,
            )

            # Start heartbeat daemon
            heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            heartbeat_thread.start()

            # Main poll loop
            self._poll_loop()

        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the runner to stop gracefully."""
        logger.info("MavenArtifactRunner stopping: server_id=%s", self._server_id)
        self._stopping.set()

    def poll_once(self) -> int:
        """Run a single poll cycle (synchronous, for testing).

        Does not use the thread pool executor. Claims and processes
        tasks sequentially.

        Returns:
            Number of tasks dispatched.
        """
        self._maybe_refresh_registry()

        if not self._registered_names:
            return 0

        capacity = self._config.max_concurrent - self._active_count()
        if capacity <= 0:
            return 0

        dispatched = 0
        task_names = list(self._registered_names)

        while capacity > 0:
            task = self._persistence.claim_task(
                task_names=task_names,
                task_list=self._config.task_list,
            )
            if task is None:
                break
            self._process_event(task)
            capacity -= 1
            dispatched += 1

        return dispatched

    # =========================================================================
    # AST Caching
    # =========================================================================

    def cache_workflow_ast(
        self, workflow_id: str, ast: dict, program_ast: dict | None = None
    ) -> None:
        """Pre-cache a workflow AST for use during processing.

        Args:
            workflow_id: The workflow ID
            ast: The compiled workflow AST dict
            program_ast: Optional full program AST for facet lookups
        """
        self._ast_cache[workflow_id] = ast
        if program_ast is not None:
            self._program_ast_cache[workflow_id] = program_ast

    def _load_workflow_ast(self, workflow_id: str) -> dict | None:
        """Load a workflow AST from persistence if available."""
        try:
            if not hasattr(self._persistence, "get_workflow"):
                return None

            wf = self._persistence.get_workflow(workflow_id)
            if not wf:
                return None

            if not hasattr(self._persistence, "get_flow"):
                return None

            flow = self._persistence.get_flow(wf.flow_id)
            if not flow or not flow.compiled_sources:
                return None

            import json

            from ..emitter import JSONEmitter
            from ..parser import AFLParser

            parser = AFLParser()
            ast = parser.parse(flow.compiled_sources[0].content)
            emitter = JSONEmitter(include_locations=False)
            program_dict = json.loads(emitter.emit(ast))

            for w in program_dict.get("workflows", []):
                if w["name"] == wf.name:
                    return w

            return None
        except Exception:
            logger.debug("Could not load AST for workflow %s", workflow_id, exc_info=True)
            return None

    # =========================================================================
    # Server Registration
    # =========================================================================

    def _register_server(self) -> None:
        """Register this runner in the persistence store."""
        now = _current_time_ms()
        server = ServerDefinition(
            uuid=self._server_id,
            server_group=self._config.server_group,
            service_name=self._config.service_name,
            server_name=self._config.server_name,
            server_ips=self._get_server_ips(),
            start_time=now,
            ping_time=now,
            topics=list(self._registered_names),
            handlers=list(self._registered_names),
            handled=[],
            state=ServerState.RUNNING,
        )
        self._persistence.save_server(server)

    def _deregister_server(self) -> None:
        """Mark this server as shut down."""
        server = self._persistence.get_server(self._server_id)
        if server:
            server.state = ServerState.SHUTDOWN
            server.ping_time = _current_time_ms()
            self._persistence.save_server(server)

    def _get_server_ips(self) -> list[str]:
        """Get local IP addresses."""
        try:
            hostname = socket.gethostname()
            return [socket.gethostbyname(hostname)]
        except Exception:
            return []

    # =========================================================================
    # Heartbeat
    # =========================================================================

    def _heartbeat_loop(self) -> None:
        """Periodically update the server's ping_time."""
        interval_s = self._config.heartbeat_interval_ms / 1000.0
        while not self._stopping.wait(interval_s):
            try:
                self._persistence.update_server_ping(self._server_id, _current_time_ms())
            except Exception:
                logger.exception("Heartbeat failed")

    # =========================================================================
    # Poll Loop
    # =========================================================================

    def _poll_loop(self) -> None:
        """Main loop: poll for work until stopped."""
        interval_s = self._config.poll_interval_ms / 1000.0
        while not self._stopping.is_set():
            try:
                self._maybe_refresh_registry()
                self._poll_cycle()
            except Exception:
                logger.exception("Poll cycle error")
            self._stopping.wait(interval_s)

    def _poll_cycle(self) -> int:
        """Single poll cycle: claim and dispatch tasks.

        Returns:
            Number of tasks dispatched.
        """
        self._cleanup_futures()

        capacity = self._config.max_concurrent - self._active_count()
        if capacity <= 0:
            return 0

        if not self._registered_names:
            return 0

        dispatched = 0
        task_names = list(self._registered_names)

        while capacity > 0:
            task = self._persistence.claim_task(
                task_names=task_names,
                task_list=self._config.task_list,
            )
            if task is None:
                break
            self._submit_event(task)
            capacity -= 1
            dispatched += 1

        return dispatched

    def _active_count(self) -> int:
        """Get the number of active work items."""
        with self._active_lock:
            return len(self._active_futures)

    def _cleanup_futures(self) -> None:
        """Remove completed futures from the active list."""
        with self._active_lock:
            self._active_futures = [f for f in self._active_futures if not f.done()]

    def _submit_event(self, task: Any) -> None:
        """Submit an event task to the thread pool."""
        if self._executor is None:
            self._process_event(task)
            return

        future = self._executor.submit(self._process_event, task)
        with self._active_lock:
            self._active_futures.append(future)

    # =========================================================================
    # Event Processing
    # =========================================================================

    def _process_event(self, task: Any) -> None:
        """Process an event task by launching a JVM subprocess.

        1. Look up HandlerRegistration by task name
        2. Parse mvn: URI → resolve artifact → get JAR path
        3. Build command with optional JVM args and main class
        4. Launch subprocess with environment variables
        5. On success: read returns, continue step, resume workflow
        6. On failure: fail step, mark task FAILED
        """
        try:
            # Look up registration
            reg = self._registrations.get(task.name)
            if reg is None:
                error_msg = f"No handler registration for event task '{task.name}'"
                self._evaluator.fail_step(task.step_id, error_msg)
                task.state = TaskState.FAILED
                task.error = {"message": error_msg}
                task.updated = _current_time_ms()
                self._persistence.save_task(task)
                logger.warning(
                    "No handler registration for event task '%s' (step=%s)",
                    task.name,
                    task.step_id,
                )
                return

            # Parse URI and resolve artifact
            try:
                group_id, artifact_id, version, classifier = self._parse_maven_uri(
                    reg.module_uri
                )
                jar_path = self._resolve_artifact(group_id, artifact_id, version, classifier)
            except ValueError as exc:
                error_msg = f"Failed to resolve artifact for '{task.name}': {exc}"
                self._evaluator.fail_step(task.step_id, error_msg)
                task.state = TaskState.FAILED
                task.error = {"message": error_msg}
                task.updated = _current_time_ms()
                self._persistence.save_task(task)
                logger.exception(
                    "Failed to resolve artifact for '%s' (step=%s)",
                    task.name,
                    task.step_id,
                )
                return

            # Build command
            jvm_args = reg.metadata.get("jvm_args", []) if reg.metadata else []
            java_cmd = self._config.java_command

            if reg.entrypoint:
                # Main class specified: java [jvm_args] -cp artifact.jar MainClass <stepId>
                cmd = [java_cmd, *jvm_args, "-cp", str(jar_path), reg.entrypoint, task.step_id]
            else:
                # Executable JAR: java [jvm_args] -jar artifact.jar <stepId>
                cmd = [java_cmd, *jvm_args, "-jar", str(jar_path), task.step_id]

            # Set environment variables
            env = os.environ.copy()
            env["AFL_STEP_ID"] = task.step_id
            if hasattr(self._persistence, "mongodb_url"):
                env["AFL_MONGODB_URL"] = self._persistence.mongodb_url
            if hasattr(self._persistence, "mongodb_database"):
                env["AFL_MONGODB_DATABASE"] = self._persistence.mongodb_database

            # Launch subprocess
            timeout_s = (reg.timeout_ms or self._config.default_timeout_ms) / 1000.0
            try:
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                error_msg = (
                    f"Subprocess timed out after {timeout_s}s for '{task.name}' "
                    f"(step={task.step_id})"
                )
                self._evaluator.fail_step(task.step_id, error_msg)
                task.state = TaskState.FAILED
                task.error = {"message": error_msg}
                task.updated = _current_time_ms()
                self._persistence.save_task(task)
                logger.error(error_msg)
                return

            if result.returncode != 0:
                stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
                error_msg = (
                    f"Subprocess failed (exit {result.returncode}) for '{task.name}': "
                    f"{stderr_text}"
                )
                self._evaluator.fail_step(task.step_id, error_msg)
                task.state = TaskState.FAILED
                task.error = {"message": error_msg}
                task.updated = _current_time_ms()
                self._persistence.save_task(task)
                logger.error(
                    "Subprocess failed for '%s' (step=%s, exit=%d): %s",
                    task.name,
                    task.step_id,
                    result.returncode,
                    stderr_text,
                )
                return

            # Success: read returns from persistence and continue step
            returns = self._read_step_returns(task.step_id)
            self._evaluator.continue_step(task.step_id, returns)

            # Resume the workflow
            self._resume_workflow(task.workflow_id)

            # Mark task completed
            task.state = TaskState.COMPLETED
            task.updated = _current_time_ms()
            self._persistence.save_task(task)

            logger.info(
                "Processed Maven event task %s (name=%s, step=%s)",
                task.uuid,
                task.name,
                task.step_id,
            )

        except Exception as exc:
            try:
                self._evaluator.fail_step(task.step_id, str(exc))
            except Exception:
                logger.debug("Could not fail step %s", task.step_id, exc_info=True)
            task.state = TaskState.FAILED
            task.error = {"message": str(exc)}
            task.updated = _current_time_ms()
            self._persistence.save_task(task)
            logger.exception(
                "Error processing Maven event task %s (name=%s)",
                task.uuid,
                task.name,
            )

    def _read_step_returns(self, step_id: str) -> dict:
        """Read step returns from persistence as a flat dict.

        The JVM program is expected to have written return attributes
        to the step's ``attributes.returns`` in MongoDB. This method
        reads them back as ``{name: value}`` for ``continue_step()``.

        Args:
            step_id: The step ID to read returns from.

        Returns:
            Dict mapping return attribute names to their values.
        """
        step = self._persistence.get_step(step_id)
        if step is None:
            return {}

        if step.attributes is None or not step.attributes.returns:
            return {}

        result = {}
        for name, attr in step.attributes.returns.items():
            if isinstance(attr, dict):
                result[name] = attr.get("value")
            elif hasattr(attr, "value"):
                result[name] = attr.value
            else:
                result[name] = attr
        return result

    # =========================================================================
    # Workflow Resume
    # =========================================================================

    def _resume_workflow(self, workflow_id: str) -> None:
        """Resume a paused workflow after step completion."""
        workflow_ast = self._ast_cache.get(workflow_id)
        if workflow_ast is None:
            workflow_ast = self._load_workflow_ast(workflow_id)
            if workflow_ast:
                self._ast_cache[workflow_id] = workflow_ast

        if workflow_ast is None:
            logger.warning(
                "No AST available for workflow %s, skipping resume",
                workflow_id,
            )
            return

        program_ast = self._program_ast_cache.get(workflow_id)
        self._evaluator.resume(workflow_id, workflow_ast, program_ast=program_ast)

    # =========================================================================
    # Shutdown
    # =========================================================================

    def _shutdown(self) -> None:
        """Gracefully shut down the runner."""
        self._running = False

        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=False)
            with self._active_lock:
                for future in self._active_futures:
                    try:
                        future.result(timeout=30)
                    except Exception:
                        pass
                self._active_futures.clear()
            self._executor = None

        try:
            self._deregister_server()
        except Exception:
            logger.exception("Error deregistering server")

        logger.info("MavenArtifactRunner stopped: server_id=%s", self._server_id)
