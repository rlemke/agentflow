
# AFL Agent SDK Specification

This document defines how external services (**AFL Agents**) interact with
the AgentFlow runtime to process event facet tasks. It covers the three
agent execution models, the task lifecycle, and the public API contract.

This specification is the authoritative reference for agent implementors.
Cross-references to `spec/30_runtime.md` and `spec/50_event_system.md`
are provided where relevant.

---

## 1. Introduction

An **AFL Agent** is a service that:

1. accepts event tasks from the AgentFlow task queue,
2. performs the required action (computation, API call, LLM inference, etc.),
3. updates the originating step with a result or error, and
4. signals the runtime to continue evaluation.

AgentFlow provides three execution models for building agents:

| Model | Use case | Transport |
|-------|----------|-----------|
| **AgentPoller** | Standalone agent services | Task queue polling |
| **RunnerService** | Distributed orchestration | Task queue + step polling + HTTP |
| **ClaudeAgentRunner** | LLM-driven execution | In-process synchronous |

All three models share the same underlying primitives: `claim_task()`,
`continue_step()`, `fail_step()`, and `resume()`.

---

## 2. Agent Lifecycle

### 2.1 Task Creation

When the evaluator processes a step that invokes an **event facet**, the
`EventTransmitHandler` creates a `TaskDefinition` in the task queue.
This occurs at the `EVENT_TRANSMIT` state (see `spec/30_runtime.md` §8.1
and `spec/50_event_system.md`).

The task is committed atomically alongside step and event changes via
`IterationChanges.created_tasks`.

> **Note:** Tasks and events are distinct concepts. An event models the
> *domain lifecycle* of the external work (what, why, outcome). A task
> models the *distribution mechanism* (claiming, routing, locking). Both
> are created together at `EVENT_TRANSMIT` but consumed by different
> subsystems. See `spec/50_event_system.md` §9 for the full explanation.

### 2.2 Poll → Claim → Dispatch → Continue → Resume

The agent lifecycle follows a five-phase cycle:

```
                    ┌──────────────────────────────────────────┐
                    │            AgentFlow Runtime              │
                    │                                          │
                    │  Evaluator executes workflow              │
                    │       │                                   │
                    │       ▼                                   │
                    │  Step reaches EVENT_TRANSMIT              │
                    │       │                                   │
                    │       ▼                                   │
                    │  EventTransmitHandler creates task        │
                    │  (TaskState.PENDING)                      │
                    │       │                                   │
                    └───────┼──────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                       AFL Agent                               │
│                                                               │
│  1. POLL    — query task queue for matching tasks             │
│       │                                                       │
│       ▼                                                       │
│  2. CLAIM   — claim_task() atomically: PENDING → RUNNING     │
│       │                                                       │
│       ▼                                                       │
│  3. DISPATCH — invoke registered callback with task payload   │
│       │                                                       │
│       ├─── success ──┐                                        │
│       │              ▼                                        │
│       │     continue_step(step_id, result)                    │
│       │     mark task COMPLETED                               │
│       │                                                       │
│       └─── failure ──┐                                        │
│                      ▼                                        │
│              fail_step(step_id, error_message)                │
│              mark task FAILED                                 │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                       AgentFlow Runtime                       │
│                                                               │
│  4. CONTINUE — step unblocked, attributes merged              │
│       │                                                       │
│       ▼                                                       │
│  5. RESUME  — evaluator resumes iteration loop                │
│              (runs to next fixed point or completion)          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 2.3 Execution Returns PAUSED

When the evaluator reaches a fixed point with one or more steps blocked
at `EVENT_TRANSMIT`, `execute()` returns an `ExecutionResult` with
`status=PAUSED`. The workflow remains in the persistence store and MAY
be resumed after the agent processes the event.

---

## 3. Task Queue Contract

### 3.1 TaskDefinition

A task is represented by the `TaskDefinition` dataclass
(`afl/runtime/entities.py`):

```python
@dataclass
class TaskDefinition:
    uuid: str
    name: str                          # Qualified facet name (e.g. "ns.CountDocs")
    runner_id: str                     # ID of the runner that created this task
    workflow_id: str
    flow_id: str
    step_id: str
    state: str = TaskState.PENDING
    created: int = 0                   # Creation timestamp (ms since epoch)
    updated: int = 0                   # Last update timestamp (ms since epoch)
    error: Optional[dict] = None
    task_list_name: str = "default"
    data_type: str = ""
    data: Optional[dict] = None        # Payload (step params, facet info)
