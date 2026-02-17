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

"""AFL Agent Poller library.

Standalone polling library for building AFL Agent services. The AgentPoller
handles one concern: poll the task queue for event tasks, dispatch to
registered callbacks, and manage the step/task lifecycle on success or failure.

Example usage::

    from afl.runtime import MemoryStore, Evaluator, Telemetry
    from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

    store = MongoStore(config)
    evaluator = Evaluator(persistence=store)

    poller = AgentPoller(
        persistence=store,
        evaluator=evaluator,
        config=AgentPollerConfig(service_name="my-agent"),
    )

    def count_documents(payload: dict) -> dict:
        count = db.collection.count_documents(payload.get("filter", {}))
        return {"count": count}

    poller.register("ns.CountDocuments", count_documents)
    poller.start()  # blocks until stopped

For async handlers (e.g., LLM-based handlers)::

    async def llm_handler(payload: dict) -> dict:
        response = await openai.chat.completions.create(...)
        return {"response": response}

    poller.register_async("ns.LLMQuery", llm_handler)
"""

import asyncio
import inspect
import logging
import socket
import threading
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Union

from .entities import (
    RunnerState,
    ServerDefinition,
    ServerState,
    TaskState,
)
from .evaluator import Evaluator, ExecutionStatus
from .persistence import PersistenceAPI
from .types import generate_id

logger = logging.getLogger(__name__)

# Type aliases for sync and async callbacks
SyncCallback = Callable[[dict], dict]
AsyncCallback = Callable[[dict], Awaitable[dict]]
AnyCallback = Union[SyncCallback, AsyncCallback]


def _current_time_ms() -> int:
    """Get current time in milliseconds."""
    return int(time.time() * 1000)


@dataclass
class AgentPollerConfig:
    """Configuration for the AgentPoller."""

    service_name: str = "afl-agent"
    server_group: str = "default"
    server_name: str = ""
    task_list: str = "default"
    poll_interval_ms: int = 2000
    max_concurrent: int = 5
    heartbeat_interval_ms: int = 10000

    def __post_init__(self) -> None:
        if not self.server_name:
            self.server_name = socket.gethostname()


