# AFL Event Framework Documentation

This document describes the event-driven architecture of the AFL workflow execution engine, including event lifecycle, handler registration, step locking, and event dispatch.

## Overview

AFL uses an event-driven pattern where workflow state transitions are driven by events. The Python runtime uses a **synchronous iterative evaluator** rather than async polling threads. The system ensures:

- **Ordered processing** - Events are processed in creation order
- **At-most-once delivery per step** - Only one event per step can be processed at a time
- **Handler-based dispatch** - Events are routed to registered handlers by event type
- **Atomic iteration commits** - Changes are accumulated in memory and committed at iteration boundaries

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Evaluator                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Iteration 1    │  │  Iteration 2    │  │  Iteration N    │             │
│  │  (process steps)│  │  (process steps)│  │  (fixed point)  │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                │                                            │
│                    ┌───────────▼───────────┐                               │
│                    │    EventManager       │                               │
│                    │  (lifecycle mgmt)     │                               │
│                    └───────────┬───────────┘                               │
│                                │                                            │
│                    ┌───────────▼───────────┐                               │
│                    │   LocalEventHandler   │                               │
│                    │  (handler registry)   │                               │
│                    └───────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PersistenceAPI                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      IterationChanges                               │   │
│  │  • Accumulated step creates/updates per iteration                  │   │
│  │  • Accumulated event creates/updates per iteration                 │   │
│  │  • Atomic commit at iteration boundary                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Event Lifecycle

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `EventManager` | `afl/runtime/events.py` | Event lifecycle management |
| `EventDispatcher` | `afl/runtime/events.py` | Dispatches events to external handlers |
| `LocalEventHandler` | `afl/runtime/events.py` | Local handler registry for testing |
| `PersistenceAPI` | `afl/runtime/persistence.py` | Event storage abstraction |
| `EventDefinition` | `afl/runtime/persistence.py` | Event data structure |

### Event Processing

The `EventManager` manages event lifecycle synchronously (`events.py:15-116`):

```python
@dataclass
class EventManager:
    """Manages event lifecycle."""
    persistence: PersistenceAPI

    def create_event(
        self,
        step_id: StepId,
        workflow_id: WorkflowId,
        event_type: str,
        payload: dict,
    ) -> EventDefinition:
        """Create a new event in CREATED state."""
        return EventDefinition(
            id=event_id(),
            step_id=step_id,
            workflow_id=workflow_id,
            state=EventState.CREATED,
            event_type=event_type,
            payload=payload,
        )

    def dispatch(self, event: EventDefinition) -> EventDefinition:
        """Dispatch an event for processing."""
        event.state = EventState.DISPATCHED
        return event

    def complete(self, event: EventDefinition, result: dict) -> EventDefinition:
        """Mark event as completed."""
        event.state = EventState.COMPLETED
        event.payload["result"] = result
        return event

    def error(self, event: EventDefinition, error: str) -> EventDefinition:
        """Mark event as errored."""
        event.state = EventState.ERROR
        event.payload["error"] = error
        return event
```

### Iterative Model

Unlike a polling-based system, the AFL runtime uses an iterative evaluator. Each iteration:

1. Processes all eligible steps through their state machines
2. Accumulates changes in `IterationChanges`
3. Commits all changes atomically at iteration boundary
4. Repeats until a fixed point is reached (no more changes)

Events are created during step execution (e.g., in `EventTransmitHandler`) and stored in `IterationChanges` for atomic commit.

---

## 2. Event Ordering

Events are processed based on creation order within the iterative evaluation loop.

### Event Definition

Events are stored as `EventDefinition` dataclasses (`persistence.py:76-87`):

```python
@dataclass
class EventDefinition:
    """Event definition for external dispatch."""
    id: EventId
    step_id: StepId
    workflow_id: WorkflowId
    state: str  # EventState constant
    event_type: str
    payload: dict = field(default_factory=dict)
```

### Event States

