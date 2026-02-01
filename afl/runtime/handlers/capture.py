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

"""Capture phase handlers.

Handles yield/capture merging from blocks into containing step.
"""

from typing import TYPE_CHECKING

from ..changers.base import StateChangeResult
from .base import StateHandler

if TYPE_CHECKING:
    from ..step import StepDefinition


class MixinCaptureBeginHandler(StateHandler):
    """Handler for state.mixin.capture.Begin.

    Merges yield results from mixin blocks.
    """

    def process_state(self) -> StateChangeResult:
        """Begin mixin capture."""
        # Get completed mixin blocks
        blocks = self.context.persistence.get_blocks_by_step(self.step.id)
        mixin_blocks = [b for b in blocks if b.container_type == "Facet" and b.is_complete]

        # Merge yield results from each mixin block
        for block in mixin_blocks:
            self._merge_yields_from_block(block)

        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)

    def _merge_yields_from_block(self, block: "StepDefinition") -> None:
        """Merge yield results from a block into the step."""
        # Get yield steps from the block
        yields = self._get_yield_steps(block)
        for yield_step in yields:
            self._merge_yield(yield_step)

    def _get_yield_steps(self, block: "StepDefinition") -> list["StepDefinition"]:
        """Get all yield steps from a block."""
        from ..types import ObjectType

        steps = self.context.persistence.get_steps_by_block(block.id)
        return [s for s in steps if s.object_type == ObjectType.YIELD_ASSIGNMENT and s.is_complete]

    def _merge_yield(self, yield_step: "StepDefinition") -> None:
        """Merge a single yield into the step's attributes."""
        # Yield step attributes become return values on this step
        for name, attr in yield_step.attributes.params.items():
            self.step.attributes.set_return(name, attr.value, attr.type_hint)


class MixinCaptureEndHandler(StateHandler):
    """Handler for state.mixin.capture.End.

    Completes mixin capture phase.
    """

    def process_state(self) -> StateChangeResult:
        """End mixin capture."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)


class StatementCaptureBeginHandler(StateHandler):
    """Handler for state.statement.capture.Begin.

    Merges yield results from statement blocks (andThen).
    This is where yield TestOne(output = s2.input + 1) is captured.
    """

    def process_state(self) -> StateChangeResult:
        """Begin statement capture."""
        # Get completed statement blocks
        blocks = self.context.persistence.get_blocks_by_step(self.step.id)
        statement_blocks = [b for b in blocks if b.is_complete]

        # Also check pending changes for blocks that just completed
        for pending_step in self.context.changes.updated_steps:
            if (
                pending_step.container_id == self.step.id
                and pending_step.is_block
                and pending_step.is_complete
                and pending_step not in statement_blocks
            ):
                statement_blocks.append(pending_step)

        # Merge yield results from each block
        for block in statement_blocks:
            self._merge_yields_from_block(block)

        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)

    def _merge_yields_from_block(self, block: "StepDefinition") -> None:
        """Merge yield results from a block into the step."""
        from ..types import ObjectType

        # Get yield steps from the block
        steps = self.context.persistence.get_steps_by_block(block.id)

        # Also check pending changes
        for pending_step in self.context.changes.created_steps:
            if pending_step.block_id == block.id and pending_step not in steps:
                steps = list(steps) + [pending_step]
        for pending_step in self.context.changes.updated_steps:
            # Update existing steps with pending changes
            for i, s in enumerate(steps):
                if s.id == pending_step.id:
                    steps = list(steps)
                    steps[i] = pending_step

        yield_steps = [
            s for s in steps if s.object_type == ObjectType.YIELD_ASSIGNMENT and s.is_complete
        ]

        for yield_step in yield_steps:
            self._merge_yield(yield_step)

    def _merge_yield(self, yield_step: "StepDefinition") -> None:
        """Merge a single yield into the step's attributes.

        Yield attributes become return values on the containing step.
        """
        for name, attr in yield_step.attributes.params.items():
            self.step.attributes.set_return(name, attr.value, attr.type_hint)


class StatementCaptureEndHandler(StateHandler):
    """Handler for state.statement.capture.End.

    Completes statement capture phase.
    """

    def process_state(self) -> StateChangeResult:
        """End statement capture."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)
