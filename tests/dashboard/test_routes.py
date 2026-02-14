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

"""Integration tests for dashboard routes using TestClient + mongomock."""

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

try:
    import mongomock

    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE or not MONGOMOCK_AVAILABLE, reason="fastapi or mongomock not installed"
)


@pytest.fixture
def client():
    """Create a test client with mongomock-backed store."""
    from afl.dashboard import dependencies as deps
    from afl.dashboard.app import create_app
    from afl.runtime.mongo_store import MongoStore

    # Create a mongomock-backed store
    mock_client = mongomock.MongoClient()
    store = MongoStore(database_name="afl_test_dashboard", client=mock_client)

    app = create_app()

    # Override the dependency
    app.dependency_overrides[deps.get_store] = lambda: store

    with TestClient(app) as tc:
        yield tc, store

    store.drop_database()
    store.close()


def _make_workflow(uuid="wf-1", name="TestWF"):
    from afl.runtime.entities import WorkflowDefinition

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
    from afl.runtime.entities import RunnerDefinition

    if workflow is None:
        workflow = _make_workflow()
    return RunnerDefinition(
        uuid=uuid,
        workflow_id=workflow.uuid,
        workflow=workflow,
        state=state,
    )


class TestHomeRoute:
    def test_home_page(self, client):
        tc, store = client
        resp = tc.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_home_shows_counts(self, client):
        tc, store = client
        resp = tc.get("/")
        assert resp.status_code == 200
        assert "Runners" in resp.text
        assert "Servers" in resp.text

    def test_home_with_data(self, client):
        """Covers runner_counts and task_counts loop bodies."""
        tc, store = client
        from afl.runtime.entities import TaskDefinition, TaskState

        store.save_runner(_make_runner("r-1", state="running"))
        store.save_runner(_make_runner("r-2", state="completed"))
        task = TaskDefinition(
            uuid="task-1",
            name="T1",
            runner_id="r-1",
            workflow_id="wf-1",
            flow_id="flow-1",
            step_id="s-1",
            task_list_name="default",
            state=TaskState.PENDING,
        )
        store.save_task(task)

        resp = tc.get("/")
        assert resp.status_code == 200


class TestRunnerRoutes:
    def test_runner_list_empty(self, client):
        tc, store = client
        resp = tc.get("/runners")
        assert resp.status_code == 200

    def test_runner_list_with_data(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.RUNNING,
        )
        store.save_runner(runner)

        resp = tc.get("/runners")
        assert resp.status_code == 200
        assert "r-1" in resp.text or "TestWF" in resp.text

    def test_runner_list_filter_by_state(self, client):
        tc, store = client
        resp = tc.get("/runners?state=running")
        assert resp.status_code == 200

    def test_runner_detail_not_found(self, client):
        tc, store = client
        resp = tc.get("/runners/nonexistent")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_runner_detail_with_data(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.RUNNING,
        )
        store.save_runner(runner)

        resp = tc.get("/runners/r-1")
        assert resp.status_code == 200
        assert "TestWF" in resp.text

    def test_cancel_runner(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.RUNNING,
        )
        store.save_runner(runner)

        resp = tc.post("/runners/r-1/cancel", follow_redirects=False)
        assert resp.status_code == 303

        updated = store.get_runner("r-1")
        assert updated.state == "cancelled"

    def test_pause_runner(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.RUNNING,
        )
        store.save_runner(runner)

        resp = tc.post("/runners/r-1/pause", follow_redirects=False)
        assert resp.status_code == 303

        updated = store.get_runner("r-1")
        assert updated.state == "paused"

    def test_resume_runner(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.PAUSED,
        )
        store.save_runner(runner)

        resp = tc.post("/runners/r-1/resume", follow_redirects=False)
        assert resp.status_code == 303

        updated = store.get_runner("r-1")
        assert updated.state == "running"

    def test_runner_steps_page(self, client):
        """Covers runners.py runner_steps route."""
        tc, store = client
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import step_id
        from afl.runtime.types import workflow_id as wf_id_fn

        wf = _make_workflow()
        runner = _make_runner("r-1", workflow=wf)
        store.save_runner(runner)

        sid = step_id()
        step = StepDefinition(
            id=sid,
            workflow_id=wf_id_fn(),
            object_type="VariableAssignment",
            state="state.facet.initialization.Begin",
        )
        step.workflow_id = wf.uuid  # match the runner's workflow
        store.save_step(step)

        resp = tc.get("/runners/r-1/steps")
        assert resp.status_code == 200
        assert "VariableAssignment" in resp.text

    def test_runner_logs_page(self, client):
        """Covers runners.py runner_logs route."""
        tc, store = client
        from afl.runtime.entities import LogDefinition

        store.save_runner(_make_runner("r-1"))
        log = LogDefinition(
            uuid="log-1",
            order=1,
            runner_id="r-1",
            message="Step started",
            time=1000,
        )
        store.save_log(log)

        resp = tc.get("/runners/r-1/logs")
        assert resp.status_code == 200
        assert "Step started" in resp.text