```

### 3.2 TaskState Transitions

```
                ┌─────────┐
                │ PENDING │
                └────┬────┘
                     │  claim_task()
                     ▼
                ┌─────────┐
                │ RUNNING │
                └────┬────┘
                     │
            ┌────────┼────────┐
            ▼                 ▼
      ┌───────────┐    ┌──────────┐
      │ COMPLETED │    │  FAILED  │
      └───────────┘    └──────────┘
```

Valid states (from `TaskState`):

| Constant | Value | Description |
|----------|-------|-------------|
| `PENDING` | `"pending"` | Task created, awaiting claim |
| `RUNNING` | `"running"` | Claimed by an agent, processing |
| `COMPLETED` | `"completed"` | Successfully processed |
| `FAILED` | `"failed"` | Processing failed |
| `IGNORED` | `"ignored"` | Skipped (no matching handler) |
| `CANCELED` | `"canceled"` | Canceled by operator |

### 3.3 Atomic Claim Semantics

The `claim_task()` method on `PersistenceAPI` MUST provide **atomic
claim semantics**:

```python
def claim_task(
    self,
    task_names: list[str],
    task_list: str = "default",
) -> Optional[TaskDefinition]
```

- The implementation MUST atomically transition exactly one matching task
  from `PENDING` to `RUNNING` and return it.
- If no matching task exists, it MUST return `None`.
- Concurrent callers MUST NOT receive the same task.
- The MemoryStore implementation uses `threading.Lock` for atomicity.
- The MongoStore implementation uses `find_one_and_update()` with a
  compound index for atomicity.
- A partial unique index on `(step_id, state=running)` ensures at most
  one agent processes a given event step at any time.

### 3.4 Task Naming

Tasks are named using **qualified facet names** of the form
`"namespace.FacetName"` (e.g. `"billing.ProcessPayment"`).

When matching tasks to handlers:

1. The agent SHOULD first attempt an exact match on the qualified name.
2. If no exact match is found, the agent SHOULD attempt a **short-name
   fallback** — matching only the facet name portion after the last dot.

This allows handlers to be registered with either qualified names
(`"billing.ProcessPayment"`) or short names (`"ProcessPayment"`).

---

## 4. AgentPoller API

The `AgentPoller` class (`afl/runtime/agent_poller.py`) is a standalone
polling library for building AFL Agent services without the full
`RunnerService`.

### 4.1 AgentPollerConfig

```python
@dataclass
class AgentPollerConfig:
    service_name: str = "afl-agent"
    server_group: str = "default"
    server_name: str = ""              # Auto-populated with socket.gethostname()
    task_list: str = "default"
    poll_interval_ms: int = 2000
    max_concurrent: int = 5
    heartbeat_interval_ms: int = 10000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `service_name` | `str` | `"afl-agent"` | Identifies the agent type in server registry |
| `server_group` | `str` | `"default"` | Logical grouping of servers |
| `server_name` | `str` | hostname | Human-readable server name |
| `task_list` | `str` | `"default"` | Task list to poll |
| `poll_interval_ms` | `int` | `2000` | Milliseconds between poll cycles |
| `max_concurrent` | `int` | `5` | Maximum concurrent task processing |
| `heartbeat_interval_ms` | `int` | `10000` | Milliseconds between heartbeat pings |

### 4.2 Constructor

```python
def __init__(
    self,
    persistence: PersistenceAPI,
    evaluator: Evaluator,
    config: Optional[AgentPollerConfig] = None,
) -> None
```

