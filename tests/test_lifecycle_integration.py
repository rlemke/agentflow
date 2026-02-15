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

"""Cross-component integration tests: AFL source → compile → execute → resume."""

import json

import pytest

from afl import emit_dict, parse
from afl.runtime import Evaluator, ExecutionStatus, MemoryStore, StepState, Telemetry
from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig
from afl.runtime.entities import HandlerRegistration

try:
    from mcp.types import TextContent  # noqa: F401

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


# =========================================================================
# Inline AFL source constants
# =========================================================================

AFL_HELLO = """\
namespace hello {
    event facet Greet(name: String) => (greeting: String)

    workflow SayHello(name: String) => (result: String) andThen {
        g = Greet(name = $.name)
        yield SayHello(result = g.greeting)
    }
}
"""

AFL_MULTI_STEP = """\
namespace multi {
    event facet StepA(input: Long) => (output: Long)
    event facet StepB(input: Long) => (output: Long)

    workflow TwoStep(x: Long) => (result: Long) andThen {
        a = StepA(input = $.x)
        b = StepB(input = a.output)
        yield TwoStep(result = b.output)
    }
}
"""

AFL_FOREACH = """\
namespace batch {
    event facet Process(input: Long) => (output: Long)

    workflow ProcessAll(items: Json) => (count: Long)
      andThen foreach r in $.items {
        v = Process(input = r)
        yield ProcessAll(count = v.output)
      }
}
"""


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def evaluator(store):
    return Evaluator(persistence=store, telemetry=Telemetry(enabled=False))


def _compile(source: str):
    """Parse and compile AFL source, returning (workflow_ast, program_ast)."""
    ast = parse(source)
    compiled = emit_dict(ast)
    return compiled


def _find_workflow(compiled: dict, name: str):
    """Find a workflow declaration by name in compiled output."""
    # Check top-level workflows list
    for wf in compiled.get("workflows", []):
        if wf.get("name") == name:
            return wf
    # Check namespaces
    for ns in compiled.get("namespaces", []):
        for wf in ns.get("workflows", []):
            if wf.get("name") == name:
                return wf
    # Check declarations (may contain WorkflowDecl or namespaces)
    for decl in compiled.get("declarations", []):
        if decl.get("type") == "WorkflowDecl" and decl.get("name") == name:
            return decl
        if decl.get("type") == "Namespace":
            for nested in decl.get("declarations", []):
                if nested.get("type") == "WorkflowDecl" and nested.get("name") == name:
                    return nested
    return None


def _register_handler(store, tmp_path, facet_name, code):
    """Write handler module to temp file and register."""
    f = tmp_path / f"{facet_name.replace('.', '_')}_handler.py"
    f.write_text(code)
    reg = HandlerRegistration(
        facet_name=facet_name,
        module_uri=f"file://{f}",
        entrypoint="handle",
    )
    store.save_handler_registration(reg)


# =========================================================================
# Full lifecycle tests
# =========================================================================


class TestFullLifecycleSimple:
    """Parse AFL → compile → execute → pause → continue → resume → verify."""

    def test_hello_workflow_compiles_and_executes(self, store, evaluator):
        compiled = _compile(AFL_HELLO)
        wf_ast = _find_workflow(compiled, "SayHello")
        assert wf_ast is not None

        result = evaluator.execute(wf_ast, inputs={"name": "World"}, program_ast=compiled)
        assert result.status == ExecutionStatus.PAUSED

    def test_hello_workflow_continues_and_completes(self, store, evaluator, tmp_path):
        compiled = _compile(AFL_HELLO)
        wf_ast = _find_workflow(compiled, "SayHello")

        result = evaluator.execute(wf_ast, inputs={"name": "World"}, program_ast=compiled)
        assert result.status == ExecutionStatus.PAUSED

        # Find the blocked step and continue it manually
        blocked = store.get_steps_by_state(StepState.EVENT_TRANSMIT)
        assert len(blocked) == 1
        step = blocked[0]
        assert step.attributes.get_param("name") == "World"

        # Manually provide return values
        evaluator.continue_step(step.id, result={"greeting": "Hello, World!"})

        final = evaluator.resume(result.workflow_id, wf_ast, compiled)
        assert final.success
        assert final.status == ExecutionStatus.COMPLETED
        assert final.outputs["result"] == "Hello, World!"

    def test_simple_workflow_without_event_completes_immediately(self, store, evaluator):
        source = "workflow Direct(x: Long) => (y: Long)"
        compiled = _compile(source)
        wf_ast = _find_workflow(compiled, "Direct")
        assert wf_ast is not None

        result = evaluator.execute(wf_ast, inputs={"x": 42}, program_ast=compiled)
        assert result.success
        assert result.status == ExecutionStatus.COMPLETED


