"""Tests for ``facetwork.runtime.mixin_alias.resolve_mixin_step_by_alias``.

These exercise the synthesis path that backs the
``get_mixin_step_by_alias`` callback wired into every
``EvaluationContext`` — given a parent step, a mixin alias, and the
parent's yield steps, the helper returns a synthetic step whose
``attributes.returns`` carries the yielded values keyed by field
name.
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
        self._by_id = {s.id: s for s in steps}
        self._by_container: dict[str, list[StepDefinition]] = {}
        self._by_block: dict[str, list[StepDefinition]] = {}
        for s in steps:
            if s.container_id:
                self._by_container.setdefault(s.container_id, []).append(s)
            if s.block_id:
                self._by_block.setdefault(s.block_id, []).append(s)

    def get_step(self, step_id):
        return self._by_id.get(step_id)

    def get_steps_by_container(self, container_id):
        return list(self._by_container.get(container_id, []))

    def get_steps_by_block(self, block_id):
        return list(self._by_block.get(block_id, []))


def _facet_def(name: str, mixins: list[dict]) -> dict:
    return {"name": name, "mixins": mixins}


def test_resolves_alias_from_single_yield():
    """A single yield to an aliased mixin surfaces as the mixin
    sub-step's only return."""
    parent = _step(
        id="f2", object_type=ObjectType.VARIABLE_ASSIGNMENT, facet_name="F2"
    )
    block = _step(
        id="b1",
        object_type=ObjectType.AND_THEN,
        container_id="f2",
        container_type=parent.object_type,
    )
    yld = _step(
        id="y-m1",
        object_type=ObjectType.YIELD_ASSIGNMENT,
        block_id="b1",
        facet_name="M1",
        params={"output": "hello"},
    )
    persistence = _FakePersistence([parent, block, yld])
    facets = {
        "F2": _facet_def("F2", [{"target": "M1", "alias": "m1"}]),
    }

    synth = resolve_mixin_step_by_alias(
        "f2", "m1", persistence, lambda n: facets.get(n)
    )
    assert synth is not None
    assert synth.facet_name == "M1"
    assert synth.statement_name == "m1"
    assert synth.attributes.returns["output"].value == "hello"


def test_merges_multiple_yields_to_same_alias_list_collection():
    """Yields contributing to a list-typed field aggregate."""
    parent = _step(
        id="f2", object_type=ObjectType.VARIABLE_ASSIGNMENT, facet_name="F2"
    )
    block = _step(
        id="b1",
        object_type=ObjectType.AND_THEN,
        container_id="f2",
        container_type=parent.object_type,
    )
    y1 = _step(
        id="y1",
        object_type=ObjectType.YIELD_ASSIGNMENT,
        block_id="b1",
        facet_name="M1",
        params={"items": ["a"]},
    )
    y2 = _step(
        id="y2",
        object_type=ObjectType.YIELD_ASSIGNMENT,
        block_id="b1",
        facet_name="M1",
        params={"items": ["b"]},
    )
    persistence = _FakePersistence([parent, block, y1, y2])
    facets = {"F2": _facet_def("F2", [{"target": "M1", "alias": "m1"}])}

    synth = resolve_mixin_step_by_alias(
        "f2", "m1", persistence, lambda n: facets.get(n)
    )
    assert synth is not None
    assert synth.attributes.returns["items"].value == ["a", "b"]


def test_returns_none_when_alias_not_declared():
    parent = _step(
        id="f2", object_type=ObjectType.VARIABLE_ASSIGNMENT, facet_name="F2"
    )
    persistence = _FakePersistence([parent])
    facets = {"F2": _facet_def("F2", [{"target": "M1", "alias": "m1"}])}

    synth = resolve_mixin_step_by_alias(
        "f2", "not_declared", persistence, lambda n: facets.get(n)
    )
    assert synth is None


def test_returns_none_when_no_yields_target_alias():
    """The alias is declared, but the parent body never yielded to it."""
    parent = _step(
        id="f2", object_type=ObjectType.VARIABLE_ASSIGNMENT, facet_name="F2"
    )
    block = _step(
        id="b1",
        object_type=ObjectType.AND_THEN,
        container_id="f2",
        container_type=parent.object_type,
    )
    # Yield targets the parent itself, not M1.
    yld = _step(
        id="y-f2",
        object_type=ObjectType.YIELD_ASSIGNMENT,
        block_id="b1",
        facet_name="F2",
        params={"output": "primary"},
    )
    persistence = _FakePersistence([parent, block, yld])
    facets = {"F2": _facet_def("F2", [{"target": "M1", "alias": "m1"}])}

    synth = resolve_mixin_step_by_alias(
        "f2", "m1", persistence, lambda n: facets.get(n)
    )
    assert synth is None


def test_returns_none_when_parent_missing():
    persistence = _FakePersistence([])
    synth = resolve_mixin_step_by_alias(
        "missing", "m1", persistence, lambda n: None
    )
    assert synth is None