The `AgentPoller` requires a `PersistenceAPI` for task queue access and
an `Evaluator` for `continue_step()` / `fail_step()` / `resume()`.

### 4.3 register()

```python
def register(self, facet_name: str, callback: Callable[[dict], dict]) -> None
```

Registers a handler callback for a given facet name. The callback
signature MUST be:

```python
Callable[[dict], dict]
```

- **Input**: a `dict` containing the task payload (step parameters and
  facet metadata from `task.data`).
- **Output**: a `dict` containing the result to merge into the step's
  return attributes via `continue_step()`.

A handler MAY be registered with either a qualified name
(`"ns.FacetName"`) or a short name (`"FacetName"`). Short-name fallback
applies during dispatch (see §3.4).

### 4.4 registered_names()

```python
def registered_names(self) -> list[str]
```

Returns the list of all registered facet names. Used to build the
`task_names` list for `claim_task()` and the `handlers` list in the
server registration record.

### 4.5 start() / stop()

```python
def start(self) -> None
def stop(self) -> None
```

`start()` enters a **blocking poll loop** that:

1. Registers a `ServerDefinition` with the persistence store.
2. Starts a background heartbeat thread.
3. Repeatedly calls `claim_task()` with the registered names.
4. Dispatches claimed tasks to the matching callback.
5. On success: calls `continue_step()`, `resume()`, marks task `COMPLETED`.
6. On failure: calls `fail_step()`, marks task `FAILED`.

`stop()` signals the poll loop to exit gracefully. The server record
is updated to `ServerState.SHUTDOWN`.

### 4.6 poll_once()

```python
def poll_once(self) -> int
```

Executes a **single synchronous poll cycle** without starting the full
loop. Returns the number of tasks dispatched. This method is intended
for testing and MUST NOT start background threads or the heartbeat loop.

### 4.7 cache_workflow_ast()

```python
def cache_workflow_ast(self, workflow_id: str, ast: dict) -> None
```

Pre-caches a workflow AST so that `resume()` can retrieve it without
a database lookup. This is required when the agent needs to resume a
workflow after processing an event — the AST is needed for the evaluator
to continue from the paused state.

### 4.8 Properties

| Property | Type | Description |
|----------|------|-------------|
| `server_id` | `str` | Unique identifier for this agent instance |
| `is_running` | `bool` | Whether the poll loop is currently active |

---

## 5. Server Registration

### 5.1 ServerDefinition

Agents register themselves with the runtime via a `ServerDefinition`
(`afl/runtime/entities.py`):

```python
@dataclass
class ServerDefinition:
    uuid: str
    server_group: str
    service_name: str
    server_name: str
    server_ips: list[str] = field(default_factory=list)
    start_time: int = 0               # Server start timestamp (ms)
    ping_time: int = 0                # Last heartbeat timestamp (ms)
    topics: list[str] = field(default_factory=list)
    handlers: list[str] = field(default_factory=list)
    handled: list[HandledCount] = field(default_factory=list)
    state: str = ServerState.STARTUP
    manager: str = ""
    error: Optional[dict] = None
```

The `handlers` field MUST contain the list of facet names this agent
can process. The `topics` field MAY contain a subset for filtering.

### 5.2 ServerState Transitions

```
  STARTUP  ──→  RUNNING  ──→  SHUTDOWN
                   │
                   └──→  ERROR
```

| Constant | Value | Description |
|----------|-------|-------------|
| `STARTUP` | `"startup"` | Server registered, initializing |
| `RUNNING` | `"running"` | Actively polling and processing |
| `SHUTDOWN` | `"shutdown"` | Graceful shutdown in progress or complete |
| `ERROR` | `"error"` | Unrecoverable error |

### 5.3 Lifecycle

1. **Registration**: at `start()`, the agent creates a `ServerDefinition`
   with `state=STARTUP`, saves it via persistence, then transitions to
   `RUNNING`.
2. **Heartbeat**: a background thread updates `ping_time` at the
   configured `heartbeat_interval_ms`. This allows the dashboard and
   other services to detect stale servers.