```python
class EventState:
    """Event state constants for event lifecycle."""

    CREATED = "event.Created"
    DISPATCHED = "event.Dispatched"
    PROCESSING = "event.Processing"
    COMPLETED = "event.Completed"
    ERROR = "event.Error"

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Check if event state is terminal."""
        return state in (cls.COMPLETED, cls.ERROR)
```

### Event Transitions

```python
EVENT_TRANSITIONS: dict[str, str] = {
    EventState.CREATED: EventState.DISPATCHED,
    EventState.DISPATCHED: EventState.PROCESSING,
    EventState.PROCESSING: EventState.COMPLETED,
}
```

Only events in non-terminal states are candidates for processing.

---

## 3. Handler Registration

### Local Event Handler

Handlers are registered with `LocalEventHandler` for testing (`events.py:149-181`):

```python
class LocalEventHandler:
    """Handles events locally for testing."""

    def __init__(self):
        self._handlers: dict[str, callable] = {}

    def register(self, event_type: str, handler: callable) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type] = handler

    def handle(self, event: EventDefinition) -> Optional[dict]:
        """Handle an event locally."""
        handler = self._handlers.get(event.event_type)
        if handler:
            return handler(event.payload)
        return None
```

### Event Dispatcher

The `EventDispatcher` provides the interface for external dispatch (`events.py:120-146`):

```python
@dataclass
class EventDispatcher:
    """Dispatches events to external handlers."""

    def dispatch(self, event: EventDefinition) -> None:
        """Dispatch an event to external system."""
        pass

    def poll_completed(self) -> list[tuple[EventId, dict]]:
        """Poll for completed events."""
        return []
```

### Handler Lookup

When an event is created during step execution, the handler is looked up by `event_type`:

```python
handler = self._handlers.get(event.event_type)
if handler:
    result = handler(event.payload)
```

---

## 4. Step Locking: One Event Per Step

The system ensures only one event per step can be processed at a time.

### In-Memory Model

In the synchronous evaluator, step locking is inherent — each step is processed sequentially within an iteration. The `IterationChanges` class tracks modifications:

```python
@dataclass
class IterationChanges:
    """Accumulated changes from a single iteration."""
    created_steps: list[StepDefinition] = field(default_factory=list)
    updated_steps: list[StepDefinition] = field(default_factory=list)
    created_events: list[EventDefinition] = field(default_factory=list)
    updated_events: list[EventDefinition] = field(default_factory=list)

    _created_ids: set[StepId] = field(default_factory=set)
    _updated_ids: dict[StepId, int] = field(default_factory=dict)

    def add_created_step(self, step: StepDefinition) -> None:
        """Record a newly created step (idempotent)."""
        if step.id not in self._created_ids:
            self._created_ids.add(step.id)
            self.created_steps.append(step)

    def add_updated_step(self, step: StepDefinition) -> None:
        """Record an updated step (replaces previous update for same ID)."""
        if step.id in self._updated_ids:
            idx = self._updated_ids[step.id]
            self.updated_steps[idx] = step
        else:
            self._updated_ids[step.id] = len(self.updated_steps)
            self.updated_steps.append(step)
```

### MongoDB Model

For production MongoDB deployments, step locking uses a **unique partial index**:

```json
{
  "key": {"stepId": 1},
  "name": "event_stepId_running_unique_index",
  "unique": true,
  "partialFilterExpression": {"state": "running"}
}
```

This index:
- Applies **only** to documents where `state = "running"`
- Enforces **uniqueness** on `stepId` within those documents
- Allows multiple pending events for the same step
- Prevents multiple running events for the same step

### Lock Lifecycle

```
┌─────────────┐     findOneAndUpdate      ┌─────────────┐
│   pending   │ ───────────────────────▶  │   running   │
└─────────────┘    (atomic transition)    └──────┬──────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        │                        │                        │
                        ▼                        ▼                        ▼
                 ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
                 │  completed  │         │    error    │         │   ignored   │
                 └─────────────┘         └─────────────┘         └─────────────┘
```

When processing completes, the event transitions from `running` to `completed`/`error`, releasing the "lock" and allowing the next pending event for that step to be claimed.

