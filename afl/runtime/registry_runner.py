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

"""AFL Registry Runner.

A universal runner that reads handler registrations from persistence,
dynamically loads Python modules, caches them, and dispatches tasks.
This eliminates the need for per-facet microservices — developers
register a ``(facet_name, module_uri, entrypoint)`` tuple and the
RegistryRunner handles the rest.

Example usage::

    from afl.runtime import MemoryStore, Evaluator, Telemetry
    from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig

    store = MemoryStore()
    evaluator = Evaluator(persistence=store)

    runner = RegistryRunner(
        persistence=store,
        evaluator=evaluator,
        config=RegistryRunnerConfig(service_name="my-registry-runner"),
    )

    # Register a handler (persisted — survives restarts)
    runner.register_handler(
        facet_name="ns.CountDocuments",
        module_uri="my.handlers",
        entrypoint="count_documents",
    )

    runner.start()  # blocks until stopped
"""

import fnmatch
import logging
import socket
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .dispatcher import RegistryDispatcher
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
class RegistryRunnerConfig:
    """Configuration for the RegistryRunner."""

    service_name: str = "afl-registry-runner"
    server_group: str = "default"
    server_name: str = ""
    task_list: str = "default"
    poll_interval_ms: int = 2000
    max_concurrent: int = 5
    heartbeat_interval_ms: int = 10000
    registry_refresh_interval_ms: int = 30000
    topics: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.server_name:
            self.server_name = socket.gethostname()