class TestStepRoutes:
    def test_step_detail_not_found(self, client):
        tc, store = client
        resp = tc.get("/steps/nonexistent")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_step_detail_with_data(self, client):
        tc, store = client
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import step_id, workflow_id

        sid = step_id()
        wid = workflow_id()
        step = StepDefinition(
            id=sid,
            workflow_id=wid,
            object_type="VariableAssignment",
            state="state.facet.initialization.Begin",
        )
        store.save_step(step)

        resp = tc.get(f"/steps/{sid}")
        assert resp.status_code == 200
        assert "VariableAssignment" in resp.text

    def test_retry_step(self, client):
        tc, store = client
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import step_id, workflow_id

        sid = step_id()
        wid = workflow_id()
        step = StepDefinition(
            id=sid,
            workflow_id=wid,
            object_type="VariableAssignment",
            state="state.facet.error.Failed",
        )
        store.save_step(step)

        resp = tc.post(f"/steps/{sid}/retry", follow_redirects=False)
        assert resp.status_code == 303

        updated = store.get_step(sid)
        assert updated.state == "state.facet.initialization.Begin"


class TestLogRoutes:
    def test_log_list(self, client):
        """Covers logs.py log_list route."""
        tc, store = client
        from afl.runtime.entities import LogDefinition

        store.save_runner(_make_runner("r-1"))
        log = LogDefinition(
            uuid="log-1",
            order=1,
            runner_id="r-1",
            message="Hello log",
            time=5000,
        )
        store.save_log(log)

        resp = tc.get("/logs/r-1")
        assert resp.status_code == 200
        assert "Hello log" in resp.text


