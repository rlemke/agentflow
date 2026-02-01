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

"""Unit tests for MCP serializers."""

from afl.mcp.serializers import (
    serialize_execution_result,
    serialize_flow,
    serialize_flow_source,
    serialize_log,
    serialize_runner,
    serialize_server,
    serialize_step,
    serialize_task,
)
from afl.runtime.entities import (
    FlowDefinition,
    FlowIdentity,
    HandledCount,
    LogDefinition,
    Parameter,
    RunnerDefinition,
    ServerDefinition,
    SourceText,
    TaskDefinition,
    WorkflowDefinition,
)
from afl.runtime.evaluator import ExecutionResult, ExecutionStatus
from afl.runtime.step import StepDefinition
from afl.runtime.types import ObjectType


def _make_workflow(uuid="wf-1", name="TestWF"):
    return WorkflowDefinition(
        uuid=uuid,
        name=name,
        namespace_id="ns-1",
        facet_id="f-1",
        flow_id="flow-1",
        starting_step="s-1",
        version="1.0",
    )


def _make_runner(uuid="r-1", workflow=None, state="running"):
    if workflow is None:
        workflow = _make_workflow()
    return RunnerDefinition(
        uuid=uuid,
        workflow_id=workflow.uuid,
        workflow=workflow,
        state=state,
        start_time=1000,
        end_time=2000,
        duration=1000,
        parameters=[Parameter(name="x", value=42)],
    )


class TestSerializeRunner:
    def test_basic_fields(self):
        runner = _make_runner()
        d = serialize_runner(runner)
        assert d["uuid"] == "r-1"
        assert d["workflow_id"] == "wf-1"
        assert d["workflow_name"] == "TestWF"
        assert d["state"] == "running"
        assert d["start_time"] == 1000
        assert d["end_time"] == 2000
        assert d["duration"] == 1000

    def test_parameters(self):
        runner = _make_runner()
        d = serialize_runner(runner)
        assert len(d["parameters"]) == 1
        assert d["parameters"][0]["name"] == "x"
        assert d["parameters"][0]["value"] == 42


class TestSerializeStep:
    def test_basic_fields(self):
        step = StepDefinition.create(
            workflow_id="wf-1",
            object_type=ObjectType.WORKFLOW,
            facet_name="MyFacet",
        )
        d = serialize_step(step)
        assert d["workflow_id"] == "wf-1"
        assert d["object_type"] == ObjectType.WORKFLOW
        assert d["facet_name"] == "MyFacet"
        assert "id" in d
        assert "state" in d

    def test_params_included(self):
        step = StepDefinition.create(
            workflow_id="wf-1",
            object_type=ObjectType.FACET,
        )
        step.set_attribute("input_val", 99)
        d = serialize_step(step)
        assert d["params"]["input_val"] == 99

    def test_no_facet_name_omitted(self):
        step = StepDefinition.create(
            workflow_id="wf-1",
            object_type=ObjectType.FACET,
        )
        d = serialize_step(step)
        assert "facet_name" not in d


class TestSerializeFlow:
    def test_basic_fields(self):
        flow = FlowDefinition(
            uuid="f-1",
            name=FlowIdentity(name="MyFlow", path="/flows/my", uuid="f-1"),
            workflows=[_make_workflow()],
            compiled_sources=[SourceText(name="main.afl", content="facet Test()")],
        )
        d = serialize_flow(flow)
        assert d["uuid"] == "f-1"
        assert d["name"] == "MyFlow"
        assert d["path"] == "/flows/my"
        assert len(d["workflows"]) == 1
        assert d["workflows"][0]["name"] == "TestWF"
        assert d["sources"] == 1

    def test_flow_source(self):
        flow = FlowDefinition(
            uuid="f-1",
            name=FlowIdentity(name="MyFlow", path="/flows/my", uuid="f-1"),
            compiled_sources=[
                SourceText(name="main.afl", content="facet Test()"),
            ],
        )
        d = serialize_flow_source(flow)
        assert d["uuid"] == "f-1"
        assert len(d["sources"]) == 1
        assert d["sources"][0]["content"] == "facet Test()"
        assert d["sources"][0]["language"] == "afl"


class TestSerializeTask:
    def test_basic_fields(self):
        task = TaskDefinition(
            uuid="t-1",
            name="DoWork",
            runner_id="r-1",
            workflow_id="wf-1",
            flow_id="f-1",
            step_id="s-1",
            state="pending",
            created=1000,
            updated=1500,
        )
        d = serialize_task(task)
        assert d["uuid"] == "t-1"
        assert d["name"] == "DoWork"
        assert d["state"] == "pending"
        assert d["created"] == 1000


class TestSerializeLog:
    def test_basic_fields(self):
        log = LogDefinition(
            uuid="l-1",
            order=1,
            runner_id="r-1",
            message="Step started",
            note_type="info",
            time=5000,
        )
        d = serialize_log(log)
        assert d["uuid"] == "l-1"
        assert d["order"] == 1
        assert d["message"] == "Step started"
        assert d["time"] == 5000


class TestSerializeServer:
    def test_basic_fields(self):
        server = ServerDefinition(
            uuid="srv-1",
            server_group="default",
            service_name="afl-runner",
            server_name="host1",
            state="running",
            start_time=100,
            ping_time=200,
            topics=["TopicA"],
            handlers=["handler1"],
            handled=[HandledCount(handler="handler1", handled=5, not_handled=1)],
        )
        d = serialize_server(server)
        assert d["uuid"] == "srv-1"
        assert d["state"] == "running"
        assert d["topics"] == ["TopicA"]
        assert len(d["handled"]) == 1
        assert d["handled"][0]["handled"] == 5


class TestSerializeExecutionResult:
    def test_success(self):
        er = ExecutionResult(
            success=True,
            workflow_id="wf-1",
            outputs={"result": 42},
            iterations=3,
            status=ExecutionStatus.COMPLETED,
        )
        d = serialize_execution_result(er)
        assert d["success"] is True
        assert d["workflow_id"] == "wf-1"
        assert d["outputs"]["result"] == 42
        assert d["iterations"] == 3
        assert "error" not in d

    def test_error(self):
        er = ExecutionResult(
            success=False,
            workflow_id="wf-1",
            error=ValueError("bad input"),
            status=ExecutionStatus.ERROR,
        )
        d = serialize_execution_result(er)
        assert d["success"] is False
        assert d["error"] == "bad input"