class RegistryRunner:
    """Universal runner that dynamically loads handlers from persistence.

    Instead of requiring developers to write standalone microservices,
    handler registrations are stored in the persistence layer and
    loaded on demand. Module loading results are cached by
    ``(module_uri, checksum)`` for efficiency.
    """

    def __init__(
        self,
        persistence: PersistenceAPI,
        evaluator: Evaluator,
        config: RegistryRunnerConfig | None = None,
    ) -> None:
        self._persistence = persistence
        self._evaluator = evaluator
        self._config = config or RegistryRunnerConfig()

        self._server_id = generate_id()
        self._running = False
        self._stopping = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._active_futures: list[Future] = []
        self._active_lock = threading.Lock()
        self._ast_cache: dict[str, dict] = {}
        self._program_ast_cache: dict[str, dict] = {}

        # Shared dispatcher for inline execution and _process_event
        self._dispatcher = RegistryDispatcher(
            persistence=persistence,
            topics=self._config.topics if self._config.topics else None,
        )

        # Registry-specific state (delegate module cache to dispatcher)
        self._module_cache = self._dispatcher.module_cache
        self._registered_names: list[str] = []
        self._last_refresh: int = 0

    @property
    def server_id(self) -> str:
        """Get the server's unique ID."""
        return self._server_id

    @property
    def is_running(self) -> bool:
        """Check if the runner is currently running."""
        return self._running

    # =========================================================================
    # Handler Registration (convenience API)
    # =========================================================================

    def register_handler(
        self,
        facet_name: str,
        module_uri: str,
        entrypoint: str = "handle",
        version: str = "1.0.0",
        checksum: str = "",
        timeout_ms: int = 30000,
        requirements: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a handler in persistence (convenience method).

        Creates a ``HandlerRegistration`` and saves it to the persistence
        store. The registration is picked up on the next registry refresh.

        Args:
            facet_name: Qualified event facet name (e.g. "ns.CountDocuments")
            module_uri: Python module path or ``file:///path/to/module.py``
            entrypoint: Function name within the module (default: "handle")
            version: Handler version string
            checksum: Cache-invalidation checksum
            timeout_ms: Handler timeout in milliseconds
            requirements: Optional pip requirements
            metadata: Optional metadata dict
        """
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
        # Force immediate refresh so the name is available for polling
        self._refresh_registry()

    def registered_names(self) -> list[str]:
        """Return the list of registered facet names (from persistence)."""
        self._maybe_refresh_registry()
        return list(self._registered_names)

    # =========================================================================
    # Registry Refresh
    # =========================================================================

    def _matches_topics(self, facet_name: str) -> bool:
        """Check if a facet name matches any configured topic pattern."""
        return any(fnmatch.fnmatch(facet_name, pattern) for pattern in self._config.topics)

    def _refresh_registry(self) -> None:
        """Reload handler registrations from persistence."""
        registrations = self._persistence.list_handler_registrations()
        names = [r.facet_name for r in registrations]
        if self._config.topics:
            names = [n for n in names if self._matches_topics(n)]
        self._registered_names = names
        self._last_refresh = _current_time_ms()

    def _maybe_refresh_registry(self) -> None:
        """Refresh the registry if the refresh interval has elapsed."""
        now = _current_time_ms()
        if now - self._last_refresh >= self._config.registry_refresh_interval_ms:
            self._refresh_registry()

    def update_step(self, step_id: str, partial_result: dict) -> None:
        """Update a step with partial results (for streaming handlers).

        Args:
            step_id: The step ID to update
            partial_result: Dict of return attribute names to values to merge

        Raises:
            ValueError: If step is not found
        """
        from .step import FacetAttributes

        step = self._persistence.get_step(step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        if step.attributes is None:
            step.attributes = FacetAttributes()
        if step.attributes.returns is None:
            step.attributes.returns = {}

        for name, value in partial_result.items():
            step.attributes.returns[name] = {
                "name": name,
                "value": value,
                "type_hint": self._infer_type_hint(value),
            }

        self._persistence.save_step(step)

    def _infer_type_hint(self, value: object) -> str:
        """Infer type hint from a Python value."""
        if isinstance(value, bool):
            return "Boolean"
        elif isinstance(value, int):
            return "Long"
        elif isinstance(value, float):
            return "Double"
        elif isinstance(value, str):
            return "String"
        elif isinstance(value, list):
            return "List"
        elif isinstance(value, dict):
            return "Map"
        elif value is None:
            return "Any"
        else:
            return "Any"

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
                "RegistryRunner started: server_id=%s, service=%s, handlers=%s",
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
        logger.info("RegistryRunner stopping: server_id=%s", self._server_id)
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

            return self._find_workflow_in_program(program_dict, wf.name)
        except Exception:
            logger.debug("Could not load AST for workflow %s", workflow_id, exc_info=True)
            return None

    @staticmethod
    def _find_workflow_in_program(program_dict: dict, workflow_name: str) -> dict | None:
        """Find a workflow in the program AST by name.

        Supports both simple names and qualified names (e.g. "ns.WorkflowName").
        """
        for w in program_dict.get("workflows", []):
            if w.get("name") == workflow_name:
                return w

        if "." in workflow_name:
            parts = workflow_name.split(".")
            short_name = parts[-1]
            ns_prefix = ".".join(parts[:-1])

            for decl in program_dict.get("declarations", []):
                if decl.get("type") == "Namespace" and decl.get("name") == ns_prefix:
                    for w in decl.get("workflows", []):
                        if w.get("name") == short_name:
                            return w
                    for d in decl.get("declarations", []):
                        if d.get("type") == "WorkflowDecl" and d.get("name") == short_name:
                            return d

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
        """Process an event task via dynamic handler lookup.

        Delegates handler loading and invocation to the shared
        RegistryDispatcher. On success, continues the step and
        resumes the workflow; on failure, fails the step.
        """
        try:
            payload = dict(task.data or {})  # shallow copy to avoid mutating task.data

            if not self._dispatcher.can_dispatch(task.name):
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

            # Dispatch via shared dispatcher (handles module loading + async detection)
            try:
                result = self._dispatcher.dispatch(task.name, payload)
            except (ImportError, AttributeError, TypeError) as exc:
                error_msg = f"Failed to load handler for '{task.name}': {exc}"
                self._evaluator.fail_step(task.step_id, error_msg)
                task.state = TaskState.FAILED
                task.error = {"message": error_msg}
                task.updated = _current_time_ms()
                self._persistence.save_task(task)
                logger.exception(
                    "Failed to load handler for '%s' (step=%s)",
                    task.name,
                    task.step_id,
                )
                return

            # Continue the step with the result
            self._evaluator.continue_step(task.step_id, result)

            # Resume the workflow
            self._resume_workflow(task.workflow_id)

            # Mark task completed
            task.state = TaskState.COMPLETED
            task.updated = _current_time_ms()
            self._persistence.save_task(task)

            logger.info(
                "Processed event task %s (name=%s, step=%s)",
                task.uuid,
                task.name,
                task.step_id,
            )

        except Exception as exc:
            # Fail the step and mark task as failed
            try:
                self._evaluator.fail_step(task.step_id, str(exc))
            except Exception:
                logger.debug("Could not fail step %s", task.step_id, exc_info=True)
            task.state = TaskState.FAILED
            task.error = {"message": str(exc)}
            task.updated = _current_time_ms()
            self._persistence.save_task(task)
            logger.exception(
                "Error processing event task %s (name=%s)",
                task.uuid,
                task.name,
            )

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
        self._evaluator.resume(
            workflow_id, workflow_ast, program_ast=program_ast, dispatcher=self._dispatcher
        )

    # =========================================================================
    # Shutdown
    # =========================================================================

    def _shutdown(self) -> None:
        """Gracefully shut down the runner."""
        self._running = False

        # Wait for active work to complete
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

        # Deregister server
        try:
            self._deregister_server()
        except Exception:
            logger.exception("Error deregistering server")

        logger.info("RegistryRunner stopped: server_id=%s", self._server_id)
