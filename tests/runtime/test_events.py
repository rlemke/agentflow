"""Tests for AFL event lifecycle management."""

from unittest.mock import MagicMock

import pytest

from afl.runtime.events import EventDispatcher, EventManager, LocalEventHandler
from afl.runtime.persistence import EventDefinition
from afl.runtime.states import EventState


@pytest.fixture
def persistence():
    return MagicMock()


@pytest.fixture
def manager(persistence):
    return EventManager(persistence=persistence)


class TestEventManager:
    """Test EventManager lifecycle transitions."""

    def test_create_event(self, manager):
        event = manager.create_event(
            step_id="s-1",
            workflow_id="wf-1",
            event_type="DoWork",
            payload={"key": "value"},
        )
        assert isinstance(event, EventDefinition)
        assert event.state == EventState.CREATED
        assert event.step_id == "s-1"
        assert event.workflow_id == "wf-1"
        assert event.event_type == "DoWork"
        assert event.payload == {"key": "value"}
        assert event.id  # should have a generated ID

    def test_dispatch_event(self, manager):
        event = manager.create_event("s-1", "wf-1", "DoWork", {})
        dispatched = manager.dispatch(event)
        assert dispatched.state == EventState.DISPATCHED
        assert dispatched is event  # same object mutated

    def test_start_processing(self, manager):
        event = manager.create_event("s-1", "wf-1", "DoWork", {})
        manager.dispatch(event)
        processing = manager.start_processing(event)
        assert processing.state == EventState.PROCESSING

    def test_complete_event(self, manager):
        event = manager.create_event("s-1", "wf-1", "DoWork", {})
        manager.dispatch(event)
        manager.start_processing(event)
        completed = manager.complete(event, {"output": 42})
        assert completed.state == EventState.COMPLETED
        assert completed.payload["result"] == {"output": 42}

    def test_error_event(self, manager):
        event = manager.create_event("s-1", "wf-1", "DoWork", {})
        manager.dispatch(event)
        manager.start_processing(event)
        errored = manager.error(event, "something went wrong")
        assert errored.state == EventState.ERROR
        assert errored.payload["error"] == "something went wrong"

    def test_full_lifecycle_success(self, manager):
        event = manager.create_event("s-1", "wf-1", "DoWork", {"input": "x"})
        assert event.state == EventState.CREATED

        manager.dispatch(event)
        assert event.state == EventState.DISPATCHED

        manager.start_processing(event)
        assert event.state == EventState.PROCESSING

        manager.complete(event, {"done": True})
        assert event.state == EventState.COMPLETED
        assert event.payload["result"] == {"done": True}
        assert event.payload["input"] == "x"  # original payload preserved

    def test_full_lifecycle_error(self, manager):
        event = manager.create_event("s-1", "wf-1", "DoWork", {})
        manager.dispatch(event)
        manager.start_processing(event)
        manager.error(event, "fail")
        assert event.state == EventState.ERROR
        assert event.payload["error"] == "fail"

    def test_get_pending_events_returns_empty(self, manager):
        result = manager.get_pending_events("wf-1")
        assert list(result) == []

    def test_create_event_unique_ids(self, manager):
        e1 = manager.create_event("s-1", "wf-1", "A", {})
        e2 = manager.create_event("s-2", "wf-1", "B", {})
        assert e1.id != e2.id


class TestEventDispatcher:
    """Test EventDispatcher stub methods."""

    def test_dispatch_is_noop(self):
        dispatcher = EventDispatcher()
        event = EventDefinition(
            id="e-1",
            step_id="s-1",
            workflow_id="wf-1",
            state=EventState.DISPATCHED,
            event_type="DoWork",
            payload={},
        )
        # Should not raise
        dispatcher.dispatch(event)

    def test_poll_completed_returns_empty(self):
        dispatcher = EventDispatcher()
        assert dispatcher.poll_completed() == []


class TestLocalEventHandler:
    """Test LocalEventHandler for local testing."""

    def test_register_and_handle(self):
        handler = LocalEventHandler()
        handler.register("DoWork", lambda payload: {"result": payload["x"] * 2})

        event = EventDefinition(
            id="e-1",
            step_id="s-1",
            workflow_id="wf-1",
            state=EventState.PROCESSING,
            event_type="DoWork",
            payload={"x": 5},
        )
        result = handler.handle(event)
        assert result == {"result": 10}

    def test_handle_unknown_type_returns_none(self):
        handler = LocalEventHandler()
        event = EventDefinition(
            id="e-1",
            step_id="s-1",
            workflow_id="wf-1",
            state=EventState.PROCESSING,
            event_type="Unknown",
            payload={},
        )
        assert handler.handle(event) is None

    def test_register_multiple_handlers(self):
        handler = LocalEventHandler()
        handler.register("A", lambda p: {"type": "A"})
        handler.register("B", lambda p: {"type": "B"})

        event_a = EventDefinition(
            id="e-1",
            step_id="s-1",
            workflow_id="wf-1",
            state=EventState.PROCESSING,
            event_type="A",
            payload={},
        )
        event_b = EventDefinition(
            id="e-2",
            step_id="s-1",
            workflow_id="wf-1",
            state=EventState.PROCESSING,
            event_type="B",
            payload={},
        )
        assert handler.handle(event_a) == {"type": "A"}
        assert handler.handle(event_b) == {"type": "B"}

    def test_handler_overwrites_previous(self):
        handler = LocalEventHandler()
        handler.register("DoWork", lambda p: {"v": 1})
        handler.register("DoWork", lambda p: {"v": 2})

        event = EventDefinition(
            id="e-1",
            step_id="s-1",
            workflow_id="wf-1",
            state=EventState.PROCESSING,
            event_type="DoWork",
            payload={},
        )
        assert handler.handle(event) == {"v": 2}
