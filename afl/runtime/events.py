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

"""AFL event lifecycle management.

Events represent work to be dispatched to external agents.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from .persistence import EventDefinition, PersistenceAPI
from .states import EventState
from .types import EventId, StepId, WorkflowId, event_id


@dataclass
class EventManager:
    """Manages event lifecycle.

    Handles:
    - Event creation
    - State transitions
    - Event dispatch
    - Completion handling
    """

    persistence: PersistenceAPI

    def create_event(
        self,
        step_id: StepId,
        workflow_id: WorkflowId,
        event_type: str,
        payload: dict,
    ) -> EventDefinition:
        """Create a new event.

        Args:
            step_id: The step that generated this event
            workflow_id: The workflow this event belongs to
            event_type: Type of event (usually facet name)
            payload: Event payload data

        Returns:
            New EventDefinition in CREATED state
        """
        eid = event_id()
        logger.info(
            "Event created: event_id=%s step_id=%s workflow_id=%s event_type=%s",
            eid,
            step_id,
            workflow_id,
            event_type,
        )
        return EventDefinition(
            id=eid,
            step_id=step_id,
            workflow_id=workflow_id,
            state=EventState.CREATED,
            event_type=event_type,
            payload=payload,
        )

    def dispatch(self, event: EventDefinition) -> EventDefinition:
        """Dispatch an event for processing.

        Args:
            event: The event to dispatch

        Returns:
            Updated event in DISPATCHED state
        """
        logger.debug(
            "Event dispatched: event_id=%s event_type=%s",
            event.id,
            event.event_type,
        )
        event.state = EventState.DISPATCHED
        return event

    def start_processing(self, event: EventDefinition) -> EventDefinition:
        """Mark event as being processed.

        Args:
            event: The event to mark

        Returns:
            Updated event in PROCESSING state
        """
        logger.debug("Event processing: event_id=%s", event.id)
        event.state = EventState.PROCESSING
        return event

    def complete(self, event: EventDefinition, result: dict) -> EventDefinition:
        """Mark event as completed.

        Args:
            event: The event to complete
            result: Result data from processing

        Returns:
            Updated event in COMPLETED state
        """
        logger.info(
            "Event completed: event_id=%s result_keys=%s",
            event.id,
            list(result.keys()),
        )
        event.state = EventState.COMPLETED
        event.payload["result"] = result
        return event

    def error(self, event: EventDefinition, error: str) -> EventDefinition:
        """Mark event as errored.

        Args:
            event: The event to mark
            error: Error message

        Returns:
            Updated event in ERROR state
        """
        logger.warning(
            "Event error: event_id=%s error=%s",
            event.id,
            error,
        )
        event.state = EventState.ERROR
        event.payload["error"] = error
        return event

    def get_pending_events(self, workflow_id: WorkflowId) -> Sequence[EventDefinition]:
        """Get all pending events for a workflow.

        Args:
            workflow_id: The workflow to check

        Returns:
            Events in non-terminal states
        """
        # This would be implemented by the persistence layer
        # For now, return empty
        return []


@dataclass
class EventDispatcher:
    """Dispatches events to external handlers.

    In a real implementation, this would send events to:
    - Message queues
    - HTTP endpoints
    - Local handlers
    """

    def dispatch(self, event: EventDefinition) -> None:
        """Dispatch an event.

        Args:
            event: The event to dispatch
        """
        # In a real implementation, this would send to external system
        # For testing, we can simulate immediate completion
        pass

    def poll_completed(self) -> list[tuple[EventId, dict]]:
        """Poll for completed events.

        Returns:
            List of (event_id, result) tuples
        """
        # In a real implementation, this would check for responses
        return []


class LocalEventHandler:
    """Handles events locally for testing.

    Simulates agent processing without external systems.
    """

    def __init__(self) -> None:
        """Initialize handler."""
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(
        self, event_type: str, handler: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        """Register a handler for an event type.

        Args:
            event_type: The event type to handle
            handler: Function that takes payload and returns result
        """
        self._handlers[event_type] = handler

    def handle(self, event: EventDefinition) -> dict | None:
        """Handle an event locally.

        Args:
            event: The event to handle

        Returns:
            Result dict if handled, None if no handler
        """
        handler = self._handlers.get(event.event_type)
        if handler:
            return handler(event.payload)
        return None
