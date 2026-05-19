"""Tests for ``MixinBlocksBeginHandler`` creating placeholder mixin
sub-step rows for aliased facet-signature mixins.

The handler now creates a ``STATEMENT_COMPLETE`` placeholder step per
aliased mixin so the mixin appears as a child of the parent step in
the dashboard.  Actual mixin execution is still future work; the
FacetRef alias view is synthesised from the parent's yields (see
``facetwork/runtime/mixin_alias.py``).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from facetwork.runtime.changers.base import StateChangeResult
from facetwork.runtime.handlers.blocks import MixinBlocksBeginHandler
from facetwork.runtime.states import StepState
from facetwork.runtime.step import StepDefinition
from facetwork.runtime.types import ObjectType


def _make_step(facet_name: str = "F2") -> StepDefinition:
    return StepDefinition.create(
        workflow_id="wf-test",
        object_type=ObjectType.VARIABLE_ASSIGNMENT,
        facet_name=facet_name,
    )


def _make_context(facet_def: dict | None) -> MagicMock:
    context = MagicMock()
    context.get_facet_definition.return_value = facet_def
    context.persistence.get_steps_by_container.return_value = []
    context.changes.created_steps = []
    context.changes.add_created_step.side_effect = (
        lambda s: context.changes.created_steps.append(s)
    )
    return context


class TestMixinBlocksBeginPlaceholders:
    def test_creates_one_placeholder_per_aliased_mixin(self):
        step = _make_step("F2")
        facet_def = {
            "type": "FacetDecl",
            "name": "F2",
            "mixins": [
                {"target": "M1", "alias": "m1"},
                {"target": "M2", "alias": "m2"},
            ],
        }
        context = _make_context(facet_def)
        handler = MixinBlocksBeginHandler(step, context)

        result = handler.process_state()

        assert isinstance(result, StateChangeResult)
        created = context.changes.created_steps
        assert len(created) == 2

        by_alias = {s.statement_name: s for s in created}
        assert by_alias["m1"].facet_name == "M1"
        assert by_alias["m1"].container_id == step.id
        assert by_alias["m1"].state == StepState.STATEMENT_COMPLETE
        assert by_alias["m2"].facet_name == "M2"

    def test_unaliased_mixins_are_not_persisted(self):
        """Mixins without `as <alias>` stay invisible — they are private
        to the facet's composition and have no consumer-side name."""
        step = _make_step("F1")
        facet_def = {
            "type": "FacetDecl",
            "name": "F1",
            "mixins": [
                {"target": "M1"},  # no alias
                {"target": "M2"},
            ],
        }
        context = _make_context(facet_def)
        handler = MixinBlocksBeginHandler(step, context)

        handler.process_state()
        assert context.changes.created_steps == []

    def test_idempotent_when_placeholders_already_persisted(self):
        """Re-running the handler must not duplicate placeholder rows."""
        step = _make_step("F2")
        facet_def = {
            "type": "FacetDecl",
            "name": "F2",
            "mixins": [{"target": "M1", "alias": "m1"}],
        }
        context = _make_context(facet_def)
        # First run
        MixinBlocksBeginHandler(step, context).process_state()
        first_count = len(context.changes.created_steps)
        # Now simulate the placeholder having been persisted between runs.
        existing = context.changes.created_steps[0]
        context.persistence.get_steps_by_container.return_value = [existing]
        context.changes.created_steps = []  # fresh tick
        MixinBlocksBeginHandler(step, context).process_state()

        assert first_count == 1
        assert context.changes.created_steps == []

    def test_no_facet_def_is_noop(self):
        step = _make_step("Unknown")
        context = _make_context(None)
        handler = MixinBlocksBeginHandler(step, context)

        result = handler.process_state()

        assert isinstance(result, StateChangeResult)
        assert context.changes.created_steps == []
