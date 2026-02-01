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

"""MongoDB implementation of PersistenceAPI.

This module provides a MongoDB-backed persistence layer for the AFL runtime.
It requires the pymongo package to be installed.
"""

import time
from collections.abc import Sequence
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, TypeVar

try:
    from pymongo import ASCENDING, MongoClient, ReturnDocument
    from pymongo.collection import Collection  # noqa: F401
    from pymongo.database import Database
    from pymongo.errors import DuplicateKeyError

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

if TYPE_CHECKING:
    from ..config import MongoDBConfig

from .entities import (
    FlowDefinition,
    FlowIdentity,
    HandledCount,
    LockDefinition,
    LockMetaData,
    LogDefinition,
    Parameter,
    RunnerDefinition,
    ServerDefinition,
    TaskDefinition,
    WorkflowDefinition,
)
from .persistence import EventDefinition, IterationChanges, PersistenceAPI
from .step import StepDefinition
from .types import BlockId, EventId, StepId, VersionInfo, WorkflowId

T = TypeVar("T")


def _current_time_ms() -> int:
    """Get current time in milliseconds."""
    return int(time.time() * 1000)


class MongoStore(PersistenceAPI):
    """MongoDB implementation of the persistence API.

    Provides full persistence to MongoDB with proper indexes,
    transactions, and serialization.

    Usage:
        store = MongoStore("mongodb://localhost:27017", "afl")
        store.get_step(step_id)

        # Or create from an AFLConfig / MongoDBConfig:
        from afl.config import load_config
        config = load_config()
        store = MongoStore.from_config(config.mongodb)
    """

    def __init__(
        self,
        connection_string: str = "",
        database_name: str = "afl",
        create_indexes: bool = True,
        client: Any = None,
    ):
        """Initialize the MongoDB store.

        Args:
            connection_string: MongoDB connection string
            database_name: Database name (default: "afl")
            create_indexes: Whether to create indexes on initialization
            client: Optional pre-built MongoClient (e.g. mongomock.MongoClient for testing)
        """
        if client is not None:
            self._client = client
        else:
            if not PYMONGO_AVAILABLE:
                raise ImportError(
                    "pymongo is required for MongoStore. Install it with: pip install pymongo"
                )
            self._client: MongoClient = MongoClient(connection_string)

        self._db: Database = self._client[database_name]

        if create_indexes:
            self._ensure_indexes()

    @classmethod
    def from_config(
        cls,
        config: "MongoDBConfig",
        create_indexes: bool = True,
    ) -> "MongoStore":
        """Create a MongoStore from a MongoDBConfig instance.

        Args:
            config: MongoDB configuration with url, database, etc.
            create_indexes: Whether to create indexes on initialization

        Returns:
            A configured MongoStore instance.
        """
        return cls(
            connection_string=config.connection_string(),
            database_name=config.database,
            create_indexes=create_indexes,
        )

    def _ensure_indexes(self) -> None:
        """Create indexes on all collections."""
        # Steps collection
        steps = self._db.steps
        steps.create_index("uuid", unique=True, name="step_uuid_index")
        steps.create_index("workflow_id", name="step_workflow_id_index")
        steps.create_index("block_id", name="step_block_id_index")
        steps.create_index("container_id", name="step_container_id_index")
        steps.create_index("state", name="step_state_index")

        # Events collection
        events = self._db.events
        events.create_index("uuid", unique=True, name="event_uuid_index")
        events.create_index("runner_id", name="event_runner_id_index")
        events.create_index("step_id", name="event_step_id_index")
        events.create_index("state", name="event_state_index")
        events.create_index("topic", name="event_topic_index")
        events.create_index("handler", name="event_handler_index")
        # Partial unique index for running events
        events.create_index(
            "step_id",
            unique=True,
            partialFilterExpression={"state": "running"},
            name="event_step_id_running_unique_index",
        )

        # Flows collection
        flows = self._db.flows
        flows.create_index("uuid", unique=True, name="flow_uuid_index")
        flows.create_index("name.path", name="flow_path_index")
        flows.create_index("name.name", name="flow_name_index")

        # Workflows collection
        workflows = self._db.workflows
        workflows.create_index("uuid", unique=True, name="workflow_uuid_index")
        workflows.create_index("name", name="workflow_name_index")
        workflows.create_index("flow_id", name="workflow_flow_id_index")

        # Runners collection
        runners = self._db.runners
        runners.create_index("uuid", unique=True, name="runner_uuid_index")
        runners.create_index("workflow_id", name="runner_workflow_id_index")
        runners.create_index("state", name="runner_state_index")

        # Tasks collection
        tasks = self._db.tasks
        tasks.create_index("uuid", unique=True, name="task_uuid_index")
        tasks.create_index("runner_id", name="task_runner_id_index")
        tasks.create_index("step_id", name="task_step_id_index")
        tasks.create_index("task_list_name", name="task_list_name_index")
        tasks.create_index("state", name="task_state_index")
        # Partial unique index for running tasks
        tasks.create_index(
            "step_id",
            unique=True,
            partialFilterExpression={"state": "running"},
            name="task_step_id_running_unique_index",
        )
        # Compound index for efficient claim queries
        tasks.create_index(
            [("state", ASCENDING), ("name", ASCENDING), ("task_list_name", ASCENDING)],
            name="task_claim_index",
        )

        # Logs collection
        logs = self._db.logs
        logs.create_index("uuid", unique=True, name="log_uuid_index")
        logs.create_index("runner_id", name="log_runner_id_index")
        logs.create_index("object_id", name="log_object_id_index")

        # Servers collection
        servers = self._db.servers
        servers.create_index("uuid", unique=True, name="server_uuid_index")

        # Locks collection
        locks = self._db.locks
        locks.create_index("key", unique=True, name="lock_key_index")
        locks.create_index("expires_at", name="lock_expires_at_index")

    # =========================================================================
    # Step Operations (PersistenceAPI)
    # =========================================================================

    def get_step(self, step_id: StepId) -> StepDefinition | None:
        """Fetch a step by ID."""
        doc = self._db.steps.find_one({"uuid": step_id})
        return self._doc_to_step(doc) if doc else None

    def get_steps_by_block(self, block_id: BlockId) -> Sequence[StepDefinition]:
        """Fetch all steps in a block."""
        docs = self._db.steps.find({"block_id": block_id})
        return [self._doc_to_step(doc) for doc in docs]

    def get_steps_by_workflow(self, workflow_id: WorkflowId) -> Sequence[StepDefinition]:
        """Fetch all steps in a workflow."""
        docs = self._db.steps.find({"workflow_id": workflow_id})
        return [self._doc_to_step(doc) for doc in docs]

    def get_steps_by_state(self, state: str) -> Sequence[StepDefinition]:
        """Fetch all steps in a given state."""
        docs = self._db.steps.find({"state": state})
        return [self._doc_to_step(doc) for doc in docs]

    def get_steps_by_container(self, container_id: StepId) -> Sequence[StepDefinition]:
        """Fetch all steps with a given container."""
        docs = self._db.steps.find({"container_id": container_id})
        return [self._doc_to_step(doc) for doc in docs]

    def save_step(self, step: StepDefinition) -> None:
        """Save a step to the store."""
        doc = self._step_to_doc(step)
        self._db.steps.replace_one({"uuid": step.id}, doc, upsert=True)

    def get_blocks_by_step(self, step_id: StepId) -> Sequence[StepDefinition]:
        """Fetch all block steps for a containing step."""
        docs = self._db.steps.find(
            {
                "container_id": step_id,
                "object_type": {"$in": ["AndThen", "AndMap", "AndMatch", "Block"]},
            }
        )
        return [self._doc_to_step(doc) for doc in docs]

    def get_workflow_root(self, workflow_id: WorkflowId) -> StepDefinition | None:
        """Get the root step of a workflow."""
        doc = self._db.steps.find_one(
            {"workflow_id": workflow_id, "root_id": None, "container_id": None}
        )
        return self._doc_to_step(doc) if doc else None

    def step_exists(self, statement_id: str, block_id: BlockId | None) -> bool:
        """Check if a step already exists for a statement in a block."""
        query = {"statement_id": statement_id}
        if block_id:
            query["block_id"] = block_id
        else:
            query["block_id"] = None
        return self._db.steps.count_documents(query, limit=1) > 0

    # =========================================================================
    # Event Operations (PersistenceAPI)
    # =========================================================================

    def get_event(self, event_id: EventId) -> EventDefinition | None:
        """Fetch an event by ID."""
        doc = self._db.events.find_one({"uuid": event_id})
        return self._doc_to_event(doc) if doc else None

    def save_event(self, event: EventDefinition) -> None:
        """Save an event to the store."""
        doc = self._event_to_doc(event)
        self._db.events.replace_one({"uuid": event.id}, doc, upsert=True)

    def get_events_by_workflow(self, workflow_id: str) -> Sequence[EventDefinition]:
        """Get all events for a workflow."""
        docs = self._db.events.find({"workflow_id": workflow_id})
        return [self._doc_to_event(doc) for doc in docs]

    # =========================================================================
    # Atomic Commit (PersistenceAPI)
    # =========================================================================

    def commit(self, changes: IterationChanges) -> None:
        """Atomically commit all iteration changes.

        Uses a MongoDB transaction when the server supports it (replica set
        or mongos). Falls back to non-transactional writes for standalone
        servers and mongomock.
        """
        try:
            session = self._client.start_session()
        except (NotImplementedError, Exception):
            # mongomock raises NotImplementedError;
            # standalone servers may raise ConfigurationError
            self._commit_changes(changes, session=None)
            return

        try:
            with session:
                with session.start_transaction():
                    self._commit_changes(changes, session=session)
        except Exception as exc:
            # Standalone MongoDB raises OperationFailure (code 20) for
            # transactions. Fall back to non-transactional writes.
            exc_msg = str(exc).lower()
            if "transaction" in exc_msg or "replica set" in exc_msg:
                self._commit_changes(changes, session=None)
            else:
                raise

    def _commit_changes(self, changes: IterationChanges, session: Any = None) -> None:
        """Write all iteration changes to MongoDB."""
        kwargs: dict[str, Any] = {}
        if session is not None:
            kwargs["session"] = session

        for step in changes.created_steps:
            doc = self._step_to_doc(step)
            self._db.steps.insert_one(doc, **kwargs)

        for step in changes.updated_steps:
            doc = self._step_to_doc(step)
            self._db.steps.replace_one({"uuid": step.id}, doc, **kwargs)

        for event in changes.created_events:
            doc = self._event_to_doc(event)
            self._db.events.insert_one(doc, **kwargs)

        for event in changes.updated_events:
            doc = self._event_to_doc(event)
            self._db.events.replace_one({"uuid": event.id}, doc, **kwargs)

        for task in changes.created_tasks:
            doc = self._task_to_doc(task)
            self._db.tasks.insert_one(doc, **kwargs)

    # =========================================================================
    # Runner Operations
    # =========================================================================

    def get_runner(self, runner_id: str) -> RunnerDefinition | None:
        """Get a runner by ID."""
        doc = self._db.runners.find_one({"uuid": runner_id})
        return self._doc_to_runner(doc) if doc else None

    def get_runners_by_workflow(self, workflow_id: str) -> Sequence[RunnerDefinition]:
        """Get all runners for a workflow."""
        docs = self._db.runners.find({"workflow_id": workflow_id})
        return [self._doc_to_runner(doc) for doc in docs]

    def get_runners_by_state(self, state: str) -> Sequence[RunnerDefinition]:
        """Get runners by state."""
        docs = self._db.runners.find({"state": state})
        return [self._doc_to_runner(doc) for doc in docs]

    def save_runner(self, runner: RunnerDefinition) -> None:
        """Save a runner."""
        doc = self._runner_to_doc(runner)
        self._db.runners.replace_one({"uuid": runner.uuid}, doc, upsert=True)

    def update_runner_state(self, runner_id: str, state: str) -> None:
        """Update runner state."""
        self._db.runners.update_one({"uuid": runner_id}, {"$set": {"state": state}})

    def get_all_runners(self, limit: int = 100) -> Sequence[RunnerDefinition]:
        """Get all runners, most recent first."""
        docs = self._db.runners.find().sort("start_time", -1).limit(limit)
        return [self._doc_to_runner(doc) for doc in docs]

    # =========================================================================
    # Task Operations
    # =========================================================================

    def get_task(self, task_id: str) -> TaskDefinition | None:
        """Get a task by ID."""
        doc = self._db.tasks.find_one({"uuid": task_id})
        return self._doc_to_task(doc) if doc else None

    def get_pending_tasks(self, task_list: str) -> Sequence[TaskDefinition]:
        """Get pending tasks for a task list."""
        docs = self._db.tasks.find({"task_list_name": task_list, "state": "pending"})
        return [self._doc_to_task(doc) for doc in docs]

    def save_task(self, task: TaskDefinition) -> None:
        """Save a task."""
        doc = self._task_to_doc(task)
        self._db.tasks.replace_one({"uuid": task.uuid}, doc, upsert=True)

    def claim_task(
        self,
        task_names: list[str],
        task_list: str = "default",
    ) -> TaskDefinition | None:
        """Atomically claim a pending task matching one of the given names.

        Uses find_one_and_update for atomic PENDING → RUNNING transition.
        The partial unique index on (step_id, state=running) ensures only
        one agent processes an event per step.
        """
        doc = self._db.tasks.find_one_and_update(
            {
                "state": "pending",
                "name": {"$in": task_names},
                "task_list_name": task_list,
            },
            {"$set": {"state": "running", "updated": _current_time_ms()}},
            return_document=ReturnDocument.AFTER,
        )
        return self._doc_to_task(doc) if doc else None

    def update_task_state(self, task_id: str, state: str) -> None:
        """Update task state."""
        self._db.tasks.update_one(
            {"uuid": task_id}, {"$set": {"state": state, "updated": _current_time_ms()}}
        )

    def get_all_tasks(self, limit: int = 100) -> Sequence[TaskDefinition]:
        """Get all tasks, most recently created first."""
        docs = self._db.tasks.find().sort("created", -1).limit(limit)
        return [self._doc_to_task(doc) for doc in docs]

    def get_tasks_by_runner(self, runner_id: str) -> Sequence[TaskDefinition]:
        """Get all tasks for a runner."""
        docs = self._db.tasks.find({"runner_id": runner_id})
        return [self._doc_to_task(doc) for doc in docs]

    # =========================================================================
    # Log Operations
    # =========================================================================

    def get_logs_by_runner(self, runner_id: str) -> Sequence[LogDefinition]:
        """Get logs for a runner."""
        docs = self._db.logs.find({"runner_id": runner_id}).sort("order", ASCENDING)
        return [self._doc_to_log(doc) for doc in docs]

    def save_log(self, log: LogDefinition) -> None:
        """Save a log entry."""
        doc = self._log_to_doc(log)
        self._db.logs.insert_one(doc)

    # =========================================================================
    # Lock Operations
    # =========================================================================

    def acquire_lock(self, key: str, duration_ms: int, meta: LockMetaData | None = None) -> bool:
        """Acquire a distributed lock."""
        now = _current_time_ms()
        expires_at = now + duration_ms

        # First, try to remove any expired lock
        self._db.locks.delete_one({"key": key, "expires_at": {"$lt": now}})

        # Try to insert the lock
        doc = {
            "key": key,
            "acquired_at": now,
            "expires_at": expires_at,
            "meta": asdict(meta) if meta else None,
        }

        try:
            self._db.locks.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    def release_lock(self, key: str) -> bool:
        """Release a distributed lock."""
        result = self._db.locks.delete_one({"key": key})
        return result.deleted_count > 0

    def check_lock(self, key: str) -> LockDefinition | None:
        """Check if a lock exists and is valid."""
        now = _current_time_ms()
        doc = self._db.locks.find_one({"key": key, "expires_at": {"$gt": now}})
        return self._doc_to_lock(doc) if doc else None

    def extend_lock(self, key: str, duration_ms: int) -> bool:
        """Extend a lock's expiration."""
        now = _current_time_ms()
        new_expires = now + duration_ms
        result = self._db.locks.update_one(
            {"key": key, "expires_at": {"$gt": now}}, {"$set": {"expires_at": new_expires}}
        )
        return result.modified_count > 0

    # =========================================================================
    # Flow Operations
    # =========================================================================

    def get_flow(self, flow_id: str) -> FlowDefinition | None:
        """Get a flow by ID."""
        doc = self._db.flows.find_one({"uuid": flow_id})
        return self._doc_to_flow(doc) if doc else None

    def get_flow_by_path(self, path: str) -> FlowDefinition | None:
        """Get a flow by path."""
        doc = self._db.flows.find_one({"name.path": path})
        return self._doc_to_flow(doc) if doc else None

    def get_flow_by_name(self, name: str) -> FlowDefinition | None:
        """Get a flow by name."""
        doc = self._db.flows.find_one({"name.name": name})
        return self._doc_to_flow(doc) if doc else None

    def save_flow(self, flow: FlowDefinition) -> None:
        """Save a flow."""
        doc = self._flow_to_doc(flow)
        self._db.flows.replace_one({"uuid": flow.uuid}, doc, upsert=True)

    def delete_flow(self, flow_id: str) -> bool:
        """Delete a flow."""
        result = self._db.flows.delete_one({"uuid": flow_id})
        return result.deleted_count > 0

    def get_all_flows(self) -> Sequence[FlowDefinition]:
        """Get all flows."""
        docs = self._db.flows.find()
        return [self._doc_to_flow(doc) for doc in docs]

    # =========================================================================
    # Workflow Operations
    # =========================================================================

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """Get a workflow by ID."""
        doc = self._db.workflows.find_one({"uuid": workflow_id})
        return self._doc_to_workflow(doc) if doc else None

    def get_workflow_by_name(self, name: str) -> WorkflowDefinition | None:
        """Get a workflow by name."""
        doc = self._db.workflows.find_one({"name": name})
        return self._doc_to_workflow(doc) if doc else None

    def get_workflows_by_flow(self, flow_id: str) -> Sequence[WorkflowDefinition]:
        """Get all workflows for a flow."""
        docs = self._db.workflows.find({"flow_id": flow_id})
        return [self._doc_to_workflow(doc) for doc in docs]

    def save_workflow(self, workflow: WorkflowDefinition) -> None:
        """Save a workflow."""
        doc = self._workflow_to_doc(workflow)
        self._db.workflows.replace_one({"uuid": workflow.uuid}, doc, upsert=True)

    # =========================================================================
    # Server Operations
    # =========================================================================

    def get_server(self, server_id: str) -> ServerDefinition | None:
        """Get a server by ID."""
        doc = self._db.servers.find_one({"uuid": server_id})
        return self._doc_to_server(doc) if doc else None

    def get_servers_by_state(self, state: str) -> Sequence[ServerDefinition]:
        """Get servers by state."""
        docs = self._db.servers.find({"state": state})
        return [self._doc_to_server(doc) for doc in docs]

    def get_all_servers(self) -> Sequence[ServerDefinition]:
        """Get all servers."""
        docs = self._db.servers.find()
        return [self._doc_to_server(doc) for doc in docs]

    def save_server(self, server: ServerDefinition) -> None:
        """Save a server."""
        doc = self._server_to_doc(server)
        self._db.servers.replace_one({"uuid": server.uuid}, doc, upsert=True)

    def update_server_ping(self, server_id: str, ping_time: int) -> None:
        """Update server ping time."""
        self._db.servers.update_one({"uuid": server_id}, {"$set": {"ping_time": ping_time}})

    # =========================================================================
    # Serialization Helpers
    # =========================================================================

    def _step_to_doc(self, step: StepDefinition) -> dict:
        """Convert StepDefinition to MongoDB document."""
        doc = {
            "uuid": step.id,
            "workflow_id": step.workflow_id,
            "object_type": step.object_type,
            "state": step.state,
            "statement_id": step.statement_id,
            "container_id": step.container_id,
            "root_id": step.root_id,
            "block_id": step.block_id,
            "facet_name": step.facet_name or None,
            "is_block": step.is_block,
            "is_starting_step": getattr(step, "is_starting_step", False),
            "version": {
                "workflow_version": step.version.workflow_version,
                "step_schema_version": step.version.step_schema_version,
                "runtime_version": step.version.runtime_version,
            }
            if step.version
            else {},
        }

        if step.attributes:
            doc["attributes"] = {
                "params": {
                    k: {"name": v.name, "value": v.value, "type_hint": v.type_hint}
                    for k, v in step.attributes.params.items()
                },
                "returns": {
                    k: {"name": v.name, "value": v.value, "type_hint": v.type_hint}
                    for k, v in step.attributes.returns.items()
                },
            }

        error = getattr(step, "error", None)
        if error is None and hasattr(step, "transition"):
            error = getattr(step.transition, "error", None)
        if error:
            doc["error"] = str(error)

        return doc

    def _doc_to_step(self, doc: dict) -> StepDefinition:
        """Convert MongoDB document to StepDefinition."""
        from .types import AttributeValue, FacetAttributes

        step = StepDefinition(
            id=StepId(doc["uuid"]),
            workflow_id=WorkflowId(doc["workflow_id"]),
            object_type=doc["object_type"],
            state=doc["state"],
        )

        step.statement_id = doc.get("statement_id")
        step.container_id = StepId(doc["container_id"]) if doc.get("container_id") else None
        step.root_id = StepId(doc["root_id"]) if doc.get("root_id") else None
        step.block_id = BlockId(doc["block_id"]) if doc.get("block_id") else None
        step.facet_name = doc.get("facet_name") or ""
        # is_block is a computed property on StepDefinition; skip setting it.
        # is_starting_step may not exist on all StepDefinition versions.
        if hasattr(step, "is_starting_step"):
            step.is_starting_step = doc.get("is_starting_step", False)
        version_doc = doc.get("version")
        if isinstance(version_doc, dict):
            step.version = VersionInfo(
                workflow_version=version_doc.get("workflow_version", "1.0"),
                step_schema_version=version_doc.get("step_schema_version", "1.0"),
                runtime_version=version_doc.get("runtime_version", "0.1.0"),
            )
        else:
            step.version = VersionInfo()

        if "attributes" in doc:
            attrs = doc["attributes"]
            step.attributes = FacetAttributes()
            for k, v in attrs.get("params", {}).items():
                step.attributes.params[k] = AttributeValue(
                    v["name"], v["value"], v.get("type_hint", "Any")
                )
            for k, v in attrs.get("returns", {}).items():
                step.attributes.returns[k] = AttributeValue(
                    v["name"], v["value"], v.get("type_hint", "Any")
                )

        if doc.get("error") and hasattr(step, "transition"):
            step.transition.error = Exception(doc["error"])

        return step

    def _event_to_doc(self, event: EventDefinition) -> dict:
        """Convert EventDefinition to MongoDB document."""
        return {
            "uuid": event.id,
            "step_id": event.step_id,
            "workflow_id": event.workflow_id,
            "state": event.state,
            "event_type": event.event_type,
            "payload": event.payload,
        }

    def _doc_to_event(self, doc: dict) -> EventDefinition:
        """Convert MongoDB document to EventDefinition."""
        return EventDefinition(
            id=EventId(doc["uuid"]),
            step_id=StepId(doc["step_id"]),
            workflow_id=WorkflowId(doc["workflow_id"]),
            state=doc["state"],
            event_type=doc["event_type"],
            payload=doc.get("payload", {}),
        )

    def _runner_to_doc(self, runner: RunnerDefinition) -> dict:
        """Convert RunnerDefinition to MongoDB document."""
        return {
            "uuid": runner.uuid,
            "workflow_id": runner.workflow_id,
            "workflow": self._workflow_to_doc(runner.workflow),
            "parameters": [asdict(p) for p in runner.parameters],
            "step_id": runner.step_id,
            "user": asdict(runner.user) if runner.user else None,
            "start_time": runner.start_time,
            "end_time": runner.end_time,
            "duration": runner.duration,
            "retain": runner.retain,
            "state": runner.state,
        }

    def _doc_to_runner(self, doc: dict) -> RunnerDefinition:
        """Convert MongoDB document to RunnerDefinition."""
        from .entities import UserDefinition

        workflow = self._doc_to_workflow(doc["workflow"])
        user = None
        if doc.get("user"):
            user = UserDefinition(**doc["user"])

        return RunnerDefinition(
            uuid=doc["uuid"],
            workflow_id=doc["workflow_id"],
            workflow=workflow,
            parameters=[Parameter(**p) for p in doc.get("parameters", [])],
            step_id=doc.get("step_id"),
            user=user,
            start_time=doc.get("start_time", 0),
            end_time=doc.get("end_time", 0),
            duration=doc.get("duration", 0),
            retain=doc.get("retain", 0),
            state=doc.get("state", "created"),
        )

    def _workflow_to_doc(self, workflow: WorkflowDefinition) -> dict:
        """Convert WorkflowDefinition to MongoDB document."""
        return {
            "uuid": workflow.uuid,
            "name": workflow.name,
            "namespace_id": workflow.namespace_id,
            "facet_id": workflow.facet_id,
            "flow_id": workflow.flow_id,
            "starting_step": workflow.starting_step,
            "version": workflow.version,
            "metadata": asdict(workflow.metadata) if workflow.metadata else None,
            "documentation": workflow.documentation,
            "date": workflow.date,
        }

    def _doc_to_workflow(self, doc: dict) -> WorkflowDefinition:
        """Convert MongoDB document to WorkflowDefinition."""
        from .entities import WorkflowMetaData

        metadata = None
        if doc.get("metadata"):
            metadata = WorkflowMetaData(**doc["metadata"])

        return WorkflowDefinition(
            uuid=doc["uuid"],
            name=doc["name"],
            namespace_id=doc["namespace_id"],
            facet_id=doc["facet_id"],
            flow_id=doc["flow_id"],
            starting_step=doc["starting_step"],
            version=doc["version"],
            metadata=metadata,
            documentation=doc.get("documentation"),
            date=doc.get("date", 0),
        )

    def _task_to_doc(self, task: TaskDefinition) -> dict:
        """Convert TaskDefinition to MongoDB document."""
        return {
            "uuid": task.uuid,
            "name": task.name,
            "runner_id": task.runner_id,
            "workflow_id": task.workflow_id,
            "flow_id": task.flow_id,
            "step_id": task.step_id,
            "state": task.state,
            "created": task.created,
            "updated": task.updated,
            "error": task.error,
            "task_list_name": task.task_list_name,
            "data_type": task.data_type,
            "data": task.data,
        }

    def _doc_to_task(self, doc: dict) -> TaskDefinition:
        """Convert MongoDB document to TaskDefinition."""
        return TaskDefinition(
            uuid=doc["uuid"],
            name=doc["name"],
            runner_id=doc["runner_id"],
            workflow_id=doc["workflow_id"],
            flow_id=doc["flow_id"],
            step_id=doc["step_id"],
            state=doc.get("state", "pending"),
            created=doc.get("created", 0),
            updated=doc.get("updated", 0),
            error=doc.get("error"),
            task_list_name=doc.get("task_list_name", "default"),
            data_type=doc.get("data_type", ""),
            data=doc.get("data"),
        )

    def _log_to_doc(self, log: LogDefinition) -> dict:
        """Convert LogDefinition to MongoDB document."""
        return {
            "uuid": log.uuid,
            "order": log.order,
            "runner_id": log.runner_id,
            "step_id": log.step_id,
            "object_id": log.object_id,
            "object_type": log.object_type,
            "note_originator": log.note_originator,
            "note_type": log.note_type,
            "note_importance": log.note_importance,
            "message": log.message,
            "state": log.state,
            "line": log.line,
            "file": log.file,
            "details": log.details,
            "time": log.time,
        }

    def _doc_to_log(self, doc: dict) -> LogDefinition:
        """Convert MongoDB document to LogDefinition."""
        return LogDefinition(
            uuid=doc["uuid"],
            order=doc["order"],
            runner_id=doc["runner_id"],
            step_id=doc.get("step_id"),
            object_id=doc.get("object_id", ""),
            object_type=doc.get("object_type", ""),
            note_originator=doc.get("note_originator", "workflow"),
            note_type=doc.get("note_type", "info"),
            note_importance=doc.get("note_importance", 5),
            message=doc.get("message", ""),
            state=doc.get("state", ""),
            line=doc.get("line", 0),
            file=doc.get("file", ""),
            details=doc.get("details", {}),
            time=doc.get("time", 0),
        )

    def _server_to_doc(self, server: ServerDefinition) -> dict:
        """Convert ServerDefinition to MongoDB document."""
        return {
            "uuid": server.uuid,
            "server_group": server.server_group,
            "service_name": server.service_name,
            "server_name": server.server_name,
            "server_ips": server.server_ips,
            "start_time": server.start_time,
            "ping_time": server.ping_time,
            "topics": server.topics,
            "handlers": server.handlers,
            "handled": [asdict(h) for h in server.handled],
            "state": server.state,
            "manager": server.manager,
            "error": server.error,
        }

    def _doc_to_server(self, doc: dict) -> ServerDefinition:
        """Convert MongoDB document to ServerDefinition."""
        return ServerDefinition(
            uuid=doc["uuid"],
            server_group=doc["server_group"],
            service_name=doc["service_name"],
            server_name=doc["server_name"],
            server_ips=doc.get("server_ips", []),
            start_time=doc.get("start_time", 0),
            ping_time=doc.get("ping_time", 0),
            topics=doc.get("topics", []),
            handlers=doc.get("handlers", []),
            handled=[HandledCount(**h) for h in doc.get("handled", [])],
            state=doc.get("state", "startup"),
            manager=doc.get("manager", ""),
            error=doc.get("error"),
        )

    def _lock_to_doc(self, lock: LockDefinition) -> dict:
        """Convert LockDefinition to MongoDB document."""
        return {
            "key": lock.key,
            "acquired_at": lock.acquired_at,
            "expires_at": lock.expires_at,
            "meta": asdict(lock.meta) if lock.meta else None,
        }

    def _doc_to_lock(self, doc: dict) -> LockDefinition:
        """Convert MongoDB document to LockDefinition."""
        meta = None
        if doc.get("meta"):
            meta = LockMetaData(**doc["meta"])

        return LockDefinition(
            key=doc["key"],
            acquired_at=doc.get("acquired_at", 0),
            expires_at=doc.get("expires_at", 0),
            meta=meta,
        )

    def _flow_to_doc(self, flow: FlowDefinition) -> dict:
        """Convert FlowDefinition to MongoDB document."""
        return {
            "uuid": flow.uuid,
            "name": asdict(flow.name),
            "namespaces": [asdict(n) for n in flow.namespaces],
            "facets": [asdict(f) for f in flow.facets],
            "workflows": [self._workflow_to_doc(w) for w in flow.workflows],
            "mixins": [asdict(m) for m in flow.mixins],
            "blocks": [asdict(b) for b in flow.blocks],
            "statements": [asdict(s) for s in flow.statements],
            "arguments": [asdict(a) for a in flow.arguments],
            "references": [asdict(r) for r in flow.references],
            "script_code": [asdict(s) for s in flow.script_code],
            "file_artifacts": [asdict(f) for f in flow.file_artifacts],
            "jar_artifacts": [asdict(j) for j in flow.jar_artifacts],
            "resources": [asdict(r) for r in flow.resources],
            "text_sources": [asdict(t) for t in flow.text_sources],
            "inline": asdict(flow.inline) if flow.inline else None,
            "classification": asdict(flow.classification) if flow.classification else None,
            "publisher": asdict(flow.publisher) if flow.publisher else None,
            "ownership": asdict(flow.ownership) if flow.ownership else None,
            "compiled_sources": [asdict(s) for s in flow.compiled_sources],
        }

    def _doc_to_flow(self, doc: dict) -> FlowDefinition:
        """Convert MongoDB document to FlowDefinition."""
        from .entities import (
            BlockDefinition,
            Classifier,
            FacetDefinition,
            FileArtifact,
            InlineSource,
            JarArtifact,
            MixinDefinition,
            NamespaceDefinition,
            Ownership,
            ResourceSource,
            ScriptCode,
            SourceText,
            StatementArguments,
            StatementDefinition,
            StatementReferences,
            TextSource,
            UserDefinition,
        )

        name = FlowIdentity(**doc["name"])

        inline = None
        if doc.get("inline"):
            inline = InlineSource(**doc["inline"])

        classification = None
        if doc.get("classification"):
            classification = Classifier(**doc["classification"])

        publisher = None
        if doc.get("publisher"):
            publisher = UserDefinition(**doc["publisher"])

        ownership = None
        if doc.get("ownership"):
            ownership = Ownership(**doc["ownership"])

        return FlowDefinition(
            uuid=doc["uuid"],
            name=name,
            namespaces=[NamespaceDefinition(**n) for n in doc.get("namespaces", [])],
            facets=[FacetDefinition(**f) for f in doc.get("facets", [])],
            workflows=[self._doc_to_workflow(w) for w in doc.get("workflows", [])],
            mixins=[MixinDefinition(**m) for m in doc.get("mixins", [])],
            blocks=[BlockDefinition(**b) for b in doc.get("blocks", [])],
            statements=[StatementDefinition(**s) for s in doc.get("statements", [])],
            arguments=[StatementArguments(**a) for a in doc.get("arguments", [])],
            references=[StatementReferences(**r) for r in doc.get("references", [])],
            script_code=[ScriptCode(**s) for s in doc.get("script_code", [])],
            file_artifacts=[FileArtifact(**f) for f in doc.get("file_artifacts", [])],
            jar_artifacts=[JarArtifact(**j) for j in doc.get("jar_artifacts", [])],
            resources=[ResourceSource(**r) for r in doc.get("resources", [])],
            text_sources=[TextSource(**t) for t in doc.get("text_sources", [])],
            inline=inline,
            classification=classification,
            publisher=publisher,
            ownership=ownership,
            compiled_sources=[SourceText(**s) for s in doc.get("compiled_sources", [])],
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def close(self) -> None:
        """Close the MongoDB connection."""
        self._client.close()

    def drop_database(self) -> None:
        """Drop the entire database. Use with caution!"""
        self._client.drop_database(self._db.name)
