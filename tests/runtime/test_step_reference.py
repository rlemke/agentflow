"""Step-reference feature: parse, validate, evaluate, serialize.

Covers the contract described in `examples/canonical/08-step-reference.ffl`:
- bare step names in argument position parse to StepRef(path=[name])
- the validator accepts them (existence is still checked)
- the evaluator returns a StepReference when path has length 1
- _resolve_path dereferences StepReference via the get_step_by_id callback
- StepReference round-trips through its tagged JSON form
- the canonical example parses and validates cleanly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from facetwork.emitter import emit_dict
from facetwork.parser import parse
from facetwork.runtime.expression import EvaluationContext, ExpressionEvaluator
from facetwork.runtime.types import (
    AttributeValue,
    FacetAttributes,
    StepReference,
    deserialize_attribute_value,
    serialize_attribute_value,
)
from facetwork.validator import validate as validate_ast


CANONICAL = Path(__file__).resolve().parents[2] / "examples" / "canonical" / "08-step-reference.ffl"


# =========================================================================
# Parser / emitter
# =========================================================================


def _find(node, predicate):
    """Walk a nested dict/list AST and return the first node where predicate is true."""
    if isinstance(node, dict):
        if predicate(node):
            return node
        for v in node.values():
            r = _find(v, predicate)
            if r is not None:
                return r
    elif isinstance(node, list):
        for x in node:
            r = _find(x, predicate)
            if r is not None:
                return r
    return None


def test_bare_step_name_emits_stepref_with_single_path():
    src = """
    namespace t {
      facet A(input: String) => (out: String) andThen {
        yield A(out = $.input)
      }
      facet B(ds: A) => (out: String) andThen {
        yield B(out = $.ds.out)
      }
      workflow W(x: String) => (out: String) andThen {
        s1 = A(input = $.x)
        s2 = B(ds = s1)
        yield W(out = s2.out)
      }
    }
    """
    ast = parse(src, "t.ffl")
    out = emit_dict(ast, include_locations=False)

    s2 = _find(out, lambda n: n.get("name") == "s2" and "call" in n)
    assert s2 is not None
    ds_arg = next(a for a in s2["call"]["args"] if a["name"] == "ds")
    assert ds_arg["value"]["type"] == "StepRef"
    assert ds_arg["value"]["path"] == ["s1"]


def test_canonical_example_parses_and_validates():
    src = CANONICAL.read_text()
    ast = parse(src, str(CANONICAL))
    result = validate_ast(ast)
    assert not result.errors, f"unexpected validator errors: {result.errors}"


# =========================================================================
# Validator — STEP_REF_FACET_MISMATCH
# =========================================================================


_MISMATCH_SRC = """
namespace refs {
    facet DoSomething(input: String) => (output: String) andThen {
        yield DoSomething(output = $.input ++ "!")
    }
    facet OtherFacet(value: String) => (output: String) andThen {
        yield OtherFacet(output = $.value)
    }
    facet AnotherThing(ds: DoSomething) => (output: String) andThen {
        yield AnotherThing(output = $.ds.output)
    }
    workflow Demo(input: String) => (output: String) andThen {
        s1  = DoSomething(input = $.input)
        bad = OtherFacet(value = $.input)
        s2  = AnotherThing(ds = bad)
        yield Demo(output = s2.output)
    }
}
"""


def test_step_ref_facet_mismatch_emits_rule_id():
    result = validate_ast(parse(_MISMATCH_SRC))
    mismatches = [e for e in result.errors if e.rule_id == "STEP_REF_FACET_MISMATCH"]
    assert len(mismatches) == 1, f"expected one mismatch, got {result.errors}"
    msg = str(mismatches[0])
    assert "bad" in msg
    assert "OtherFacet" in msg
    assert "DoSomething" in msg
    assert "ds" in msg


def test_step_ref_facet_match_passes():
    src = """
