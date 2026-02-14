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

"""Completion phase handlers.

Handles statement end, completion, and event transmission.
"""

import time
from typing import TYPE_CHECKING

from ..changers.base import StateChangeResult
from ..states import EventState
from ..types import event_id, generate_id
from .base import StateHandler

if TYPE_CHECKING:
    pass


def _current_time_ms() -> int:
    """Get current time in milliseconds."""
    return int(time.time() * 1000)


class EventTransmitHandler(StateHandler):
    """Handler for state.EventTransmit.

    Dispatches events to external agents for processing.
    For event facets, this is where the external work happens.
    """

    def process_state(self) -> StateChangeResult:
        """Transmit event to agent.

        For event facets: if an inline dispatcher is available and can
        handle this facet, dispatches immediately and completes the step.
        Otherwise creates an event and a task in the task queue, then
        BLOCKS the step until an external caller invokes continue_step().
        For regular facets: passes through to next state.
        """
        facet_def = self.context.get_facet_definition(self.step.facet_name)

        if facet_def and facet_def.get("type") == "EventFacetDecl":
            # Try inline dispatch if a dispatcher is available
            dispatcher = self.context.dispatcher
            if dispatcher and dispatcher.can_dispatch(self.step.facet_name):
                try:
                    payload = self._build_payload()
                    result = dispatcher.dispatch(self.step.facet_name, payload)
                    if result is not None:
                        for name, value in result.items():
                            self.step.set_attribute(name, value, is_return=True)
                        self.step.request_state_change(True)
                        return StateChangeResult(step=self.step)
                except Exception as e:
                    return self.error(e)

            # Fallback: create event + task and block
            from ..persistence import EventDefinition

            event = EventDefinition(
                id=event_id(),
                step_id=self.step.id,
                workflow_id=self.step.workflow_id,
                state=EventState.CREATED,
                event_type=self.step.facet_name,
                payload=self._build_payload(),
            )

            # Add to pending events
            self.context.changes.add_created_event(event)

            # Create a task in the task queue for agents to claim
            self._create_event_task()

            # BLOCK: stay at EventTransmit, do not re-queue
            return self.stay(push=False)

        # Non-event facet: pass through to next state
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)

    def _build_payload(self) -> dict:
        """Build event payload from step attributes."""
        payload = {}
        for name, attr in self.step.attributes.params.items():
            payload[name] = attr.value
        return payload

    def _create_event_task(self) -> None:
        """Create a TaskDefinition for the event and add to iteration changes."""
        from ..entities import TaskDefinition, TaskState

        now = _current_time_ms()
        task = TaskDefinition(
            uuid=generate_id(),
            name=self.step.facet_name,
            runner_id=self.context.runner_id,
            workflow_id=self.step.workflow_id,
            flow_id="",
            step_id=self.step.id,
            state=TaskState.PENDING,
            created=now,
            updated=now,
            task_list_name="default",
            data=self._build_payload(),
        )
        self.context.changes.add_created_task(task)


class StatementEndHandler(StateHandler):
    """Handler for state.statement.End.

    Prepares step for completion.
    """

    def process_state(self) -> StateChangeResult:
        """End statement execution."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)


class StatementCompleteHandler(StateHandler):
    """Handler for state.statement.Complete.

    Marks step as complete and notifies containing block.
    """

    def process_state(self) -> StateChangeResult:
        """Complete statement execution."""
        # Mark step as completed
        self.step.mark_completed()

        # Notify containing block if any
        self._notify_container()

        return StateChangeResult(
            step=self.step,
            continue_processing=False,
        )

    def _notify_container(self) -> None:
        """Notify containing block that this step is complete.

        This triggers the block to re-evaluate its progress.
        Note: We don't add to updated_steps here because the container
        will be re-processed in the next iteration anyway. Adding a stale
        copy from persistence would overwrite the properly updated version.
        """
        # Container notification is handled implicitly through iteration
        # The container will be re-processed and see this step is complete
        pass
