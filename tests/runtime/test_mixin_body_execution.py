"""End-to-end tests for Scope B: mixin sub-steps execute their facet's
own ``andThen`` body before the parent body runs.

Locked design (mirrors session_mixin_body_execution_2026-05-19 memo):

1. Aliased mixin sub-steps run fully before the parent body.
2. Multiple aliased mixins on the same parent run in parallel.
3. Inside a mixin body, ``$.`` resolves only to the mixin sub-step's
   own attributes — no workflow root inheritance, no parent-scope
   reach-out.
4. Sig-args (``with M(x = $.input)``) are evaluated in the parent's
   scope at the parent's FACET_INIT_BEGIN and become the mixin
   sub-step's bound params.
5. If a mixin sub-step errors, the parent step errors.
6. ``parent.attributes.params[alias]`` is refreshed at MIXIN_CAPTURE
   to a merged ``{params, returns}`` dict snapshot of the mixin
   sub-step — the parent's andThen body reads ``$.alias.field``
   through this snapshot.  FacetRef consumers read the live
   persisted sub-step (so Scope A parent-yield overrides are
   visible to them).
"""

from __future__ import annotations

from facetwork.ast_utils import find_workflow
from facetwork.emitter import emit_dict
from facetwork.parser import parse
from facetwork.runtime import Evaluator, ExecutionStatus, MemoryStore, Telemetry


def _run(src: str, inputs: dict, workflow_name: str = "Demo"):
    program = emit_dict(parse(src))
    workflow_ast = find_workflow(program, workflow_name)
    store = MemoryStore()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))
    result = evaluator.execute(workflow_ast, inputs=inputs, program_ast=program)
    return result, store


# ---------------------------------------------------------------------------
# Mixin body executes and parent body reads its returns.
# ---------------------------------------------------------------------------


_MIXIN_BODY_RUNS = """
namespace mb {
    facet M(input: String) => (output: String) andThen {
        yield M(output = $.input ++ "-from-mixin-body")
    }

    facet Parent(input: String) => (out: String)
        with M(input = $.input) as m
        andThen {
            yield Parent(out = $.m.output)
        }

    workflow Demo(input: String) => (out: String) andThen {
        p = Parent(input = $.input)
        yield Demo(out = p.out)
    }
}
"""


def test_mixin_body_executes_and_parent_reads_returns():
    result, _ = _run(_MIXIN_BODY_RUNS, inputs={"input": "hello"})
    assert result.success, f"workflow failed: {result.error}"
    assert result.status == ExecutionStatus.COMPLETED
    # Mixin body ran and produced output; parent body read it via $.m.output.
    assert result.outputs == {"out": "hello-from-mixin-body"}


# ---------------------------------------------------------------------------
# Two aliased mixins run in parallel; parent reads both.
# ---------------------------------------------------------------------------


_TWO_MIXINS_PARALLEL = """
namespace mb {
    facet Tag(prefix: String) => (out: String) andThen {
        yield Tag(out = $.prefix ++ ":done")
    }

    facet Parent(input: String) => (left: String, right: String)
        with Tag(prefix = "L") as l
        with Tag(prefix = "R") as r
        andThen {
            yield Parent(left = $.l.out, right = $.r.out)
        }

    workflow Demo(input: String) => (left: String, right: String) andThen {
        p = Parent(input = $.input)
        yield Demo(left = p.left, right = p.right)
    }
}
"""


def test_two_aliased_mixins_run_independently_and_parent_reads_both():
    result, _ = _run(_TWO_MIXINS_PARALLEL, inputs={"input": "x"})
    assert result.success, f"workflow failed: {result.error}"
    assert result.outputs == {"left": "L:done", "right": "R:done"}


# ---------------------------------------------------------------------------
# Mixin body scope is isolated — $.workflow_input is not visible inside it.
# ---------------------------------------------------------------------------


_MIXIN_SCOPE_ISOLATED = """
namespace mb {
    facet M(input: String) => (output: String) andThen {
        // Only $.input (mixin's own param) is visible here.
        // Workflow root's $.input is not in scope.
        yield M(output = "mixin-saw-" ++ $.input)
    }

    facet Parent(input: String) => (out: String)
        with M(input = "isolated") as m
        andThen {
            yield Parent(out = $.m.output)
        }

    workflow Demo(input: String) => (out: String) andThen {
        p = Parent(input = $.input)
        yield Demo(out = p.out)
    }
}
"""


def test_mixin_body_scope_isolation_uses_only_its_own_params():
    """If mixin scope were not isolated, `$.input` inside M's body could
    pick up the workflow root's "input" instead of the mixin's bound
    one.  This test pins the isolated behavior."""
    result, _ = _run(_MIXIN_SCOPE_ISOLATED, inputs={"input": "workflow-root"})
    assert result.success, f"workflow failed: {result.error}"
    # M.input was bound to "isolated" at sig-arg time; M's body saw that,
    # not "workflow-root".
    assert result.outputs == {"out": "mixin-saw-isolated"}