class TestFullLifecycleMultiStep:
    """Two sequential event facets with data flow between steps."""

    def test_two_step_data_flows(self, store, evaluator, tmp_path):
        compiled = _compile(AFL_MULTI_STEP)
        wf_ast = _find_workflow(compiled, "TwoStep")

        result = evaluator.execute(wf_ast, inputs={"x": 5}, program_ast=compiled)
        assert result.status == ExecutionStatus.PAUSED

        # Step A should be blocked with input=5
        blocked = store.get_steps_by_state(StepState.EVENT_TRANSMIT)
        assert len(blocked) == 1
        evaluator.continue_step(blocked[0].id, result={"output": 10})

        # Resume to create Step B
        r2 = evaluator.resume(result.workflow_id, wf_ast, compiled)
        assert r2.status == ExecutionStatus.PAUSED

        # Step B should be blocked with input=10 (from a.output)
        blocked2 = store.get_steps_by_state(StepState.EVENT_TRANSMIT)
        assert len(blocked2) == 1
        assert blocked2[0].attributes.get_param("input") == 10

        evaluator.continue_step(blocked2[0].id, result={"output": 100})

        final = evaluator.resume(result.workflow_id, wf_ast, compiled)
        assert final.success
        assert final.outputs["result"] == 100


class TestFullLifecycleRegistryRunner:
    """From AFL source through RegistryRunner dispatch."""

    def test_registry_runner_processes_hello(self, store, evaluator, tmp_path):
        compiled = _compile(AFL_HELLO)
        wf_ast = _find_workflow(compiled, "SayHello")

        _register_handler(
            store, tmp_path, "hello.Greet",
            "def handle(payload):\n    return {'greeting': 'Hi, ' + payload['name']}\n",
        )

        result = evaluator.execute(wf_ast, inputs={"name": "Test"}, program_ast=compiled)
        assert result.status == ExecutionStatus.PAUSED

        runner = RegistryRunner(
            persistence=store,
            evaluator=evaluator,
            config=RegistryRunnerConfig(),
        )
        runner.cache_workflow_ast(result.workflow_id, wf_ast, program_ast=compiled)
        dispatched = runner.poll_once()
        assert dispatched == 1

        final = evaluator.resume(result.workflow_id, wf_ast, compiled)
        assert final.success
        assert final.outputs["result"] == "Hi, Test"


class TestCompileAndExecuteEdgeCases:
    """Edge cases in compilation and execution."""

    def test_namespaced_workflow_found(self, store, evaluator):
        compiled = _compile(AFL_HELLO)
        wf_ast = _find_workflow(compiled, "SayHello")
        assert wf_ast is not None
        assert wf_ast["type"] == "WorkflowDecl"
        assert wf_ast["name"] == "SayHello"

    def test_invalid_source_raises(self):
        with pytest.raises(Exception):
            _compile("this is not valid afl {{{{")

    def test_validation_catches_duplicate(self):
        from afl.validator import validate

        source = "facet Dup()\nfacet Dup()"
        ast = parse(source)
        result = validate(ast)
        assert not result.is_valid

    def test_nonexistent_workflow_returns_none(self, store, evaluator):
        compiled = _compile("facet NotAWorkflow()")
        wf_ast = _find_workflow(compiled, "Missing")
        assert wf_ast is None


AFL_TOP_LEVEL_WORKFLOW = """\
event facet AddOne(input: Long) => (output: Long)

workflow TestAddOne(x: Long) => (result: Long) andThen {
    s = AddOne(input = $.x)
    yield TestAddOne(result = s.output)
}
"""


@pytest.mark.skipif(not MCP_AVAILABLE, reason="mcp not installed")
class TestMcpToolIntegration:
    """Chain MCP tool functions: compile → execute → continue → resume."""

    def test_compile_valid_source(self):
        from afl.mcp.server import _tool_compile

        result = _tool_compile({"source": AFL_HELLO})
        data = json.loads(result[0].text)
        assert data["success"] is True
        assert "json" in data

    def test_compile_then_execute_top_level(self):
        from afl.mcp.server import _tool_compile, _tool_execute_workflow

        # Compile
        compile_result = _tool_compile({"source": AFL_TOP_LEVEL_WORKFLOW})
        compile_data = json.loads(compile_result[0].text)
        assert compile_data["success"] is True

        # Execute — top-level workflow should be found and pause
        exec_result = _tool_execute_workflow({
            "source": AFL_TOP_LEVEL_WORKFLOW,
            "workflow_name": "TestAddOne",
            "inputs": {"x": 5},
        })
        exec_data = json.loads(exec_result[0].text)
        assert exec_data["success"] is True
        assert "workflow_id" in exec_data

    def test_execute_simple_workflow_completes(self):
        from afl.mcp.server import _tool_execute_workflow

        source = "workflow Direct(x: Long) => (y: Long)"
        result = _tool_execute_workflow({
            "source": source,
            "workflow_name": "Direct",
            "inputs": {"x": 42},
        })
        data = json.loads(result[0].text)
        assert data["success"] is True
        assert data["status"] == "COMPLETED"

    def test_execute_nonexistent_workflow(self):
        from afl.mcp.server import _tool_execute_workflow

        result = _tool_execute_workflow({
            "source": "facet NotWorkflow()",
            "workflow_name": "Missing",
        })
        data = json.loads(result[0].text)
        assert data["success"] is False
        assert "not found" in data["error"]