namespace refs {
    facet DoSomething(input: String) => (output: String) andThen {
        yield DoSomething(output = $.input)
    }
    facet AnotherThing(ds: DoSomething) => (output: String) andThen {
        yield AnotherThing(output = $.ds.output)
    }
    workflow Demo(input: String) => (output: String) andThen {
        s1 = DoSomething(input = $.input)
        s2 = AnotherThing(ds = s1)
        yield Demo(output = s2.output)
    }
}
"""
    result = validate_ast(parse(src))
    assert not [e for e in result.errors if e.rule_id == "STEP_REF_FACET_MISMATCH"], (
        f"unexpected mismatch: {result.errors}"
    )


def test_step_ref_field_access_not_flagged_as_mismatch():
    """`step.field` references are not step-refs; they should never trigger
    STEP_REF_FACET_MISMATCH even if the field name happens to be a facet
    name."""
    src = """
namespace refs {
    facet DoSomething(input: String) => (output: String) andThen {
        yield DoSomething(output = $.input)
    }
    facet Sink(value: String) => (out: String) andThen {
        yield Sink(out = $.value)
    }
    workflow Demo(input: String) => (out: String) andThen {
        s1 = DoSomething(input = $.input)
        s2 = Sink(value = s1.output)
        yield Demo(out = s2.out)
    }
}
"""
    result = validate_ast(parse(src))
    assert not [e for e in result.errors if e.rule_id == "STEP_REF_FACET_MISMATCH"]


def test_step_ref_mismatch_in_mixin_args():
    """Mixin call args should also be checked."""
    src = """