class TestFlowRoutes:
    def test_flow_list_empty(self, client):
        tc, store = client
        resp = tc.get("/flows")
        assert resp.status_code == 200
        assert "Flows" in resp.text

    def test_flow_list_with_data(self, client):
        tc, store = client
        from afl.runtime.entities import FlowDefinition, FlowIdentity

        flow = FlowDefinition(
            uuid="flow-1",
            name=FlowIdentity(name="TestFlow", path="/test", uuid="flow-1"),
        )
        store.save_flow(flow)

        resp = tc.get("/flows")
        assert resp.status_code == 200
        assert "TestFlow" in resp.text

    def test_flow_detail(self, client):
        tc, store = client
        from afl.runtime.entities import FlowDefinition, FlowIdentity

        flow = FlowDefinition(
            uuid="flow-1",
            name=FlowIdentity(name="TestFlow", path="/test", uuid="flow-1"),
        )
        store.save_flow(flow)

        resp = tc.get("/flows/flow-1")
        assert resp.status_code == 200
        assert "TestFlow" in resp.text

    def test_flow_detail_not_found(self, client):
        tc, store = client
        resp = tc.get("/flows/nonexistent")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_flow_source_with_data(self, client):
        """Covers flows.py flow_source route."""
        tc, store = client
        from afl.runtime.entities import FlowDefinition, FlowIdentity, SourceText

        flow = FlowDefinition(
            uuid="flow-1",
            name=FlowIdentity(name="TestFlow", path="/test", uuid="flow-1"),
            compiled_sources=[SourceText(name="main.afl", content="facet Foo()", language="afl")],
        )
        store.save_flow(flow)

        resp = tc.get("/flows/flow-1/source")
        assert resp.status_code == 200
        assert "facet Foo()" in resp.text

    def test_flow_source_not_found(self, client):
        tc, store = client
        resp = tc.get("/flows/nonexistent/source")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_flow_json_with_valid_afl(self, client):
        """Covers flows.py flow_json route — successful parse."""
        tc, store = client
        from afl.runtime.entities import FlowDefinition, FlowIdentity, SourceText

        flow = FlowDefinition(
            uuid="flow-1",
            name=FlowIdentity(name="TestFlow", path="/test", uuid="flow-1"),
            compiled_sources=[
                SourceText(name="main.afl", content="facet Bar(x: String)", language="afl")
            ],
        )
        store.save_flow(flow)

        resp = tc.get("/flows/flow-1/json")
        assert resp.status_code == 200
        assert "Bar" in resp.text
        assert "String" in resp.text

    def test_flow_json_with_parse_error(self, client):
        """Covers flows.py flow_json route — parse error path."""
        tc, store = client
        from afl.runtime.entities import FlowDefinition, FlowIdentity, SourceText

        flow = FlowDefinition(
            uuid="flow-1",
            name=FlowIdentity(name="BadFlow", path="/test", uuid="flow-1"),
            compiled_sources=[
                SourceText(name="bad.afl", content="this is not valid afl {{{{", language="afl")
            ],
        )
        store.save_flow(flow)

        resp = tc.get("/flows/flow-1/json")
        assert resp.status_code == 200
        assert "Parse Error" in resp.text or "Error" in resp.text

    def test_flow_json_not_found(self, client):
        tc, store = client
        resp = tc.get("/flows/nonexistent/json")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_flow_json_no_sources(self, client):
        """Covers flow_json when flow exists but has no compiled_sources."""
        tc, store = client
        from afl.runtime.entities import FlowDefinition, FlowIdentity

        flow = FlowDefinition(
            uuid="flow-1",
            name=FlowIdentity(name="EmptyFlow", path="/test", uuid="flow-1"),
        )
        store.save_flow(flow)

        resp = tc.get("/flows/flow-1/json")
        assert resp.status_code == 200
        assert "No compiled sources" in resp.text or "EmptyFlow" in resp.text


class TestServerRoutes:
    def test_server_list(self, client):
        tc, store = client
        resp = tc.get("/servers")
        assert resp.status_code == 200
        assert "Servers" in resp.text

    def test_server_list_with_data(self, client):
        tc, store = client
        from afl.runtime.entities import ServerDefinition, ServerState

        server = ServerDefinition(
            uuid="s-1",
            server_group="workers",
            service_name="afl",
            server_name="worker-01",
            state=ServerState.RUNNING,
        )
        store.save_server(server)

        resp = tc.get("/servers")
        assert resp.status_code == 200
        assert "worker-01" in resp.text


class TestTaskRoutes:
    def test_task_list(self, client):
        tc, store = client
        resp = tc.get("/tasks")
        assert resp.status_code == 200
        assert "Task" in resp.text

    def test_task_list_with_data(self, client):
        tc, store = client
        from afl.runtime.entities import TaskDefinition, TaskState

        task = TaskDefinition(
            uuid="task-1",
            name="SendEmail",
            runner_id="r-1",
            workflow_id="wf-1",
            flow_id="flow-1",
            step_id="step-1",
            task_list_name="email-tasks",
            state=TaskState.PENDING,
        )
        store.save_task(task)

        resp = tc.get("/tasks")
        assert resp.status_code == 200
        assert "SendEmail" in resp.text


