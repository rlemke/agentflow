"""Dashboard catalog page tests (TestClient + mongomock)."""

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

ADDER = """namespace claude.demo {
    workflow Adder(a: Int = 2, b: Int = 3) => (sum: Int) andThen {
        yield Adder(sum = $.a + $.b)
    }
}"""

LIB = """namespace claude.lib.geo {
    schema Pt { lat: Double, lon: Double }
    event facet Locate(name: String) => (point: Pt)
}"""

DEP_WF = """namespace claude.demo2 {
    use claude.lib.geo
    workflow Find(name: String = "x") => (lat: Double) andThen {
        p = Locate(name = $.name)
        yield Find(lat = p.point.lat)
    }
}"""


@pytest.fixture
def client():
    from facetwork.dashboard import dependencies as deps
    from facetwork.dashboard.app import create_app
    from facetwork.runtime.mongo_store import MongoStore

    store = MongoStore(database_name="afl_test_catalog", client=mongomock.MongoClient())
    app = create_app()
    app.dependency_overrides[deps.get_store] = lambda: store
    with TestClient(app) as tc:
        yield tc, store
    store.drop_database()
    store.close()


def _seed(store, slug="demo.adder", publish=False):
    from facetwork.catalog import CatalogService, MongoCatalogStore

    svc = CatalogService(MongoCatalogStore(store._db), store)
    r = svc.save(slug, ffl_source=ADDER, title="Adder", description="adds two ints", tags=["math"])
    assert r.ok and r.is_valid, r
    if publish:
        svc.publish(slug)
    return svc


def test_catalog_list_renders_entry(client):
    tc, store = client
    _seed(store)
    r = tc.get("/catalog")
    assert r.status_code == 200
    assert "Catalog" in r.text and "demo.adder" in r.text


def test_catalog_page_links_to_docs(client):
    tc, store = client
    r = tc.get("/catalog")
    assert "docs/architecture/catalog-use-resolution.md" in r.text  # use-resolution doc
    assert "docs/architecture/claude-workflow-catalog.md" in r.text  # catalog overview doc


def test_render_summary_md_renders_subset_safely():
    from facetwork.dashboard.routes.execution.catalog import render_summary_md

    html = render_summary_md(
        "Built from a request.\n\n"
        "**Approach**:\n\n"
        "1. step `one`\n"
        "2. step *two*\n\n"
        "See [docs](https://example.com/x)."
    )
    assert "<strong>Approach</strong>" in html
    assert "<ol>" in html and "<li>step <code>one</code></li>" in html
    assert "<em>two</em>" in html
    assert '<a href="https://example.com/x" target="_blank" rel="noopener">docs</a>' in html
    # raw HTML is escaped (XSS-safe), markdown still applies around it
    evil = render_summary_md("<script>alert(1)</script> **bold**")
    assert "<script>" not in evil and "&lt;script&gt;" in evil
    assert "<strong>bold</strong>" in evil


def test_catalog_detail_renders_summary_markdown(client):
    tc, store = client
    from facetwork.catalog import CatalogService, MongoCatalogStore

    svc = CatalogService(MongoCatalogStore(store._db), store)
    svc.save(
        "demo.adder", ffl_source=ADDER, title="Adder",
        summary="**Why**: adds ints.\n\n1. take a\n2. take b",
    )
    body = tc.get("/catalog/demo.adder").text
    assert "<strong>Why</strong>" in body and "<ol>" in body


def test_catalog_detail_shows_authoring_summary(client):
    tc, store = client
    from facetwork.catalog import CatalogService, MongoCatalogStore

    svc = CatalogService(MongoCatalogStore(store._db), store)
    svc.save("demo.adder", ffl_source=ADDER, title="Adder",
             summary="Adds two integers; built from a calculator request.")
    body = tc.get("/catalog/demo.adder").text
    assert "Purpose" in body and "calculator request" in body


def test_catalog_detail_shows_ffl_params_and_run_form(client):
    tc, store = client
    _seed(store)
    r = tc.get("/catalog/demo.adder")
    assert r.status_code == 200
    assert "namespace claude.demo" in r.text  # FFL source rendered
    assert "claude.demo.Adder" in r.text  # entry workflow
    assert "draft" in r.text  # status
    assert "Run on the fleet" in r.text  # run form present


def test_publish_then_run_creates_bootstrap_task(client):
    tc, store = client
    _seed(store)
    rp = tc.post("/catalog/demo.adder/publish", data={"version": "1"}, follow_redirects=False)
    assert rp.status_code == 303 and rp.headers["location"] == "/catalog/demo.adder"
    assert "published" in tc.get("/catalog/demo.adder").text

    rr = tc.post(
        "/catalog/demo.adder/run",
        data={"version": "1", "inputs_json": '{"a": 10, "b": 5}'},
        follow_redirects=False,
    )
    assert rr.status_code == 303 and rr.headers["location"].startswith("/runners/")
    task = store._db.tasks.find_one({"name": "fw:execute:claude.demo.Adder"})
    assert task is not None and task["data"]["inputs"] == {"a": 10, "b": 5}


def test_run_draft_is_blocked_by_gate(client):
    tc, store = client
    _seed(store)  # draft, not published
    rr = tc.post(
        "/catalog/demo.adder/run",
        data={"version": "1", "inputs_json": "{}"},
        follow_redirects=False,
    )
    assert rr.status_code == 303
    assert "error" in rr.headers["location"]  # gate redirect, not a run
    assert store._db.tasks.find_one({"name": "fw:execute:claude.demo.Adder"}) is None


def test_publish_via_button_then_visible(client):
    tc, store = client
    _seed(store, publish=True)
    body = tc.get("/catalog/demo.adder").text
    assert "published" in body


def _seed_package(store):
    """A library + a workflow depending on it + a standalone workflow."""
    from facetwork.catalog import CatalogService, MongoCatalogStore

    svc = CatalogService(MongoCatalogStore(store._db), store)
    svc.save("lib.geo", kind="library", ffl_source=LIB, title="Geo lib", tags=["geo"])
    svc.publish("lib.geo")
    svc.save("demo.find", ffl_source=DEP_WF, depends_on=[{"slug": "lib.geo"}])
    svc.save("demo.adder", ffl_source=ADDER, title="Adder")
    return svc


def test_catalog_overview_groups_packages_and_standalone(client):
    tc, store = client
    _seed_package(store)
    body = tc.get("/catalog").text
    assert "Packages" in body  # libraries section heading
    assert "lib.geo" in body  # the library/package
    assert "Standalone workflows" in body
    assert "demo.adder" in body  # standalone listed
    # The dependent workflow is summarized as a package member, not in standalone.
    assert "?package=lib.geo" in body


def test_catalog_package_drilldown_lists_members(client):
    tc, store = client
    _seed_package(store)
    body = tc.get("/catalog?package=lib.geo").text
    assert "workflows in package" in body
    assert "demo.find" in body  # the member workflow
    assert "demo.adder" not in body  # standalone is not a member of lib.geo
