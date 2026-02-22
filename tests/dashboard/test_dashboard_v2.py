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

"""Tests for dashboard v2 helpers and routes."""

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


# ---------------------------------------------------------------------------
# Helper unit tests (no server needed)
# ---------------------------------------------------------------------------

from afl.dashboard.helpers import (
    categorize_step_state,
    extract_namespace,
    group_runners_by_namespace,
    short_workflow_name,
)


class TestExtractNamespace:
    def test_qualified_name(self):
        assert extract_namespace("osm.geo.Routes.BicycleRoutes") == "osm.geo.Routes"

    def test_simple_name(self):
        assert extract_namespace("SimpleWorkflow") == "(top-level)"

    def test_two_parts(self):
        assert extract_namespace("ns.Workflow") == "ns"

    def test_empty_string(self):
        assert extract_namespace("") == "(top-level)"

    def test_deeply_nested(self):
        assert extract_namespace("a.b.c.d.e.F") == "a.b.c.d.e"


class TestShortWorkflowName:
    def test_qualified_name(self):
        assert short_workflow_name("osm.geo.Routes.BicycleRoutes") == "BicycleRoutes"

    def test_simple_name(self):
        assert short_workflow_name("SimpleWorkflow") == "SimpleWorkflow"

    def test_two_parts(self):
        assert short_workflow_name("ns.Workflow") == "Workflow"


class TestCategorizeStepState:
    def test_complete(self):
        assert categorize_step_state("state.statement.Complete") == "complete"

    def test_error(self):
        assert categorize_step_state("state.statement.Error") == "error"

    def test_created(self):
        assert categorize_step_state("state.statement.Created") == "running"

    def test_event_transmit(self):
        assert categorize_step_state("state.EventTransmit") == "running"

    def test_block_begin(self):
        assert categorize_step_state("state.block.execution.Begin") == "running"


class TestGroupRunnersByNamespace:
    def _make_runner(self, name, state="running"):
        """Create a minimal runner-like object for grouping tests."""
        from types import SimpleNamespace

        return SimpleNamespace(
            uuid=f"r-{name}",
            workflow=SimpleNamespace(name=name),
            state=state,
        )

    def test_groups_by_namespace(self):
        runners = [
            self._make_runner("osm.geo.BicycleRoutes"),
            self._make_runner("osm.geo.WalkingRoutes"),
            self._make_runner("aws.Lambda"),
        ]
        groups = group_runners_by_namespace(runners)
        assert len(groups) == 2
        assert groups[0]["namespace"] == "aws"
        assert groups[0]["total"] == 1
        assert groups[1]["namespace"] == "osm.geo"
        assert groups[1]["total"] == 2

    def test_top_level(self):
        runners = [self._make_runner("SimpleWorkflow")]
        groups = group_runners_by_namespace(runners)
        assert len(groups) == 1
        assert groups[0]["namespace"] == "(top-level)"

    def test_empty(self):
        groups = group_runners_by_namespace([])
        assert groups == []

    def test_counts_by_state(self):
        runners = [
            self._make_runner("ns.A", "running"),
            self._make_runner("ns.B", "completed"),
            self._make_runner("ns.C", "running"),
        ]
        groups = group_runners_by_namespace(runners)
        assert groups[0]["counts"] == {"running": 2, "completed": 1}


# ---------------------------------------------------------------------------
# Route integration tests (require fastapi + mongomock)
# ---------------------------------------------------------------------------

pytestmark_routes = pytest.mark.skipif(
    not FASTAPI_AVAILABLE or not MONGOMOCK_AVAILABLE, reason="fastapi or mongomock not installed"
)


def _make_workflow(uuid="wf-1", name="osm.geo.TestWF"):
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


@pytest.fixture
def client():
    """Create a test client with mongomock-backed store."""
    from afl.dashboard import dependencies as deps
    from afl.dashboard.app import create_app
    from afl.runtime.mongo_store import MongoStore

    mock_client = mongomock.MongoClient()
    store = MongoStore(database_name="afl_test_v2", client=mock_client)

    app = create_app()
    app.dependency_overrides[deps.get_store] = lambda: store

    with TestClient(app) as tc:
        yield tc, store

    store.drop_database()
    store.close()


@pytestmark_routes
class TestV2WorkflowList:
    def test_workflow_list_empty(self, client):
        tc, store = client
        resp = tc.get("/v2/workflows", follow_redirects=False)
        assert resp.status_code == 200
        assert "Workflows" in resp.text

    def test_workflow_list_with_runners(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="running"))
        resp = tc.get("/v2/workflows?tab=running")
        assert resp.status_code == 200
        assert "osm.geo" in resp.text
        assert "TestWF" in resp.text

    def test_workflow_list_completed_tab(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="completed"))
        resp = tc.get("/v2/workflows?tab=completed")
        assert resp.status_code == 200
        assert "TestWF" in resp.text

    def test_workflow_list_failed_tab(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="failed"))
        resp = tc.get("/v2/workflows?tab=failed")
        assert resp.status_code == 200
        assert "TestWF" in resp.text

    def test_workflow_list_running_excludes_completed(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="completed"))
        resp = tc.get("/v2/workflows?tab=running")
        assert resp.status_code == 200
        assert "No workflows" in resp.text

    def test_workflow_list_partial(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="running"))
        resp = tc.get("/v2/workflows/partial?tab=running")
        assert resp.status_code == 200
        assert "osm.geo" in resp.text


@pytestmark_routes
class TestV2WorkflowDetail:
    def test_detail_not_found(self, client):
        tc, store = client
        resp = tc.get("/v2/workflows/nonexistent")
        assert resp.status_code == 200
        assert "Not Found" in resp.text

    def test_detail_with_runner(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="running"))
        resp = tc.get("/v2/workflows/r-1")
        assert resp.status_code == 200
        assert "TestWF" in resp.text

    def test_step_rows_partial(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="running"))
        resp = tc.get("/v2/workflows/r-1/steps/partial?step_tab=running")
        assert resp.status_code == 200

    def test_step_rows_partial_not_found(self, client):
        tc, store = client
        resp = tc.get("/v2/workflows/nonexistent/steps/partial?step_tab=running")
        assert resp.status_code == 200

    def test_step_expand(self, client):
        tc, store = client
        store.save_runner(_make_runner("r-1", state="running"))
        resp = tc.get("/v2/workflows/r-1/steps/some-step/expand")
        assert resp.status_code == 200


@pytestmark_routes
class TestHomeRedirect:
    def test_home_redirects_to_v2(self, client):
        tc, store = client
        resp = tc.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/v2/workflows"


@pytestmark_routes
class TestNavStructure:
    def test_nav_has_workflows_link(self, client):
        tc, store = client
        resp = tc.get("/v2/workflows")
        assert '/v2/workflows"' in resp.text

    def test_nav_has_servers_link(self, client):
        tc, store = client
        resp = tc.get("/v2/workflows")
        assert '/v2/servers"' in resp.text

    def test_nav_has_more_dropdown(self, client):
        tc, store = client
        resp = tc.get("/v2/workflows")
        assert "More" in resp.text
        assert "/handlers" in resp.text
        assert "/events" in resp.text
        assert "/tasks" in resp.text

    def test_old_runners_route_still_works(self, client):
        tc, store = client
        resp = tc.get("/runners")
        assert resp.status_code == 200