---

## 5. Event Dispatch

### Dispatch Flow

```
Step Execution (EventTransmitHandler)
      │
      ▼
┌─────────────────────────────────────────┐
│  EventTransmitHandler.process_state()   │
│  • Check if facet is EventFacetDecl     │
│  • Build payload from step attributes   │
│  • Create EventDefinition               │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│  IterationChanges.add_created_event()   │
│  • Store for atomic commit              │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│  PersistenceAPI.commit(changes)         │
│  • Persist all events atomically        │
└─────────────────────────────────────────┘
```

### EventTransmitHandler

**File:** `afl/runtime/handlers/completion.py`

The `EventTransmitHandler` creates events for event facets (`completion.py:18-60`):

```python
class EventTransmitHandler(StateHandler):
    """Handler for state.EventTransmit.

    Dispatches events to external agents for processing.
    """

    def process_state(self) -> StateChangeResult:
        """Transmit event to agent."""
        facet_def = self.context.get_facet_definition(self.step.facet_name)

        if facet_def and facet_def.get("type") == "EventFacetDecl":
            event = EventDefinition(
                id=event_id(),
                step_id=self.step.id,
                workflow_id=self.step.workflow_id,
                state=EventState.CREATED,
                event_type=self.step.facet_name,
                payload=self._build_payload(),
            )

            self.context.changes.add_created_event(event)

        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)

    def _build_payload(self) -> dict:
        """Build event payload from step attributes."""
        payload = {}
        for name, attr in self.step.attributes.params.items():
            payload[name] = attr.value
        return payload
```

### StateHandler Base Class

**File:** `afl/runtime/handlers/base.py`

All handlers extend `StateHandler(ABC)` (`base.py:13-117`):

```python
class StateHandler(ABC):
    """Abstract base for state handlers."""

    def __init__(self, step: StepDefinition, context: ExecutionContext):
        self.step = step
        self.context = context

    def process(self) -> StateChangeResult:
        """Process this state with logging and error handling."""
        self.context.telemetry.log_state_begin(self.step, self.state_name)
        try:
            result = self.process_state()
            self.context.telemetry.log_state_end(self.step, self.state_name)
            return result
        except Exception as e:
            self.context.telemetry.log_error(self.step, self.state_name, e)
            return StateChangeResult(
                step=self.step, success=False, error=e,
            )

    @abstractmethod
    def process_state(self) -> StateChangeResult:
        """Process the state logic. Subclasses implement this."""
        ...

    def transition(self) -> StateChangeResult:
        """Request transition to next state."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)

    def stay(self, push: bool = False) -> StateChangeResult:
        """Stay in current state, optionally re-queue."""
        self.step.request_state_change(False)
        self.step.transition.set_push_me(push)
        return StateChangeResult(step=self.step, continue_processing=push)

    def error(self, exception: Exception) -> StateChangeResult:
        """Mark step as errored."""
        self.step.mark_error(exception)
        return StateChangeResult(
            step=self.step, success=False, error=exception,
            continue_processing=False,
        )
```

### Handler Examples

**StatementCompleteHandler** (`completion.py:75-104`):

```python
class StatementCompleteHandler(StateHandler):
    """Handler for state.statement.Complete."""

    def process_state(self) -> StateChangeResult:
        """Complete statement execution."""
        self.step.mark_completed()
        self._notify_container()
        return StateChangeResult(
            step=self.step,
            continue_processing=False,
        )

    def _notify_container(self) -> None:
        """Notify containing block that this step is complete.
        Container notification is handled implicitly through iteration."""
        pass
```

**FacetInitializationBeginHandler** (`initialization.py:33-101`):