3. **Deregistration**: at `stop()`, the agent updates the server record
   to `state=SHUTDOWN`.

---

## 6. Error Handling

### 6.1 Callback Exceptions

If a registered callback raises an exception during dispatch:

1. The agent MUST call `fail_step(step_id, error_message)` on the
   evaluator.
2. The agent MUST mark the task as `TaskState.FAILED`.
3. The agent MUST NOT re-raise the exception to the poll loop.

There are **no implicit retries**. A failed task remains in `FAILED`
state until explicitly retried by an operator (e.g. via the dashboard
retry action).

### 6.2 Evaluator.fail_step()

```python
def fail_step(self, step_id: StepId, error_message: str) -> None
```

This method:

1. Retrieves the step from persistence.
2. Verifies the step is at `EVENT_TRANSMIT` state.
3. Calls `mark_error()` on the step with the error message.
4. Saves the step directly to persistence.

The step transitions to `STATEMENT_ERROR`, which the evaluator treats
as a terminal error for that step.

### 6.3 Evaluator.continue_step()

```python
def continue_step(self, step_id: StepId, result: Optional[dict] = None) -> None
```

This method:

1. Retrieves the step from persistence.
2. Verifies the step is at `EVENT_TRANSMIT` state.
3. Merges `result` into the step's return attributes.
4. Calls `request_state_change(True)` on the step's transition.
5. Saves the step directly to persistence.

### 6.4 Evaluator.resume()

```python
def resume(
    self,
    workflow_id_val: WorkflowId,
    workflow_ast: dict,
    program_ast: Optional[dict] = None,
    inputs: Optional[dict] = None,
) -> ExecutionResult
```

Resumes a paused workflow from its current state. The evaluator
re-enters the iteration loop and runs until the next fixed point or
completion.

---

## 7. RunnerService

The `RunnerService` (`afl/runtime/runner/service.py`) is a superset of
the `AgentPoller` that adds distributed coordination capabilities.

### 7.1 RunnerConfig

```python
@dataclass
class RunnerConfig:
    server_group: str = "default"
    service_name: str = "afl-runner"
    server_name: str = ""              # Auto-populated with socket.gethostname()
    topics: list[str] = field(default_factory=list)
    task_list: str = "default"
    poll_interval_ms: int = 2000
    heartbeat_interval_ms: int = 10000
    lock_duration_ms: int = 60000
    lock_extend_interval_ms: int = 20000
    max_concurrent: int = 5
    shutdown_timeout_ms: int = 30000
    http_port: int = 8080
    http_max_port_attempts: int = 20
```

### 7.2 Capabilities Beyond AgentPoller

| Capability | AgentPoller | RunnerService |
|------------|-------------|---------------|
| Task queue polling | Yes | Yes |
| Handler registration | `register()` | `ToolRegistry` |
| Distributed locking | No | Yes (`acquire_lock` / `extend_lock` / `release_lock`) |
| HTTP status server | No | Yes (`/health`, `/status`) |
| Non-event tasks (`afl:execute`) | No | Yes |
| ThreadPoolExecutor concurrency | No | Yes |
| Per-work-item lock extension | No | Yes (background threads) |
| Signal handling (SIGTERM/SIGINT) | No | Yes |
| Graceful shutdown timeout | No | Yes (`shutdown_timeout_ms`) |

### 7.3 ToolRegistry

The `RunnerService` uses a `ToolRegistry` for handler dispatch instead
of direct callback registration. The registry supports:

- Registration by qualified facet name.
- Short-name fallback matching.
- A default handler fallback for unmatched tasks.

### 7.4 Distributed Locking

The `RunnerService` acquires a distributed lock before processing each
work item. A background thread extends the lock at `lock_extend_interval_ms`
while processing is in progress. This prevents other runner instances
from claiming the same work.

Lock methods on `PersistenceAPI`:

```python
def acquire_lock(self, key: str, duration_ms: int, meta: Optional[LockMetaData] = None) -> bool
def extend_lock(self, key: str, duration_ms: int) -> bool
def release_lock(self, key: str) -> bool
```

