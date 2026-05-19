"""Mixin-alias resolution for FacetRef consumers.

A consumer that holds a FacetRef can address an aliased mixin's
attributes through ``$.fref.<alias>.<field>``.  The aliased mixin's
sub-step does not exist as a persisted row today (the runtime's
``MixinBlocksBeginHandler`` is still stubbed), so we synthesize one
on demand from the parent's yield steps:

    facet F2(...) => (...) with M1() as m1 with M2() as m2 andThen {
        yield F2(...) with M1(out = "x") with M2(out = "y")
    }

The chained yield is unpacked into three independent YieldStmt nodes
(one per target).  Each yield step persists with the call's named args
on ``attributes.params``.  For a FacetRef consumer reading
``$.f2.m1.out``, we look up F2's signature mixins to find the alias's
target facet (``M1``), walk F2's blocks for yield steps whose
``facet_name`` matches, and pack their params into a synthetic
sub-step's ``attributes.returns``.  Multiple yields targeting the
same mixin merge per the standard yield-merge rules (collections
aggregate, scalars overwrite — mirrors ``FacetAttributes.merge`` and
``_merge_yield_value`` in ``handlers/capture.py``).

The synthesized step is read-only and never persisted.  If/when the
runtime gains real facet-signature mixin execution, this helper can
be replaced with a direct ``get_steps_by_container`` lookup.
"""

from __future__ import annotations

from typing import Any

from .step import StepDefinition
from .types import AttributeValue, FacetAttributes


def _names_match(a: str | None, b: str | None) -> bool:
    """Match facet names handling qualified vs short forms."""
    if not a or not b:
        return a == b
    if a == b:
        return True
    return a.endswith("." + b) or b.endswith("." + a)


def _merge_yield_value(existing: object, new: object) -> object:
    """Mirror of ``handlers/capture._merge_yield_value`` — collections
    aggregate, other types overwrite."""
    if isinstance(existing, list) and isinstance(new, list):
        return existing + new
    if isinstance(existing, (set, frozenset)) and isinstance(new, (set, frozenset)):
        return existing | new
    return new


def resolve_mixin_step_by_alias(
    parent_step_id: str,
    alias: str,
    persistence: Any,
    get_facet_definition: Any,
) -> StepDefinition | None:
    """Return a synthetic step representing the aliased mixin's
    sub-step under ``parent_step_id``, or ``None`` if the parent
    isn't found, the alias isn't declared on the parent's facet, or
    no yields targeting that mixin have been captured.

    Args:
        parent_step_id: The persisted step holding the parent facet.
        alias: The mixin alias the consumer is reaching for.
        persistence: PersistenceAPI providing ``get_step``,
            ``get_steps_by_container``, ``get_steps_by_block``.
        get_facet_definition: Callable resolving a facet name to the
            facet declaration dict (with ``mixins``).  Same signature
            as ``EvaluationContext.get_facet_definition``.
    """
    parent = persistence.get_step(parent_step_id)
    if parent is None or not parent.facet_name:
        return None

    target_facet = _alias_target(get_facet_definition, parent.facet_name, alias)
    if target_facet is None:
        return None

    merged: dict[str, AttributeValue] = {}
    for yield_step in _collect_yields_for_target(persistence, parent.id, target_facet):
        for name, attr in yield_step.attributes.params.items():
            prior = merged.get(name)
            value = (
                _merge_yield_value(prior.value, attr.value)
                if prior is not None
                else attr.value
            )
            merged[name] = AttributeValue(name, value, attr.type_hint)

    if not merged:
        return None

    synth = StepDefinition(
        id=f"{parent_step_id}::{alias}",
        object_type=getattr(parent, "object_type", ""),
        workflow_id=parent.workflow_id,
        facet_name=target_facet,
        statement_name=alias,
        container_id=parent.id,
        container_type=parent.object_type,
        root_id=parent.root_id or parent.id,
        attributes=FacetAttributes(returns=merged),
    )
    return synth


def _alias_target(
    get_facet_definition: Any, parent_facet: str, alias: str
) -> str | None:
    """Look up the mixin target a given alias on a facet definition."""
    facet_def = get_facet_definition(parent_facet)
    if not facet_def:
        return None
    for mixin in facet_def.get("mixins", []):
        if mixin.get("alias") == alias:
            return mixin.get("target") or None
    return None


def _collect_yields_for_target(
    persistence: Any, container_id: str, target_facet: str
) -> list[StepDefinition]:
    """Walk every block under ``container_id`` and return yield steps
    whose ``facet_name`` matches ``target_facet``.  Recurses one level
    of nested blocks so yields inside the parent's ``andThen`` body
    are found regardless of which sub-block they were authored in."""
    from .types import ObjectType

    found: list[StepDefinition] = []
    blocks = list(persistence.get_steps_by_container(container_id))
    for block in blocks:
        if not getattr(block, "is_block", False):
            continue
        _walk_block_yields(persistence, block.id, target_facet, found, depth=0)
    return found


def _walk_block_yields(
    persistence: Any,
    block_id: str,
    target_facet: str,
    found: list[StepDefinition],
    depth: int,
) -> None:
    """Recursively collect yield steps under ``block_id`` matching
    ``target_facet``.  Depth is capped to avoid pathological loops in
    malformed step graphs."""
    from .types import ObjectType

    if depth > 8:
        return
    for step in persistence.get_steps_by_block(block_id):
        if (
            step.object_type == ObjectType.YIELD_ASSIGNMENT
            and step.is_complete
            and _names_match(step.facet_name, target_facet)
        ):
            found.append(step)
        elif getattr(step, "is_block", False):
            _walk_block_yields(persistence, step.id, target_facet, found, depth + 1)
