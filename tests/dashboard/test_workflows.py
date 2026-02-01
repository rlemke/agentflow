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

"""Integration tests for dashboard workflow routes (new, compile, run)."""

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

    mock_client = mongomock.MongoClient()
    store = MongoStore(database_name="afl_test_workflows", client=mock_client)

    app = create_app()
    app.dependency_overrides[deps.get_store] = lambda: store

    with TestClient(app) as tc:
        yield tc, store

    store.drop_database()
    store.close()


VALID_AFL_SOURCE = """
facet Compute(input: Long)

workflow SimpleWF(x: Long) => (result: Long) andThen {
    s1 = Compute(input = $.x)
    yield SimpleWF(result = s1.input)
}
"""

MULTI_WORKFLOW_SOURCE = """
facet Compute(input: Long)

workflow WF_A(x: Long) => (result: Long) andThen {
    s1 = Compute(input = $.x)
    yield WF_A(result = s1.input)
}

workflow WF_B(y: String) => (out: String) andThen {
    s1 = Compute(input = 1)
    yield WF_B(out = "done")
}
"""

INVALID_AFL_SOURCE = "this is not valid AFL %%% syntax"


class TestWorkflowNew:
    """Tests for GET /workflows/new."""

    def test_new_page_renders(self, client):
        tc, store = client
        resp = tc.get("/workflows/new")
        assert resp.status_code == 200
        assert "New Workflow" in resp.text
        assert "<textarea" in resp.text

    def test_new_page_has_compile_form(self, client):
        tc, store = client
        resp = tc.get("/workflows/new")
        assert "/workflows/compile" in resp.text


class TestWorkflowCompile:
    """Tests for POST /workflows/compile."""

    def test_compile_valid_source(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/compile",
            data={"source": VALID_AFL_SOURCE},
        )
        assert resp.status_code == 200
        assert "SimpleWF" in resp.text
        assert "Run Workflow" in resp.text

    def test_compile_shows_params(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/compile",
            data={"source": VALID_AFL_SOURCE},
        )
        assert resp.status_code == 200
        assert "x" in resp.text
        assert "Long" in resp.text

    def test_compile_invalid_source(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/compile",
            data={"source": INVALID_AFL_SOURCE},
        )
        assert resp.status_code == 200
        # Should show error
        assert "Errors" in resp.text or "error" in resp.text.lower()

    def test_compile_multiple_workflows(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/compile",
            data={"source": MULTI_WORKFLOW_SOURCE},
        )
        assert resp.status_code == 200
        assert "WF_A" in resp.text
        assert "WF_B" in resp.text

    def test_compile_no_workflows(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/compile",
            data={"source": "facet Standalone(x: Long)"},
        )
        assert resp.status_code == 200
        assert "No workflows found" in resp.text


class TestWorkflowRun:
    """Tests for POST /workflows/run."""

    def test_run_creates_entities_and_redirects(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/run",
            data={
                "source": VALID_AFL_SOURCE,
                "workflow_name": "SimpleWF",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/runners/" in resp.headers["location"]

    def test_run_creates_flow(self, client):
        tc, store = client
        tc.post(
            "/workflows/run",
            data={
                "source": VALID_AFL_SOURCE,
                "workflow_name": "SimpleWF",
            },
            follow_redirects=False,
        )
        flows = store.get_all_flows()
        assert len(flows) == 1
        assert flows[0].name.name == "SimpleWF"
        assert len(flows[0].compiled_sources) == 1
        assert flows[0].compiled_sources[0].name == "source.afl"

    def test_run_creates_workflow(self, client):
        tc, store = client
        tc.post(
            "/workflows/run",
            data={
                "source": VALID_AFL_SOURCE,
                "workflow_name": "SimpleWF",
            },
            follow_redirects=False,
        )
        flows = store.get_all_flows()
        flow = flows[0]
        workflows = store.get_workflows_by_flow(flow.uuid)
        assert len(workflows) == 1
        assert workflows[0].name == "SimpleWF"

    def test_run_creates_runner(self, client):
        tc, store = client
        resp = tc.post(
            "/workflows/run",
            data={
                "source": VALID_AFL_SOURCE,
                "workflow_name": "SimpleWF",
            },
            follow_redirects=False,
        )
        # Extract runner_id from redirect URL
        location = resp.headers["location"]
        runner_id = location.split("/runners/")[1]
        runner = store.get_runner(runner_id)
        assert runner is not None
        assert runner.state == "created"

    def test_run_creates_task(self, client):
        tc, store = client
        tc.post(
            "/workflows/run",
            data={
                "source": VALID_AFL_SOURCE,
                "workflow_name": "SimpleWF",
            },
            follow_redirects=False,
        )
        tasks = store.get_pending_tasks("default")
        assert len(tasks) == 1
        assert tasks[0].name == "afl:execute"
        assert tasks[0].data["workflow_name"] == "SimpleWF"


class TestNavLink:
    """Tests for the navigation link."""

    def test_nav_has_new_link(self, client):
        tc, store = client
        resp = tc.get("/")
        assert resp.status_code == 200
        assert "/workflows/new" in resp.text
        assert ">New<" in resp.text