# ---------------------------------------------------------------------------
# Mixin error propagates to parent.
# ---------------------------------------------------------------------------


_MIXIN_ERROR_PROPAGATES = """
namespace mb {
    facet Bad(input: String) => (output: String) andThen {
        // Reference a name that isn't in scope so the mixin errors at
        // evaluation time.
        yield Bad(output = $.bogus)
    }

    facet Parent(input: String) => (out: String)
        with Bad(input = $.input) as b
        andThen {
            yield Parent(out = $.b.output)
        }

    workflow Demo(input: String) => (out: String) andThen {
        p = Parent(input = $.input)
        yield Demo(out = p.out)
    }
}
"""


def test_mixin_error_halts_parent():
    result, _ = _run(_MIXIN_ERROR_PROPAGATES, inputs={"input": "x"})
    assert not result.success
    assert result.status == ExecutionStatus.ERROR


# ---------------------------------------------------------------------------
# Parent-yield override (Scope A interaction): mixin body sets a value,
# parent body's `yield aliasName(...)` overrides it for FacetRef consumers.
# ---------------------------------------------------------------------------


_OVERRIDE_PATTERN = """
namespace mb {
    facet M(input: String) => (output: String) andThen {
        yield M(output = "from-body")
    }

    facet Parent(input: String) => (out: String)
        with M(input = "x") as m
        andThen {
            // Parent yield-to-mixin overrides the mixin body's return
            // for downstream FacetRef consumers (see Consumer below).
            // The parent's own `$.m.output` read still sees the mixin
            // body's value (the snapshot was taken at MIXIN_CAPTURE,
            // before this yield is routed).
            yield Parent(out = $.m.output)
            yield m(output = "from-parent-override")
        }

    facet Consumer(p: Parent) => (parent_view: String, consumer_view: String) andThen {
        yield Consumer(
            parent_view = $.p.out,
            consumer_view = $.p.m.output
        )
    }

    workflow Demo(input: String) => (parent_view: String, consumer_view: String) andThen {
        p = Parent(input = $.input)
        c = Consumer(p = p)
        yield Demo(parent_view = c.parent_view, consumer_view = c.consumer_view)
    }
}
"""


def test_parent_yield_overrides_mixin_body_for_facetref_consumers():
    result, _ = _run(_OVERRIDE_PATTERN, inputs={"input": "x"})
    assert result.success, f"workflow failed: {result.error}"
    # Parent's own body read $.m.output via the MIXIN_CAPTURE snapshot,
    # which froze the mixin body's value before the override.
    assert result.outputs["parent_view"] == "from-body"
    # Consumer reads the live persisted sub-step via FacetRef, so it
    # sees the override applied at parent's STATEMENT_CAPTURE_BEGIN.
    assert result.outputs["consumer_view"] == "from-parent-override"


# ---------------------------------------------------------------------------
# Mixin sub-step persists with its computed returns.
# ---------------------------------------------------------------------------


def test_mixin_sub_step_persisted_with_computed_returns():
    result, store = _run(_MIXIN_BODY_RUNS, inputs={"input": "ping"})
    assert result.success

    from facetwork.runtime import ObjectType

    workflow_steps = list(store.get_steps_by_workflow(result.workflow_id))
    parent_steps = [
        s
        for s in workflow_steps
        if s.facet_name
        and s.facet_name.split(".")[-1] == "Parent"
        and s.object_type == ObjectType.VARIABLE_ASSIGNMENT
    ]
    assert len(parent_steps) == 1
    parent = parent_steps[0]

    children = list(store.get_steps_by_container(parent.id))
    by_alias = {c.statement_name: c for c in children if c.statement_name}
    assert "m" in by_alias
    m_step = by_alias["m"]

    assert m_step.attributes.params["input"].value == "ping"
    assert m_step.attributes.returns["output"].value == "ping-from-mixin-body"


# ---------------------------------------------------------------------------
# Canonical 09 runs end-to-end under Scope B.
# ---------------------------------------------------------------------------


def test_canonical_09_runs_under_scope_b():
    """Run examples/canonical/09-facetref-mixin-alias.ffl end-to-end:
    mixin bodies compute their outputs, parent body reads them via
    snapshot, FacetRef consumer reads them via persistence resolver."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "canonical"
        / "09-facetref-mixin-alias.ffl"
    ).read_text()
    result, _ = _run(src, inputs={"input": "alpha"})
    assert result.success, f"workflow failed: {result.error}"
    assert result.outputs == {
        "primary": "alpha-primary",
        "m1_out": "alpha-m1",
        "m2_out": "alpha-m2",
    }
