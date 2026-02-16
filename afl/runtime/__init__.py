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

"""AFL runtime package.

Executes compiled AFL workflows through iterative evaluation.
"""

from .agent import ClaudeAgentRunner, ToolDefinition, ToolRegistry
from .agent_poller import AgentPoller, AgentPollerConfig
from .block import BlockAnalysis, StatementDefinition, StepAnalysis

# DAO protocols
from .dao import (
    DataServices,
    EventDefinitionDAO,
    FlowDefinitionDAO,
    KeyLockDAO,
    LogDefinitionDAO,
    RunnerDefinitionDAO,
    ServerDefinitionDAO,
    StepDefinitionDAO,
    TaskDefinitionDAO,
    WorkflowDefinitionDAO,
)
from .dependency import DependencyGraph
from .dispatcher import (
    CompositeDispatcher,
    HandlerDispatcher,
    InMemoryDispatcher,
    RegistryDispatcher,
    ToolRegistryDispatcher,
)


# Entity definitions
from .entities import (
    BlockDefinition,
    Classifier,
    FacetDefinition,
    FileArtifact,
    FlowDefinition,
    FlowIdentity,
    HandledCount,
    HandlerRegistration,
    InlineSource,
    JarArtifact,
    LockDefinition,
    LockMetaData,
    LogDefinition,
    MixinDefinition,
    # Flow types
    NamespaceDefinition,
    NoteImportance,
    NoteOriginator,
    NoteType,
    Ownership,
    # Supporting types
    Parameter,
    ResourceSource,
    RunnerDefinition,
    RunnerState,
    ScriptCode,
    ServerDefinition,
    ServerState,
    SourceText,
    StatementArguments,
    StatementReferences,
    TaskDefinition,
    TaskState,
    TextSource,
    UserDefinition,
    # Workflow and execution
    WorkflowDefinition,
    WorkflowMetaData,
)
from .entities import (
    StatementDefinition as EntityStatementDefinition,
)
from .errors import (
    BlockNotFoundError,
    ConcurrencyError,
    DependencyNotSatisfiedError,
    EvaluationError,
    EventError,
    InvalidStepStateError,
    InvalidTransitionError,
    ReferenceError,
    RuntimeError,
    StepNotFoundError,
    VersionMismatchError,
)
from .evaluator import Evaluator, ExecutionContext, ExecutionResult, ExecutionStatus
from .events import EventDispatcher, EventManager, LocalEventHandler
from .expression import EvaluationContext, ExpressionEvaluator, evaluate_args
from .memory_store import MemoryStore
from .persistence import EventDefinition, IterationChanges, PersistenceAPI
from .maven_runner import MavenArtifactRunner, MavenRunnerConfig
from .registry_runner import RegistryRunner, RegistryRunnerConfig
from .runner import RunnerConfig, RunnerService
from .states import (
    BLOCK_TRANSITIONS,
    EVENT_TRANSITIONS,
    SCHEMA_TRANSITIONS,
    STEP_TRANSITIONS,
    YIELD_TRANSITIONS,
    EventState,
    StepState,
    get_next_state,
    select_transitions,
)
from .step import StepDefinition, StepTransition
from .telemetry import Telemetry, TelemetryEvent
from .types import (
    AttributeValue,
    BlockId,
    EventId,
    FacetAttributes,
    ObjectType,
    StatementId,
    StepId,
    VersionInfo,
    WorkflowId,
    block_id,
    event_id,
    generate_id,
    step_id,
    workflow_id,
)

__all__ = [
    # Types
    "StepId",
    "BlockId",
    "EventId",
    "WorkflowId",
    "StatementId",
    "ObjectType",
    "AttributeValue",
    "FacetAttributes",
    "VersionInfo",
    "generate_id",
    "step_id",
    "block_id",
    "event_id",
    "workflow_id",
    # States
    "StepState",
    "EventState",
    "STEP_TRANSITIONS",
    "BLOCK_TRANSITIONS",
    "YIELD_TRANSITIONS",
    "SCHEMA_TRANSITIONS",
    "EVENT_TRANSITIONS",
    "get_next_state",
    "select_transitions",
    # Step
    "StepDefinition",
    "StepTransition",
    # Persistence
    "PersistenceAPI",
    "IterationChanges",
    "EventDefinition",
    "MemoryStore",
    # Block
    "StatementDefinition",
    "StepAnalysis",
    "BlockAnalysis",
    # Dependency
    "DependencyGraph",
    # Expression
    "ExpressionEvaluator",
    "EvaluationContext",
    "evaluate_args",
    # Evaluator
    "Evaluator",
    "ExecutionContext",
    "ExecutionResult",
    "ExecutionStatus",
    # Telemetry
    "Telemetry",
    "TelemetryEvent",
    # Events
    "EventManager",
    "EventDispatcher",
    "LocalEventHandler",
    # Agent
    "ClaudeAgentRunner",
    "ToolRegistry",
    "ToolDefinition",
    # Runner
    "RunnerService",
    "RunnerConfig",
    # Agent Poller
    "AgentPoller",
    "AgentPollerConfig",
    # Registry Runner
    "RegistryRunner",
    "RegistryRunnerConfig",
    "HandlerRegistration",
    # Maven Artifact Runner
    "MavenArtifactRunner",
    "MavenRunnerConfig",
    # Dispatchers
    "HandlerDispatcher",
    "RegistryDispatcher",
    "InMemoryDispatcher",
    "ToolRegistryDispatcher",
    "CompositeDispatcher",
    # Errors
    "RuntimeError",
    "InvalidStepStateError",
    "StepNotFoundError",
    "BlockNotFoundError",
    "DependencyNotSatisfiedError",
    "EvaluationError",
    "ReferenceError",
    "InvalidTransitionError",
    "ConcurrencyError",
    "EventError",
    "VersionMismatchError",
    # Entity types
    "Parameter",
    "UserDefinition",
    "Ownership",
    "Classifier",
    "SourceText",
    "InlineSource",
    "FileArtifact",
    "JarArtifact",
    "ResourceSource",
    "TextSource",
    "ScriptCode",
    "WorkflowMetaData",
    "NamespaceDefinition",
    "FacetDefinition",
    "MixinDefinition",
    "BlockDefinition",
    "EntityStatementDefinition",
    "StatementArguments",
    "StatementReferences",
    "FlowIdentity",
    "FlowDefinition",
    "WorkflowDefinition",
    "RunnerDefinition",
    "RunnerState",
    "TaskDefinition",
    "TaskState",
    "LogDefinition",
    "NoteType",
    "NoteOriginator",
    "NoteImportance",
    "ServerDefinition",
    "ServerState",
    "HandledCount",
    "LockDefinition",
    "LockMetaData",
    # DAO protocols
    "FlowDefinitionDAO",
    "WorkflowDefinitionDAO",
    "RunnerDefinitionDAO",
    "StepDefinitionDAO",
    "EventDefinitionDAO",
    "TaskDefinitionDAO",
    "LogDefinitionDAO",
    "ServerDefinitionDAO",
    "KeyLockDAO",
    "DataServices",
]
