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


def _names_match(a: str | None, b: str | None) -> bool:
    """Check if two facet names match, handling qualified vs short names."""
    if not a or not b:
        return a == b
    if a == b:
        return True
    return a.endswith("." + b) or b.endswith("." + a)


def _merge_yield_value(existing: object, new: object) -> object:
    """Combine a prior yield value with a fresh one.

    Yield merge semantics are type-driven:
      - ``list``   → concat (``existing + new``). Order is yield order; for
        ``andThen foreach`` blocks where sub-blocks complete in parallel,
        that is dispatch-completion order, not iteration order.
      - ``set`` / ``frozenset`` → union (``existing | new``).
      - everything else (scalars, dicts, schema instances) → ``new``
        overwrites ``existing``. This preserves the historical contract
        for scalar yields (``yield F(count = $.x)`` reports the last
        iteration's value, dispatch-order-dependent) and for schema
        results (a yield of a single ``OSMCache`` replaces the prior one
        rather than smashing fields together).

    A ``foreach`` body that wants its outputs collected should yield a
    *list* containing the new element — ``yield F(items = [item])`` —
    so each iteration contributes one entry to the aggregate.

    Args:
        existing: The current return value already on the parent step.
        new: The value carried by the yield being merged.

    Returns:
        The combined value to store on the parent step.
    """
    if isinstance(existing, list) and isinstance(new, list):
        return existing + new
    if isinstance(existing, set) and isinstance(new, set):
        return existing | new
    if isinstance(existing, frozenset) and isinstance(new, frozenset):
        return existing | new
    return new


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
        """Merge a single yield into the step's attributes.

        Collection-typed values (``list``, ``set``, ``frozenset``) combine
        with the prior return value via concat/union so multiple yields
        aggregate into one collection. Other types (scalars, dicts,
        schema instances) overwrite — see ``_merge_yield_value``.
        """
        # Yield step attributes become return values on this step
        for name, attr in yield_step.attributes.params.items():
            existing = self.step.attributes.returns.get(name)
            merged_value = (
                _merge_yield_value(existing.value, attr.value)
                if existing is not None
                else attr.value
            )
            self.step.attributes.set_return(name, merged_value, attr.type_hint)


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

        # Merge yield results from every block, deduplicating yield steps
        # across blocks.  Foreach sub-blocks (each iteration) are listed as
        # direct children of the containing step AND show up again when the
        # parent foreach block is walked recursively — without the seen-set
        # below, each yield's contribution would be applied twice (a no-op
        # for scalar overwrites, but a doubled list for collection merges).
        self._seen_yield_ids: set[str] = set()
        for block in statement_blocks:
            self._merge_yields_from_block(block)

        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)

    def _merge_yields_from_block(self, block: "StepDefinition") -> None:
        """Merge yield results from a block into the step.

        For regular blocks, merges yield step attributes.
        For andThen script blocks, merges the block step's own returns
        (set by ScriptExecutor in _execute_script_block).

        Recursively searches descendant blocks (andWhen cases, nested
        andThen blocks) to collect yields at any depth.  Deduplication
        across calls to this method uses ``self._seen_yield_ids``, which
        the caller (``process_state``) seeds.
        """

        # Check if block itself has returns (andThen script blocks)
        if block.attributes.returns:
            for name, attr in block.attributes.returns.items():
                self.step.attributes.set_return(name, attr.value, attr.type_hint)

        # Collect yields recursively from this block and all descendant
        # blocks.  Only capture yields whose target matches the capture
        # scope (self.step.facet_name) so that inner facet body yields
        # (e.g. yield IntValueAdd inside Adder body) are not incorrectly
        # merged into the parent scope.
        target = self.step.facet_name
        yield_steps = self._collect_yields_recursive(block.id, target)

        seen = getattr(self, "_seen_yield_ids", None)
        for yield_step in yield_steps:
            if seen is not None:
                if yield_step.id in seen:
                    continue
                seen.add(yield_step.id)
            self._merge_yield(yield_step)

    def _collect_yields_recursive(
        self, block_id, target_name: str | None = None
    ) -> list["StepDefinition"]:
        """Recursively collect yield steps from a block and its descendants.

        Follows both block children (andWhen cases, nested andThen) and
        step_body blocks (andThen when/foreach attached to a step).

        Args:
            block_id: The block to search.
            target_name: If given, only yield steps whose facet_name
                matches this target are collected.  This prevents inner
                facet body yields from leaking into outer capture scopes.
        """
        from ..types import ObjectType

        steps = list(self.context.persistence.get_steps_by_block(block_id))

        # Also check pending changes
        for pending_step in self.context.changes.created_steps:
            if pending_step.block_id == block_id and pending_step not in steps:
                steps.append(pending_step)
        for pending_step in self.context.changes.updated_steps:
            for i, s in enumerate(steps):
                if s.id == pending_step.id:
                    steps[i] = pending_step

        yields = [
            s
            for s in steps
            if s.object_type == ObjectType.YIELD_ASSIGNMENT
            and s.is_complete
            and (target_name is None or _names_match(s.facet_name, target_name))
        ]

        # Recurse into sub-blocks (andWhen cases, nested andThen blocks)
        for s in steps:
            if s.is_block and s.is_complete:
                yields.extend(self._collect_yields_recursive(s.id, target_name))

        # Also follow step_body blocks: for each non-block step, check if
        # it has block children (from andThen when/foreach step_body).
        for s in steps:
            if not s.is_block and s.is_complete:
                child_blocks = self.context.persistence.get_blocks_by_step(s.id)
                for cb in child_blocks:
                    if cb.is_complete:
                        yields.extend(self._collect_yields_recursive(cb.id, target_name))

        return yields

    def _merge_yield(self, yield_step: "StepDefinition") -> None:
        """Merge a single yield into the step's attributes.

        Yield attributes become return values on the containing step.
        Collection-typed values (``list``, ``set``, ``frozenset``)
        combine with the prior return via concat/union so multiple
        yields — typically from ``andThen foreach`` sub-blocks —
        aggregate into one collection. Other types (scalars, dicts,
        schema instances) overwrite — see ``_merge_yield_value``.

        This is what lets a foreach body collect its outputs:

            } andThen foreach r in batch.regions {
                c = Download(region = $.r)
                yield Workflow(caches = [c.cache])  // 1-element list per iter
            }                                       // parent caches: [N elements]
        """
        for name, attr in yield_step.attributes.params.items():
            existing = self.step.attributes.returns.get(name)
            merged_value = (
                _merge_yield_value(existing.value, attr.value)
                if existing is not None
                else attr.value
            )
            self.step.attributes.set_return(name, merged_value, attr.type_hint)


class StatementCaptureEndHandler(StateHandler):
    """Handler for state.statement.capture.End.

    Completes statement capture phase.
    """

    def process_state(self) -> StateChangeResult:
        """End statement capture."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)