```python
class FacetInitializationBeginHandler(StateHandler):
    """Handler for state.facet.initialization.Begin."""

    def process_state(self) -> StateChangeResult:
        """Evaluate facet attribute expressions."""
        stmt_def = self.context.get_statement_definition(self.step)
        if stmt_def is None:
            # Workflow root step
            self.step.request_state_change(True)
            return StateChangeResult(step=self.step)

        ctx = self._build_context()
        try:
            args = stmt_def.args
            evaluated = evaluate_args(args, ctx)
            for name, value in evaluated.items():
                self.step.set_attribute(name, value)
            self.step.request_state_change(True)
            return StateChangeResult(step=self.step)
        except Exception as e:
            return self.error(e)
```

---

---

## 6. EventTransmit Blocking Behavior

> **Implemented** — see `spec/70_examples.md` Example 4 and `spec/30_runtime.md` §8.1.

The `EventTransmitHandler` has two distinct behaviors based on the facet type of the step being processed:

### Non-Event Facets (`FacetDecl`)

For steps that call a regular (non-event) facet:
- No event is created.
- The handler calls `request_state_change(True)`.
- The step immediately transitions to `state.statement.blocks.Begin`.
- This is a **pass-through** — no blocking occurs.

### Event Facets (`EventFacetDecl`)

For steps that call an event facet (e.g., `event CountDocuments(...)`):
1. The handler creates an `EventDefinition` with:
   - `event_type`: the facet name (e.g., `"example.4.CountDocuments"`)
   - `payload`: built from the step's evaluated attributes
   - `state`: `EventState.CREATED`
2. The event is added to `IterationChanges.add_created_event()`.
3. The handler calls `request_state_change(False)` — the step **stays** at `EventTransmit`.
4. The step is **blocked** until a `StepContinue` event is received from an external agent.

This blocking behavior is what causes the evaluator to reach a fixed point and pause (see §8).

---

## 7. StepContinue Events

> **Implemented** — see `spec/30_runtime.md` §12.1.

`StepContinue` is a system event type used to resume steps blocked at `state.EventTransmit`.

### Event Structure

```python
EventDefinition(
    event_type="StepContinue",
    step_id=<blocked step's StepId>,
    payload={"step_id": <blocked step's StepId>},
    state=EventState.CREATED,
)
```

### Processing Flow

1. External agent completes event processing and writes result to persistence.
2. Agent sends `StepContinue` event targeting the blocked step's ID.
3. Evaluator receives `StepContinue` (via polling or notification mechanism).
4. Evaluator locates the matching step in persistence.
5. Evaluator verifies step is at `state.EventTransmit`.
6. Step is allowed to transition: `EventTransmit` → `state.statement.blocks.Begin`.
7. Normal evaluation resumes.

### Idempotency

- `StepContinue` for a step that has already advanced past `EventTransmit` is a **no-op**.
- Duplicate `StepContinue` events MUST NOT cause errors or duplicate side effects.

---

## 8. Multi-Run Event Processing

> **Implemented** — see `spec/70_examples.md` Example 4 for the full sequence.

Workflows that invoke event facets require multiple evaluator runs separated by external agent processing.

### Sequence

```
┌──────────────┐                  ┌───────────────────┐                  ┌──────────────┐
│  Evaluator   │                  │   Persistence     │                  │   External   │
│              │                  │   (Database)      │                  │   Agent      │
└──────┬───────┘                  └────────┬──────────┘                  └──────┬───────┘
       │                                   │                                    │
       │── Run 1: process to fixed point ─▶│                                    │
       │   (steps + events committed)      │                                    │
       │                                   │                                    │
       │   (evaluator paused)              │  ◀── poll for events ──────────── │
       │                                   │                                    │
       │                                   │  ── event found, claimed ────────▶ │
       │                                   │                                    │
       │                                   │  ◀── processing complete ──────── │
       │                                   │     + StepContinue event           │
       │                                   │                                    │
       │  ◀── StepContinue received ────── │                                    │
       │                                   │                                    │
       │── Run 2: resume, process ────────▶│                                    │
       │   to next fixed point or done     │                                    │
       │                                   │                                    │
```

### Key Properties

- **State persistence**: All execution state is fully persisted at each pause boundary. The evaluator can be restarted from persistence.
- **Multiple pauses**: A workflow MAY pause and resume multiple times if it contains multiple event facet invocations at different points in the dependency graph.
- **No lost work**: Changes from all prior iterations are committed before pausing. External agents see the complete state.

