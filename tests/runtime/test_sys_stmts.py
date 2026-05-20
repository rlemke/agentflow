"""End-to-end tests for `sys.log(...)` and `sys.assert(...)`.

These are inline diagnostic statements: side-effect only, no return
value, no place in expression position. They sit inside andThen
blocks alongside step assignments and walk a minimal lifecycle
(``SYS_STMT_TRANSITIONS``) — a single FACET_INIT_BEGIN tick does
the work and the step transitions to ``STATEMENT_COMPLETE`` (or
``STATEMENT_ERROR`` on a failing assertion).

Covered:

* ``sys.log`` evaluates args + emits a Splunk JSON record on the
  ``facetwork.sys.log`` logger; the record carries the user's named
  args alongside the runtime context (workflow_id, step_id,
  facet_name).
* ``sys.log`` mirrors to the step-log collection.
* ``sys.assert(true)`` passes; downstream steps run normally.
* ``sys.assert(false)`` errors the containing block and propagates.
* New boolean operators: ``in``, ``not in``, ``contains``,
  ``startsWith``, ``endsWith``.
"""

from __future__ import annotations

import json

import pytest

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
# sys.log
# ---------------------------------------------------------------------------


_LOG_SRC = """
namespace x {
    facet Identity(input: String) => (output: String) andThen {
        yield Identity(output = $.input)
    }
    workflow Demo(input: String) => (out: String) andThen {
        s1 = Identity(input = $.input)
        sys.log(name = s1.output, prefix = "hi")
        yield Demo(out = s1.output)
    }
}
"""


def test_sys_log_emits_splunk_json_record(caplog):
    """sys.log writes one log record on the `facetwork.sys.log` logger
    carrying the evaluated named args + execution context."""
    import logging

    with caplog.at_level(logging.INFO, logger="facetwork.sys.log"):
        result, _ = _run(_LOG_SRC, inputs={"input": "hello"})

    assert result.success
    sys_records = [r for r in caplog.records if r.name == "facetwork.sys.log"]
    assert len(sys_records) == 1, f"expected one sys.log record, got {len(sys_records)}"
    sys_extra = getattr(sys_records[0], "_sys_log", None)
    assert sys_extra is not None, "sys.log must attach the `_sys_log` extra dict"
    event = sys_extra.get("event") or {}
    assert event == {"name": "hello", "prefix": "hi"}
    # Runtime context must come along for free.
    assert sys_extra.get("workflow_id"), "workflow_id missing from sys.log context"
    assert sys_extra.get("step_id"), "step_id missing from sys.log context"


def test_sys_log_mirrors_to_step_log(caplog):
    """A sys.log call also writes an INFO step-log entry so the
    dashboard surfaces it alongside the step tree."""
    result, store = _run(_LOG_SRC, inputs={"input": "hello"})
    assert result.success

    logs = []
    # MemoryStore exposes get_step_logs_by_step for each step;
    # gather every entry and look for the sys.log JSON payload.
    from facetwork.runtime import ObjectType

    for s in store.get_steps_by_workflow(result.workflow_id):
        if s.object_type == ObjectType.SYS_LOG:
            logs.extend(store.get_step_logs_by_step(s.id))
    assert logs, "sys.log step should have at least one step-log entry"
    payloads = [log.message for log in logs if "sys.log" in (log.message or "")]
    assert payloads, "step-log should carry the sys.log JSON payload"
    parsed = json.loads(payloads[0])
    assert parsed.get("sys.log") == {"name": "hello", "prefix": "hi"}


# ---------------------------------------------------------------------------
# sys.assert
# ---------------------------------------------------------------------------


def test_sys_assert_true_passes_through():
    src = """
namespace x {
    facet Identity(input: String) => (output: String) andThen {
        yield Identity(output = $.input)
    }
    workflow Demo(input: String) => (out: String) andThen {
        s1 = Identity(input = $.input)
        sys.assert(s1.output == "hello")
        sys.assert(s1.output in ["hello", "world"])
        sys.assert("foo" not in [s1.output])
        sys.assert(s1.output startsWith "hel")
        sys.assert(s1.output endsWith "llo")
        sys.assert(s1.output contains "ell")
        yield Demo(out = s1.output)
    }
}
"""
    result, _ = _run(src, inputs={"input": "hello"})
    assert result.success, f"workflow failed: {result.error}"
    assert result.outputs == {"out": "hello"}


def test_sys_assert_false_halts_workflow():
    src = """
namespace x {
    facet Identity(input: String) => (output: String) andThen {
        yield Identity(output = $.input)
    }
    workflow Demo(input: String) => (out: String) andThen {
        s1 = Identity(input = $.input)
        sys.assert(s1.output == "different")
        yield Demo(out = s1.output)
    }
}
"""
    result, _ = _run(src, inputs={"input": "hello"})
    assert not result.success
    assert result.status == ExecutionStatus.ERROR
    assert "sys.assert failed" in str(result.error)


@pytest.mark.parametrize(
    "condition, input_value, expected_success",
    [
        ('s1.output in ["a", "b", "c"]', "a", True),
        ('s1.output in ["a", "b", "c"]', "z", False),
        ('s1.output not in ["a", "b", "c"]', "z", True),
        ('s1.output not in ["a", "b", "c"]', "a", False),
        ('s1.output contains "ell"', "hello", True),
        ('s1.output contains "xyz"', "hello", False),
        ('s1.output startsWith "h"', "hello", True),
        ('s1.output startsWith "x"', "hello", False),
        ('s1.output endsWith "lo"', "hello", True),
        ('s1.output endsWith "no"', "hello", False),
    ],
)
def test_new_operators_in_sys_assert(condition: str, input_value: str, expected_success: bool):
    src = f"""
namespace x {{
    facet Identity(input: String) => (output: String) andThen {{
        yield Identity(output = $.input)
    }}
    workflow Demo(input: String) => (out: String) andThen {{
        s1 = Identity(input = $.input)
        sys.assert({condition})
        yield Demo(out = s1.output)
    }}
}}
"""
    result, _ = _run(src, inputs={"input": input_value})
    assert result.success is expected_success, (
        f"condition {condition!r} with input {input_value!r}: "
        f"expected success={expected_success}, got {result.success}"
    )
