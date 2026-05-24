"""Tests for the handler-gap scaffolder (facetwork.scaffold)."""

import json

import pytest

from facetwork.scaffold import (
    FacetSpec,
    detect_missing_facets,
    parse_pairs,
    scaffold_facet,
    scaffold_handler,
    scaffold_test,
)

WF = """namespace t {
    event facet DoX(a: String) => (b: String)
    workflow W(a: String = "x") => (b: String) andThen {
        d = DoX(a = $.a)
        yield W(b = d.b)
    }
}"""


def _program(src):
    from facetwork.ast import Program
    from facetwork.emitter import JSONEmitter
    from facetwork.parser import FFLParser

    merged = Program.merge([FFLParser().parse(src)])
    return json.loads(JSONEmitter(include_locations=False).emit(merged))


def test_parse_pairs():
    assert parse_pairs("a:String, b:Int") == [("a", "String"), ("b", "Int")]
    assert parse_pairs("x") == [("x", "String")]  # default type
    assert parse_pairs("") == []


def test_module_stem_is_acronym_aware():
    assert FacetSpec("osm.Filters.FilterGeoJSONByTagContains").module_stem == (
        "filter_geo_json_by_tag_contains_handler"
    )
    assert FacetSpec("ns.DoX").module_stem == "do_x_handler"


def test_detect_missing_facets():
    prog = _program(WF)
    # nothing registered -> the workflow's event facet is a gap
    assert detect_missing_facets(prog, "W", set()) == ["t.DoX"]
    # registered (qualified) -> no gap
    assert detect_missing_facets(prog, "W", {"t.DoX"}) == []
    # registered by short name -> no gap
    assert detect_missing_facets(prog, "W", {"DoX"}) == []


def test_scaffold_facet_declares_signature():
    spec = FacetSpec("ns.MyFilter", [("input_path", "String"), ("k", "String")], [("result", "R")])
    ffl = scaffold_facet(spec)
    assert "event facet MyFilter(input_path: String, k: String) => (result: R)" in ffl
    assert "namespace ns" in ffl  # placement hint


def test_scaffold_handler_is_valid_python_and_registers():
    spec = FacetSpec("ns.MyFilter", [("x", "String")], [("result", "R")])
    src = scaffold_handler(spec)
    ns: dict = {"__file__": "/tmp/my_filter_handler.py"}  # a real module has __file__
    exec(compile(src, "my_filter_handler.py", "exec"), ns)  # must be valid Python

    # body is a stub until implemented
    with pytest.raises(NotImplementedError):
        ns["handle"]({"x": "v"})

    # register_handlers wires the right facet name + entrypoint
    calls = []

    class _Runner:
        def register_handler(self, **kw):
            calls.append((kw["facet_name"], kw["entrypoint"]))

    ns["register_handlers"](_Runner())
    assert calls == [("ns.MyFilter", "handle")]


def test_scaffold_test_imports_the_handler_module():
    spec = FacetSpec("ns.MyFilter", [("x", "String")], [("result", "R")])
    t = scaffold_test(spec)
    assert "from my_filter_handler import handle" in t
    assert "NotImplementedError" in t