class TestApiRoutes:
    def test_api_runners(self, client):
        tc, store = client
        resp = tc.get("/api/runners")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_api_runners_with_data(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.RUNNING,
        )
        store.save_runner(runner)

        resp = tc.get("/api/runners")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["uuid"] == "r-1"

    def test_api_runner_detail(self, client):
        tc, store = client
        from afl.runtime.entities import (
            RunnerDefinition,
            RunnerState,
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(
            uuid="wf-1",
            name="TestWF",
            namespace_id="ns-1",
            facet_id="f-1",
            flow_id="flow-1",
            starting_step="s-1",
            version="1.0",
        )
        runner = RunnerDefinition(
            uuid="r-1",
            workflow_id="wf-1",
            workflow=workflow,
            state=RunnerState.RUNNING,
        )
        store.save_runner(runner)

        resp = tc.get("/api/runners/r-1")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == "r-1"

    def test_api_runner_not_found(self, client):
        tc, store = client
        resp = tc.get("/api/runners/nonexistent")
        assert resp.status_code == 404

    def test_api_flows(self, client):
        tc, store = client
        resp = tc.get("/api/flows")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_api_servers(self, client):
        tc, store = client
        resp = tc.get("/api/servers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_api_step_not_found(self, client):
        tc, store = client
        resp = tc.get("/api/steps/nonexistent")
        assert resp.status_code == 404

    def test_api_step_detail_with_data(self, client):
        """Covers api.py api_step_detail success path and _step_dict."""
        tc, store = client
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import step_id, workflow_id

        sid = step_id()
        wid = workflow_id()
        step = StepDefinition(
            id=sid,
            workflow_id=wid,
            object_type="VariableAssignment",
            state="state.facet.initialization.Begin",
        )
        store.save_step(step)

        resp = tc.get(f"/api/steps/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sid
        assert data["object_type"] == "VariableAssignment"

    def test_api_runners_filter_by_state(self, client):
        """Covers api.py api_runners with state parameter."""
        tc, store = client
        from afl.runtime.entities import RunnerState

        store.save_runner(_make_runner("r-1", state=RunnerState.RUNNING))
        store.save_runner(_make_runner("r-2", state=RunnerState.COMPLETED))

        resp = tc.get("/api/runners?state=running")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["state"] == "running"

    def test_api_runners_partial(self, client):
        """Covers api.py api_runners with partial=true (htmx partial rendering)."""
        tc, store = client

        store.save_runner(_make_runner("r-1"))

        resp = tc.get("/api/runners?partial=true")
        assert resp.status_code == 200
        assert "r-1" in resp.text

    def test_api_runner_steps_json(self, client):
        """Covers api.py api_runner_steps JSON path."""
        tc, store = client
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import step_id as make_step_id

        wf = _make_workflow()
        runner = _make_runner("r-1", workflow=wf)
        store.save_runner(runner)

        sid = make_step_id()
        step = StepDefinition(
            id=sid,
            workflow_id=wf.uuid,
            object_type="VariableAssignment",
            state="state.facet.initialization.Begin",
        )
        store.save_step(step)

        resp = tc.get("/api/runners/r-1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["object_type"] == "VariableAssignment"

    def test_api_runner_steps_not_found(self, client):
        """Covers api.py api_runner_steps 404 path."""
        tc, store = client
        resp = tc.get("/api/runners/nonexistent/steps")
        assert resp.status_code == 404

    def test_api_runner_steps_partial(self, client):
        """Covers api.py api_runner_steps with partial=true."""
        tc, store = client
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import step_id as make_step_id

        wf = _make_workflow()
        runner = _make_runner("r-1", workflow=wf)
        store.save_runner(runner)

        sid = make_step_id()
        step = StepDefinition(
            id=sid,
            workflow_id=wf.uuid,
            object_type="VariableAssignment",
            state="state.facet.initialization.Begin",
        )
        store.save_step(step)

        resp = tc.get("/api/runners/r-1/steps?partial=true")
        assert resp.status_code == 200
        assert "VariableAssignment" in resp.text


def _make_handler(facet_name="ns.TestFacet", module_uri="my.handlers", entrypoint="handle"):
    from afl.runtime.entities import HandlerRegistration

    return HandlerRegistration(
        facet_name=facet_name,
        module_uri=module_uri,
        entrypoint=entrypoint,
        version="1.0.0",
        timeout_ms=30000,
    )


class TestHandlerRoutes:
    def test_handler_list_empty(self, client):
        tc, store = client
        resp = tc.get("/handlers")
        assert resp.status_code == 200
        assert "Handlers" in resp.text

    def test_handler_list_with_data(self, client):
        tc, store = client
        store.save_handler_registration(_make_handler())
        resp = tc.get("/handlers")
        assert resp.status_code == 200
        assert "ns.TestFacet" in resp.text

    def test_handler_detail(self, client):
        tc, store = client
        store.save_handler_registration(_make_handler())
        resp = tc.get("/handlers/ns.TestFacet")
        assert resp.status_code == 200
        assert "ns.TestFacet" in resp.text
        assert "my.handlers" in resp.text

    def test_handler_detail_not_found(self, client):
        tc, store = client
        resp = tc.get("/handlers/ns.Missing")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_delete_handler(self, client):
        tc, store = client
        store.save_handler_registration(_make_handler())
        resp = tc.post("/handlers/ns.TestFacet/delete", follow_redirects=False)
        assert resp.status_code == 303
        assert store.get_handler_registration("ns.TestFacet") is None

    def test_delete_handler_not_found(self, client):
        tc, store = client
        resp = tc.post("/handlers/ns.Missing/delete", follow_redirects=False)
        assert resp.status_code == 303

    def test_api_handlers_empty(self, client):
        tc, store = client
        resp = tc.get("/api/handlers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_api_handlers_with_data(self, client):
        tc, store = client
        store.save_handler_registration(_make_handler())
        resp = tc.get("/api/handlers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["facet_name"] == "ns.TestFacet"
        assert data[0]["module_uri"] == "my.handlers"

    def test_home_handler_count(self, client):
        tc, store = client
        store.save_handler_registration(_make_handler())
        resp = tc.get("/")
        assert resp.status_code == 200
        assert "Handlers" in resp.text


def _make_event(event_id="evt-1", step_id="step-1", workflow_id="wf-1", state="pending", event_type="afl:execute"):
    from afl.runtime.persistence import EventDefinition

    return EventDefinition(
        id=event_id,
        step_id=step_id,
        workflow_id=workflow_id,
        state=state,
        event_type=event_type,
        payload={"key": "value"},
    )


class TestEventRoutes:
    def test_event_list_empty(self, client):
        tc, store = client
        resp = tc.get("/events")
        assert resp.status_code == 200
        assert "Events" in resp.text

    def test_event_list_with_data(self, client):
        tc, store = client
        store.save_event(_make_event())
        resp = tc.get("/events")
        assert resp.status_code == 200
        assert "evt-1" in resp.text

    def test_event_detail(self, client):
        tc, store = client
        store.save_event(_make_event())
        resp = tc.get("/events/evt-1")
        assert resp.status_code == 200
        assert "evt-1" in resp.text
        assert "afl:execute" in resp.text

    def test_event_detail_not_found(self, client):
        tc, store = client
        resp = tc.get("/events/nonexistent")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_event_detail_shows_payload(self, client):
        tc, store = client
        store.save_event(_make_event())
        resp = tc.get("/events/evt-1")
        assert resp.status_code == 200
        assert "key" in resp.text

    def test_api_events_empty(self, client):
        tc, store = client
        resp = tc.get("/api/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_api_events_with_data(self, client):
        tc, store = client
        store.save_event(_make_event())
        resp = tc.get("/api/events")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "evt-1"
        assert data[0]["event_type"] == "afl:execute"
