"""Tests for catalog backup / restore / import (facetwork.catalog.backup)."""

import json

from facetwork.catalog import CatalogService, InMemoryCatalogStore, backup
from facetwork.runtime import MemoryStore

WF = """namespace claude.demo {
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


class _FlowStore(MemoryStore):
    """MemoryStore + in-memory flow/workflow CRUD (Mongo-only in prod)."""

    def __init__(self):
        super().__init__()
        self._flow_defs = {}
        self._wf_defs = {}

    def save_flow(self, flow):
        self._flow_defs[flow.uuid] = flow

    def get_flow(self, flow_id):
        return self._flow_defs.get(flow_id)

    def save_workflow(self, wf):
        self._wf_defs[wf.uuid] = wf

    def get_workflow(self, workflow_id):
        return self._wf_defs.get(workflow_id)


def _svc():
    return CatalogService(InMemoryCatalogStore(), _FlowStore())


def _seed_full(svc):
    """A library + a workflow depending on it + a standalone published workflow."""
    svc.save("lib.geo", kind="library", ffl_source=LIB)
    svc.publish("lib.geo")
    svc.save("demo.find", ffl_source=DEP_WF, depends_on=[{"slug": "lib.geo"}])
    svc.save("demo.adder", ffl_source=WF, title="Adder", tags=["math"])
    svc.publish("demo.adder")


def test_export_shape():
    svc = _svc()
    _seed_full(svc)
    data = backup.export(svc)
    assert data["format"] == "facetwork-catalog-backup"
    slugs = {e["slug"] for e in data["entries"]}
    assert slugs == {"lib.geo", "demo.find", "demo.adder"}
    # revisions carry the FFL + pins (the source of truth)
    adder = next(r for r in data["revisions"] if r["slug"] == "demo.adder")
    assert "namespace claude.demo" in adder["ffl_source"] and adder["status"] == "published"
    find = next(r for r in data["revisions"] if r["slug"] == "demo.find")
    assert find["depends_on"] and find["depends_on"][0]["slug"] == "lib.geo"


def test_backup_restore_roundtrip_into_fresh_db():
    src = _svc()
    _seed_full(src)
    data = backup.export(src)

    # Fresh, empty catalog + flow store (simulates a wiped dev DB).
    dst = _svc()
    res = backup.restore(data, dst)
    assert res["entries"] == 3 and res["rematerialized"] == 3 and not res["failed"]

    # Identity preserved: revision_id, version, content_hash, status, pins.
    src_adder = src._catalog.get_revision_by_version("demo.adder", 1)
    dst_adder = dst._catalog.get_revision_by_version("demo.adder", 1)
    assert dst_adder.revision_id == src_adder.revision_id
    assert dst_adder.content_hash == src_adder.content_hash
    assert dst_adder.status == "published"  # publish state survived
    dst_find = dst._catalog.get_revision_by_version("demo.find", 1)
    assert dst_find.depends_on[0].slug == "lib.geo"

    # Flows were rebuilt in the fresh DB and are runnable (publish gate honored).
    assert dst._flows.get_flow(dst_adder.flow_id) is not None
    run = dst.run("demo.adder", inputs={"a": 4, "b": 6})
    assert run["version"] == 1 and run["workflow"] == "claude.demo.Adder"


def test_restore_from_file(tmp_path):
    src = _svc()
    _seed_full(src)
    path = tmp_path / "catalog.json"
    summary = backup.export_to_file(src, path)
    assert summary["entries"] == 3
    assert json.loads(path.read_text())["format"] == "facetwork-catalog-backup"

    dst = _svc()
    res = backup.restore_from_file(path, dst)
    assert res["entries"] == 3 and res["rematerialized"] == 3
    assert dst.get("demo.adder")["status"] == "published"


def test_import_ffl_file(tmp_path):
    svc = _svc()
    f = tmp_path / "adder.ffl"
    f.write_text(WF)
    results = backup.import_files(svc, [str(f)], slug="demo.adder", tags=["math"], publish=True)
    assert len(results) == 1
    _, res = results[0]
    assert res.ok and res.is_valid and res.status == "published"
    # Imported and immediately runnable (published).
    assert svc.run("demo.adder", inputs={"a": 1, "b": 1})["version"] == 1


def test_import_directory_derives_slugs(tmp_path):
    svc = _svc()
    (tmp_path / "adder.ffl").write_text(WF)
    (tmp_path / "geo_lib.ffl").write_text(LIB)
    results = backup.import_files(svc, [str(tmp_path)], kind="workflow")
    imported = {res.slug for _, res in results}
    assert "adder" in imported and "geo-lib" in imported  # stem, _ -> -


def test_restore_is_idempotent():
    src = _svc()
    _seed_full(src)
    data = backup.export(src)
    dst = _svc()
    backup.restore(data, dst)
    r2 = backup.restore(data, dst)  # again
    assert r2["entries"] == 3
    # still exactly one revision per (slug, version)
    assert len(dst._catalog.get_revisions_for_slug("demo.adder")) == 1