---

## 9. Events vs. Tasks

Events and tasks are closely related but serve different purposes in the architecture.

### Events: Domain Lifecycle

An `EventDefinition` models the *semantic lifecycle* of external work. When a step invokes an event facet, the runtime creates an event that records:

- **What** needs to happen (`event_type`, e.g. `"example.4.CountDocuments"`)
- **Why** it needs to happen (`step_id` — the step that triggered it)
- **What data** to send (`payload` — built from evaluated step attributes)
- **Where it stands** (`state` — Created → Dispatched → Processing → Completed/Error)

Events are a domain concept: they describe the fact that a step requires work from an external agent, and they track the outcome of that work.

### Tasks: Distribution Mechanism

A `TaskDefinition` models a *claimable work item* in a distributed queue. When the `EventTransmitHandler` creates an event, it also creates a corresponding task that provides:

- **Routing** — `task_list_name` determines which queue the work appears in
- **Claiming** — `claim_task()` provides atomic PENDING → RUNNING transitions so multiple runners can compete safely
- **Locking** — MongoDB partial unique index `(step_id, state=running)` ensures exactly one agent processes each event step
- **Runner context** — `runner_id` tracks which runner claimed the work

Tasks are an infrastructure concept: they answer "who picks up the work and when?" without affecting event semantics.

### How They Relate

At `EVENT_TRANSMIT`, the handler creates both an event and a task in the same `IterationChanges`, committed atomically:

```
Step reaches EVENT_TRANSMIT
       │
       ├──▶ EventDefinition created   (what: domain lifecycle)
       │
       └──▶ TaskDefinition created    (who: distribution queue)
```

A runner or `AgentPoller` claims the **task**, performs the work, then calls `continue_step()` or `fail_step()` on the underlying **event-blocked step**. The event records the outcome; the task records the operational metadata (which runner, when claimed, duration).

### Why the Separation

This split allows the distribution strategy (polling intervals, concurrency limits, locking TTLs, task list routing) to evolve independently of the event model (state transitions, payload structure, lifecycle semantics). The evaluator's atomic commit model stays clean because tasks and events are committed together but consumed by different subsystems — the evaluator reads events, runners claim tasks.

---

## Summary

| Aspect | Implementation |
|--------|----------------|
| **Processing Model** | Synchronous iterative evaluator (not async polling) |
| **Event Lifecycle** | `EventManager` manages state transitions |
| **Event States** | Created → Dispatched → Processing → Completed/Error |
| **Handler Registration** | `LocalEventHandler` with dict-based lookup by event type |
| **Step Locking** | Inherent in synchronous model; MongoDB partial index for production |
| **Atomic Commits** | `IterationChanges` accumulated and committed at iteration boundary |
| **Dispatch** | `EventTransmitHandler` creates events during step execution |
| **State Transitions** | Created → Dispatched → Processing → Completed/Error |
| **EventTransmit Blocking** | Event facets block at EventTransmit; non-event facets pass through |
| **StepContinue** | System event to resume steps blocked at EventTransmit |
| **Multi-Run Execution** | Evaluator pauses at fixed point, resumes after external processing |

## Key Files Reference

| Component | Path |
|-----------|------|
| EventManager | `afl/runtime/events.py` |
| EventDispatcher | `afl/runtime/events.py` |
| LocalEventHandler | `afl/runtime/events.py` |
| EventDefinition | `afl/runtime/persistence.py` |
| EventState | `afl/runtime/states.py` |
| EVENT_TRANSITIONS | `afl/runtime/states.py` |
| IterationChanges | `afl/runtime/persistence.py` |
| PersistenceAPI | `afl/runtime/persistence.py` |
| EventTransmitHandler | `afl/runtime/handlers/completion.py` |
| StateHandler base | `afl/runtime/handlers/base.py` |
| Handler registry | `afl/runtime/handlers/__init__.py` |