namespace refs {
    facet DoSomething(input: String) => (output: String) andThen {
        yield DoSomething(output = $.input)
    }
    facet OtherFacet(value: String) => (output: String) andThen {
        yield OtherFacet(output = $.value)
    }
    facet WithRef(ds: DoSomething) => (output: String) andThen {
        yield WithRef(output = $.ds.output)
    }
    facet Composed() => (output: String) andThen {
        yield Composed(output = "x")
    }
    workflow Demo(input: String) => (output: String) andThen {
        bad = OtherFacet(value = $.input)
        c   = Composed() with WithRef(ds = bad)
        yield Demo(output = c.output)
    }
}
"""
    result = validate_ast(parse(src))
    mismatches = [e for e in result.errors if e.rule_id == "STEP_REF_FACET_MISMATCH"]
    assert len(mismatches) == 1, f"expected mismatch in mixin args, got {result.errors}"


# =========================================================================
# Evaluator
# =========================================================================


class _FakeStep:
    """Minimal StepDefinition shape consumed by the evaluator."""

    def __init__(self, step_id, workflow_id, facet_name, returns, params=None):
        self.id = step_id
        self.workflow_id = workflow_id
        self.facet_name = facet_name
        self.attributes = FacetAttributes(
            params={k: AttributeValue(k, v) for k, v in (params or {}).items()},
            returns={k: AttributeValue(k, v) for k, v in returns.items()},
        )


def test_eval_step_ref_bare_returns_step_reference():
    step = _FakeStep("sid-1", "wf-1", "DoSomething", {"output": "hello"})
    ctx = EvaluationContext(
        inputs={},
        get_step_output=lambda *_: None,
        get_step_by_name=lambda name: step if name == "s1" else None,
    )
    evaluator = ExpressionEvaluator()
    val = evaluator.evaluate({"type": "StepRef", "path": ["s1"]}, ctx)
    assert isinstance(val, StepReference)
    assert val.step_id == "sid-1"
    assert val.workflow_id == "wf-1"
    assert val.facet_name == "DoSomething"
    # caching populated
    assert "sid-1" in ctx._resolved_refs


def test_resolve_path_dereferences_step_reference():
    step = _FakeStep("sid-2", "wf-1", "DoSomething", {"output": "world"})
    ref = StepReference(step_id="sid-2", workflow_id="wf-1", facet_name="DoSomething")
    ctx = EvaluationContext(
        inputs={"ds": ref},
        get_step_output=lambda *_: None,
        get_step_by_id=lambda sid: step if sid == "sid-2" else None,
    )
    evaluator = ExpressionEvaluator()
    val = evaluator.evaluate({"type": "InputRef", "path": ["ds", "output"]}, ctx)
    assert val == "world"


def test_resolve_path_missing_callback_errors():
    ref = StepReference(step_id="sid-3", workflow_id="wf-1", facet_name="Anything")
    ctx = EvaluationContext(
        inputs={"ds": ref},
        get_step_output=lambda *_: None,
    )
    evaluator = ExpressionEvaluator()
    from facetwork.runtime.errors import ReferenceError

    with pytest.raises(ReferenceError, match="get_step_by_id"):
        evaluator.evaluate({"type": "InputRef", "path": ["ds", "output"]}, ctx)


def test_resolve_path_unknown_field_errors_on_param_or_return():
    step = _FakeStep("sid-4", "wf-1", "DoSomething", {"output": "x"})
    ref = StepReference(step_id="sid-4", workflow_id="wf-1", facet_name="DoSomething")
    ctx = EvaluationContext(
        inputs={"ds": ref},
        get_step_output=lambda *_: None,
        get_step_by_id=lambda sid: step,
    )
    evaluator = ExpressionEvaluator()
    from facetwork.runtime.errors import ReferenceError

    with pytest.raises(ReferenceError, match="no param or return 'nope'"):
        evaluator.evaluate({"type": "InputRef", "path": ["ds", "nope"]}, ctx)


def test_resolve_path_reads_bound_input_via_step_ref():
    """A step-ref consumer reads bound inputs of the upstream step as well
    as its returns — both are persisted attributes of a fully-evaluated
    step."""
    step = _FakeStep(
        "sid-5",
        "wf-1",
        "Value",
        returns={},
        params={"input": "hi"},
    )
    ref = StepReference(step_id="sid-5", workflow_id="wf-1", facet_name="Value")
    ctx = EvaluationContext(
        inputs={"facetRef": ref},
        get_step_output=lambda *_: None,
        get_step_by_id=lambda sid: step,
    )
    evaluator = ExpressionEvaluator()
    val = evaluator.evaluate(
        {"type": "InputRef", "path": ["facetRef", "input"]}, ctx
    )
    assert val == "hi"


def test_resolve_path_return_shadows_param_on_name_collision():
    """When a field name appears in both params and returns (e.g. a yielded
    value overrides the input under the same name), the return wins —
    matching FacetAttributes.merge() semantics."""
    step = _FakeStep(
        "sid-6",
        "wf-1",
        "Value",
        returns={"input": "yielded"},
        params={"input": "bound"},
    )
    ref = StepReference(step_id="sid-6", workflow_id="wf-1", facet_name="Value")
    ctx = EvaluationContext(
        inputs={"facetRef": ref},
        get_step_output=lambda *_: None,
        get_step_by_id=lambda sid: step,
    )
    evaluator = ExpressionEvaluator()
    val = evaluator.evaluate(
        {"type": "InputRef", "path": ["facetRef", "input"]}, ctx
    )
    assert val == "yielded"


# =========================================================================
# Serialization
# =========================================================================


def test_step_reference_json_round_trip():
    ref = StepReference(step_id="abc", workflow_id="wf", facet_name="A")
    data = ref.to_json()
    assert data == {
        "_facet_ref": True,
        "step_id": "abc",
        "workflow_id": "wf",
        "facet_name": "A",
    }
    back = StepReference.from_json(data)
    assert back == ref


def test_serialize_attribute_value_handles_nested_refs():
    ref = StepReference(step_id="abc", workflow_id="wf", facet_name="A")
    nested = {"list": [ref, 1, "x"], "ref": ref, "plain": "ok"}
    out = serialize_attribute_value(nested)
    assert out["ref"] == ref.to_json()
    assert out["list"][0] == ref.to_json()
    assert out["list"][1:] == [1, "x"]
    assert out["plain"] == "ok"

    restored = deserialize_attribute_value(out)
    assert restored["ref"] == ref
    assert restored["list"][0] == ref


def test_is_ref_recognizes_both_forms():
    ref = StepReference(step_id="x", workflow_id="w", facet_name="A")
    assert StepReference.is_ref(ref)
    assert StepReference.is_ref(ref.to_json())
    assert not StepReference.is_ref({"foo": "bar"})
    assert not StepReference.is_ref("not-a-ref")