### 7.5 HTTP Status Server

The `RunnerService` starts an embedded HTTP server with two endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Returns `200 OK` if the service is running |
| `/status` | GET | Returns JSON with server ID, state, uptime, and statistics |

The server auto-probes ports starting from `http_port`, incrementing up
to `http_max_port_attempts` times if the port is in use.

---

## 8. ClaudeAgentRunner

The `ClaudeAgentRunner` is a synchronous in-process execution model
designed for LLM-driven workflow processing.

### 8.1 Characteristics

| Aspect | Behavior |
|--------|----------|
| Execution model | Synchronous, in-process |
| Handler dispatch | `ToolRegistry` + Anthropic Claude API |
| Task queue | Not used |
| Server registration | Not used |
| Persistence | Required (for step/event storage) |
| Concurrency | Single-threaded |

### 8.2 Execution Flow

1. The `ClaudeAgentRunner` receives a workflow AST and inputs.
2. The evaluator executes until it reaches `EVENT_TRANSMIT`.
3. The runner extracts the event payload and sends it to the Claude API.
4. The Claude response is passed to `continue_step()`.
5. The evaluator resumes and continues to the next event or completion.

Unlike `AgentPoller` and `RunnerService`, the `ClaudeAgentRunner` does
not poll a task queue. It drives execution directly through the evaluator
in a tight loop.

---

## 9. Concurrency Model

The `AgentPoller` and `RunnerService` process multiple event tasks
concurrently. This section defines how in-memory state is kept isolated
between concurrent executions.

### 9.1 Design Principle

The `Evaluator`, `AgentPoller`, and `RunnerService` are **shared
instances**, but all mutable execution state is **created per-invocation**.
The shared `PersistenceAPI` acts as the sole coordination point, with
atomicity guarantees enforced at the storage layer.

```
┌──────────────────────────────────────────────────────┐
│              Shared (long-lived)                      │
│                                                      │
│  Evaluator   AgentPoller/RunnerService   Persistence │
│     │               │                       │        │
│     │   ┌───────────┼───────────┐           │        │
│     │   │  Thread A  │  Thread B │           │        │
│     │   │           │           │           │        │
│     │   │  ┌────────┴─┐  ┌─────┴──────┐    │        │
│     │   │  │ Context A │  │ Context B  │    │        │
│     │   │  │ Changes A │  │ Changes B  │    │        │
│     │   │  │ Step copy │  │ Step copy  │    │        │
│     │   │  └──────────┘  └────────────┘    │        │
│     │   └───────────────────────────────┘   │        │
│     │                                       │        │
│     └───────────── read/write ──────────────┘        │
└──────────────────────────────────────────────────────┘
```

### 9.2 Per-Invocation ExecutionContext

Each call to `execute()` or `resume()` MUST create a **fresh
`ExecutionContext`** with a new `IterationChanges` instance:

```python
context = ExecutionContext(
    persistence=self.persistence,
    telemetry=self.telemetry,
    changes=IterationChanges(),   # fresh per invocation
    workflow_id=wf_id,
    workflow_ast=workflow_ast,
    ...
)
```

The `ExecutionContext` contains per-invocation caches
(`_block_graphs`, `_completed_step_cache`) that are private to each
execution. Concurrent threads calling `resume()` for different events
operate on entirely separate context objects.

### 9.3 Deep-Copy Persistence Pattern

The `MemoryStore` MUST return a **deep copy** of every `StepDefinition`
on read and MUST clone before storing on write:

```python
def get_step(self, step_id: StepId) -> Optional[StepDefinition]:
    step = self._steps.get(step_id)
    if step:
        return step.clone()    # copy.deepcopy
    return None
```

This ensures that each thread operates on its own copy of step and
event data. Concurrent modifications to the same step in different
threads do not collide in memory.

The `MongoStore` achieves the same isolation naturally — each read
deserializes a fresh object from the database document.

### 9.4 Atomic Task Claiming

The `claim_task()` method MUST guarantee that exactly one caller
receives a given task:

