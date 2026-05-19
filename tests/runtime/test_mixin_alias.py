"""Tests for ``facetwork.runtime.mixin_alias.resolve_mixin_step_by_alias``.

The helper is a thin lookup over persistence: given a parent step id
and an alias name, it returns the persisted mixin sub-step whose
``statement_name`` matches the alias.  The sub-step is created by
``MixinBlocksBeginHandler`` and populated with returns by
``StatementCaptureBeginHandler``'s yield-routing path.
"""

from __future__ import annotations

from facetwork.runtime.mixin_alias import resolve_mixin_step_by_alias
from facetwork.runtime.step import StepDefinition
from facetwork.runtime.types import AttributeValue, FacetAttributes, ObjectType


def _step(
    *,
    id: str,
    object_type: str,
    workflow_id: str = "wf-1",
    facet_name: str = "",
    statement_name: str = "",
    container_id: str | None = None,
    container_type: str | None = None,
    block_id: str | None = None,
    params: dict | None = None,
    returns: dict | None = None,
    state: str = "state.statement.Complete",
) -> StepDefinition:
    attrs = FacetAttributes(
        params={k: AttributeValue(k, v) for k, v in (params or {}).items()},
        returns={k: AttributeValue(k, v) for k, v in (returns or {}).items()},
    )
    return StepDefinition(
        id=id,
        object_type=object_type,
        workflow_id=workflow_id,
        facet_name=facet_name,
        statement_name=statement_name,
        container_id=container_id,
        container_type=container_type,
        block_id=block_id,
        state=state,
        attributes=attrs,
    )


class _FakePersistence:
    def __init__(self, steps: list[StepDefinition]):
        self._by_container: dict[str, list[StepDefinition]] = {}
        for s in steps:
            if s.container_id:
                self._by_container.setdefault(s.container_id, []).append(s)

    def get_steps_by_container(self, container_id):
        return list(self._by_container.get(container_id, []))


def test_returns_sub_step_when_alias_matches_statement_name():
    """Happy path: persistence has a child with ``statement_name == alias``."""
    sub = _step(
        id="sub-m1",
        object_type=ObjectType.VARIABLE_ASSIGNMENT,
        facet_name="M1",
        statement_name="m1",
        container_id="f2",
        returns={"output": "from-routing"},
    )
    persistence = _FakePersistence([sub])
    result = resolve_mixin_step_by_alias("f2", "m1", persistence)
    assert result is sub
    assert result.attributes.returns["output"].value == "from-routing"


def test_returns_none_when_no_child_matches_alias():
    """The parent has children but none use this alias."""
    other = _step(
        id="other",
        object_type=ObjectType.VARIABLE_ASSIGNMENT,
        facet_name="M2",
        statement_name="m2",
        container_id="f2",
    )
    persistence = _FakePersistence([other])
    assert resolve_mixin_step_by_alias("f2", "m1", persistence) is None


def test_returns_none_when_parent_has_no_children():
    """Parent never reached MIXIN_BLOCKS_BEGIN, so no placeholder exists."""
    persistence = _FakePersistence([])
    assert resolve_mixin_step_by_alias("f2", "m1", persistence) is None


def test_legacy_get_facet_definition_positional_arg_is_ignored():
    """The synthesis-era 4th positional arg is accepted for source-level
    back-compat with callers that still pass it."""
    sub = _step(
        id="sub-m1",
        object_type=ObjectType.VARIABLE_ASSIGNMENT,
        facet_name="M1",
        statement_name="m1",
        container_id="f2",
    )
    persistence = _FakePersistence([sub])
    result = resolve_mixin_step_by_alias(
        "f2", "m1", persistence, lambda name: {"name": name, "mixins": []}
    )
    assert result is sub