class AgentPoller:
    """Polls the task queue for event tasks and dispatches to registered callbacks.

    Handles task claiming, callback dispatch, step continuation/failure,
    and workflow resumption. Multiple AgentPoller instances can run
    concurrently, coordinated through the persistence store's atomic
    claim_task mechanism.
    """

    def __init__(
        self,
        persistence: PersistenceAPI,
        evaluator: Evaluator,
        config: AgentPollerConfig | None = None,
    ) -> None:
        self._persistence = persistence
        self._evaluator = evaluator
        self._config = config or AgentPollerConfig()

        self._server_id = generate_id()
        self._handlers: dict[str, AnyCallback] = {}
        self._running = False
        self._stopping = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._active_futures: list[Future] = []
        self._active_lock = threading.Lock()
        self._ast_cache: dict[str, dict] = {}
        self._program_ast_cache: dict[str, dict] = {}
        self._resume_locks: dict[str, threading.Lock] = {}
        self._resume_locks_lock = threading.Lock()

    @property
    def server_id(self) -> str:
        """Get the server's unique ID."""
        return self._server_id

    @property
    def is_running(self) -> bool:
        """Check if the poller is currently running."""
        return self._running

    # =========================================================================
    # Registration
    # =========================================================================

    def register(self, facet_name: str, callback: SyncCallback) -> None:
        """Register a synchronous callback for a qualified facet name.

        Args:
            facet_name: Qualified event facet name (e.g. "ns.CountDocuments")
            callback: Sync function (payload_dict) -> result_dict.
                      Raise an exception to signal failure.
        """
        self._handlers[facet_name] = callback

    def register_async(self, facet_name: str, callback: AsyncCallback) -> None:
        """Register an async callback for a qualified facet name.

        Async callbacks are useful for LLM-based handlers that need to await
        API calls. The callback will be invoked with asyncio.run().

        Args:
            facet_name: Qualified event facet name (e.g. "ns.LLMQuery")
            callback: Async function (payload_dict) -> result_dict.
                      Raise an exception to signal failure.
        """
        self._handlers[facet_name] = callback

    def registered_names(self) -> list[str]:
        """Return the list of registered facet names."""
        return list(self._handlers.keys())

    def update_step(self, step_id: str, partial_result: dict) -> None:
        """Update a step with partial results (for streaming handlers).

        This method can be called from within a handler to incrementally
        update the step's return attributes before final completion.
        Useful for streaming LLM responses.

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

        # Merge partial results into existing returns
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
        """Start the poller (blocking).

        Registers the server, starts the heartbeat thread, and enters
        the main poll loop. Blocks until stop() is called.

        Signal handlers (SIGTERM/SIGINT) should be set up by the caller.
        """
        self._running = True
        self._stopping.clear()
        self._executor = ThreadPoolExecutor(max_workers=self._config.max_concurrent)

        try:
            self._register_server()
            logger.info(
                "AgentPoller started: server_id=%s, service=%s, handlers=%s",
                self._server_id,
                self._config.service_name,
                list(self._handlers.keys()),
            )

            # Start heartbeat daemon
            heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            heartbeat_thread.start()

            # Main poll loop
            self._poll_loop()

        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the poller to stop gracefully."""
        logger.info("AgentPoller stopping: server_id=%s", self._server_id)
        self._stopping.set()

    def poll_once(self) -> int:
        """Run a single poll cycle (synchronous, for testing).

        Does not use the thread pool executor. Claims and processes
        tasks sequentially.

        Returns:
            Number of tasks dispatched.
        """
        if not self._handlers:
            return 0

        capacity = self._config.max_concurrent - self._active_count()
        if capacity <= 0:
            return 0

        dispatched = 0
        task_names = list(self._handlers.keys())

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
        """Load a workflow AST from persistence if available.

        Returns None if the persistence store does not support flow lookups.
        """
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

            # Cache program AST for facet definition lookups during resume
            self._program_ast_cache[workflow_id] = program_dict

            return self._find_workflow_in_program(program_dict, wf.name)
        except Exception:
            logger.debug("Could not load AST for workflow %s", workflow_id, exc_info=True)
            return None

    @staticmethod
    def _find_workflow_in_program(program_dict: dict, workflow_name: str) -> dict | None:
        """Find a workflow in the program AST by name.

        Supports both simple names and qualified names (e.g. "ns.WorkflowName").
        """
        # Check top-level workflows
        for w in program_dict.get("workflows", []):
            if w.get("name") == workflow_name:
                return w

        # Handle qualified names by searching declarations/namespaces
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
        """Register this agent in the persistence store."""
        now = _current_time_ms()
        server = ServerDefinition(
            uuid=self._server_id,
            server_group=self._config.server_group,
            service_name=self._config.service_name,
            server_name=self._config.server_name,
            server_ips=self._get_server_ips(),
            start_time=now,
            ping_time=now,
            topics=list(self._handlers.keys()),
            handlers=list(self._handlers.keys()),
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

        if not self._handlers:
            return 0

        dispatched = 0
        task_names = list(self._handlers.keys())

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
        """Process an event task.

        1. Extract payload from task.data
        2. Look up callback by task.name (try qualified, then short name)
        3. Call callback(payload)
        4. On success: continue_step, resume workflow, mark task completed
        5. On failure: fail_step, mark task failed
        """
        try:
            payload = task.data or {}

            # Look up callback (try exact name, then short name)
            callback = self._handlers.get(task.name)
            if callback is None and "." in task.name:
                short_name = task.name.rsplit(".", 1)[-1]
                callback = self._handlers.get(short_name)

            if callback is None:
                error_msg = f"No handler for event task '{task.name}'"
                self._evaluator.fail_step(task.step_id, error_msg)
                task.state = TaskState.FAILED
                task.error = {"message": error_msg}
                task.updated = _current_time_ms()
                self._persistence.save_task(task)
                logger.warning(
                    "No handler for event task '%s' (step=%s)",
                    task.name,
                    task.step_id,
                )
                return

            # Invoke callback (handle both sync and async)
            if inspect.iscoroutinefunction(callback):
                result = asyncio.run(callback(payload))
            else:
                result = callback(payload)

            # Continue the step with the result
            self._evaluator.continue_step(task.step_id, result)

            # Resume the workflow
            self._resume_workflow(task.workflow_id, task.runner_id)

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

    def _resume_workflow(self, workflow_id: str, runner_id: str = "") -> None:
        """Resume a paused workflow after step completion."""
        # Acquire per-workflow lock to prevent concurrent resumes
        with self._resume_locks_lock:
            if workflow_id not in self._resume_locks:
                self._resume_locks[workflow_id] = threading.Lock()
            lock = self._resume_locks[workflow_id]

        if not lock.acquire(blocking=False):
            logger.debug("Resume already in progress for workflow %s, skipping", workflow_id)
            return

        try:
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
            result = self._evaluator.resume(workflow_id, workflow_ast, program_ast=program_ast)

            if runner_id and result.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.ERROR,
            ):
                self._update_runner_state(runner_id, result)
        finally:
            lock.release()

    def _update_runner_state(self, runner_id: str, result: "ExecutionResult") -> None:
        """Update runner state based on execution result."""
        from .evaluator import ExecutionResult  # noqa: F811 (type hint)

        try:
            runner = self._persistence.get_runner(runner_id)
            if runner and runner.state == RunnerState.RUNNING:
                now = _current_time_ms()
                if result.status == ExecutionStatus.COMPLETED:
                    runner.state = RunnerState.COMPLETED
                    runner.end_time = now
                    runner.duration = now - (runner.start_time or now)
                elif result.status == ExecutionStatus.ERROR:
                    runner.state = RunnerState.FAILED
                    runner.end_time = now
                    runner.duration = now - (runner.start_time or now)
                self._persistence.save_runner(runner)
                logger.info("Updated runner %s state to %s", runner_id, runner.state)
        except Exception:
            logger.debug("Could not update runner %s", runner_id, exc_info=True)

    # =========================================================================
    # Shutdown
    # =========================================================================

    def _shutdown(self) -> None:
        """Gracefully shut down the poller."""
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

        logger.info("AgentPoller stopped: server_id=%s", self._server_id)