- **MemoryStore**: uses a `threading.Lock` around the
  `PENDING → RUNNING` transition.
- **MongoStore**: uses `find_one_and_update()` with a state filter,
  which is atomic at the database level.
- A partial unique index on `(step_id, state=running)` ensures at most
  one agent processes a given event step at any time.

### 9.5 Distributed Locking (RunnerService)

The `RunnerService` acquires a distributed lock per work item before
processing. A background thread extends the lock at
`lock_extend_interval_ms` for the duration of processing. This prevents
other runner instances from claiming the same work concurrently.

The `AgentPoller` does not use distributed locks. It relies on the
atomic `claim_task()` semantics to prevent duplicate processing.

### 9.6 Isolation Guarantees

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| `ExecutionContext` | Fresh instance per `execute()` / `resume()` | Per-invocation |
| `IterationChanges` | Fresh instance per context | Per-invocation |
| `StepDefinition` reads | Deep copy (`clone()`) in MemoryStore; deserialization in MongoStore | Per-read |
| `StepDefinition` writes | Clone before store (MemoryStore); serialize to document (MongoStore) | Per-write |
| Task claiming | `threading.Lock` (memory) / `find_one_and_update` (MongoDB) | Global |
| Work-item locking | `acquire_lock()` / `extend_lock()` (RunnerService only) | Per-work-item |

### 9.7 Known Benign Races

The following shared state is accessed without synchronization. These
races are benign and do not affect correctness:

- **AST cache** (`_ast_cache` in `AgentPoller` and `RunnerService`):
  concurrent threads may populate the same key simultaneously. The
  worst case is duplicate loading of an immutable AST — no corruption
  occurs.
- **Handled-count statistics** (`_handled_counts` in `RunnerService`):
  counter increments are not atomic, so counts may drift slightly under
  contention. These are cosmetic statistics only.

---

## 10. Key Files Reference

| File | Description |
|------|-------------|
| `afl/runtime/agent_poller.py` | `AgentPoller` class and `AgentPollerConfig` |
| `afl/runtime/runner/service.py` | `RunnerService` class and `RunnerConfig` |
| `afl/runtime/entities.py` | `TaskDefinition`, `TaskState`, `ServerDefinition`, `ServerState` |
| `afl/runtime/persistence.py` | `PersistenceAPI` protocol (including `claim_task()`) |
| `afl/runtime/evaluator.py` | `ExecutionContext`, `continue_step()`, `fail_step()`, `resume()` |
| `afl/runtime/events.py` | `EventManager`, `EventDispatcher`, event lifecycle |
| `afl/runtime/memory_store.py` | In-memory `PersistenceAPI` with deep-copy isolation |
| `afl/runtime/mongo_store.py` | MongoDB `PersistenceAPI` with atomic operations |
| `afl/runtime/runner/__main__.py` | CLI entry point: `python -m afl.runtime.runner` |
| `afl/runtime/handlers/initialization.py` | `EventTransmitHandler` (task creation) |

---

## 11. Comparison Matrix

| Feature | AgentPoller | RunnerService | ClaudeAgentRunner |
|---------|-------------|---------------|-------------------|
| Task queue polling | Yes | Yes | No |
| Step state polling | No | Yes | No |
| Distributed locking | No | Yes | No |
| HTTP status server | No | Yes | No |
| Server registration | Yes | Yes | No |
| Heartbeat | Yes | Yes | No |
| Handler model | `register()` callback | `ToolRegistry` | `ToolRegistry` + Claude API |
| Concurrency | Sequential (`poll_once`) | `ThreadPoolExecutor` | Single-threaded |
| Signal handling | No | Yes (SIGTERM/SIGINT) | No |
| Non-event tasks | No | Yes | No |
| AST caching | `cache_workflow_ast()` | `cache_workflow_ast()` | In-process |
| Short-name fallback | Yes | Yes | Yes |
| Error → `fail_step()` | Yes | Yes | Yes |
| Intended use | Standalone agent services | Production orchestration | LLM-driven execution |
