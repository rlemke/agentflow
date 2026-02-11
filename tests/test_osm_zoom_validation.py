"""Tests for the OSM zoom builder AFL file.

Verifies that osmzoombuilder.afl parses, validates, and compiles correctly,
and that the composed RoadZoomBuilder workflow in osmworkflows_composed.afl
also compiles with all dependencies.
"""

from pathlib import Path

from afl.cli import main
from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

_OSM_AFL_DIR = Path(__file__).resolve().parent.parent / "examples" / "osm-geocoder" / "afl"


def _compile(*filenames: str) -> dict:
    """Compile one or more AFL files from the OSM example directory."""
    entries = []
    for i, name in enumerate(filenames):
        path = _OSM_AFL_DIR / name
        entries.append(
            SourceEntry(
                text=path.read_text(),
                origin=FileOrigin(path=str(path)),
                is_library=(i > 0),
            )
        )

    compiler_input = CompilerInput(
        primary_sources=[entries[0]],
        library_sources=entries[1:],
    )

    parser = AFLParser()
    program_ast, _registry = parser.parse_sources(compiler_input)

    result = validate(program_ast)
    if result.errors:
        messages = "; ".join(str(e) for e in result.errors)
        raise ValueError(f"Validation errors: {messages}")

    return emit_dict(program_ast, include_locations=False)


class TestZoomBuilderCompilation:
    """Compilation tests for osmzoombuilder.afl."""

    def test_parse_osmzoombuilder(self):
        """osmzoombuilder.afl parses and validates with its dependency."""
        program = _compile("osmzoombuilder.afl", "osmtypes.afl")
        assert program["type"] == "Program"

    def test_zoombuilder_namespace_exists(self):
        """The ZoomBuilder namespace is emitted."""
        program = _compile("osmzoombuilder.afl", "osmtypes.afl")

        ns_names = []

        def _collect_ns(node, prefix=""):
            name = node.get("name", "")
            full = f"{prefix}.{name}" if prefix else name
            ns_names.append(full)
            for child in node.get("namespaces", []):
                _collect_ns(child, full)

        for ns in program.get("namespaces", []):
            _collect_ns(ns)

        assert any("ZoomBuilder" in n for n in ns_names)

    def test_zoombuilder_schemas(self):
        """All six schemas are emitted."""
        program = _compile("osmzoombuilder.afl", "osmtypes.afl")

        schema_names = []

        def _collect_schemas(node):
            for s in node.get("schemas", []):
                schema_names.append(s["name"])
            for ns in node.get("namespaces", []):
                _collect_schemas(ns)

        _collect_schemas(program)

        assert "LogicalEdge" in schema_names
        assert "ZoomEdgeResult" in schema_names
        assert "ZoomBuilderResult" in schema_names
        assert "ZoomBuilderMetrics" in schema_names
        assert "ZoomBuilderConfig" in schema_names
        assert "CellBudget" in schema_names

    def test_zoombuilder_event_facets(self):
        """All nine event facets are emitted."""
        program = _compile("osmzoombuilder.afl", "osmtypes.afl")

        facet_names = []

        def _collect_facets(node):
            for f in node.get("eventFacets", []):
                facet_names.append(f["name"])
            for ns in node.get("namespaces", []):
                _collect_facets(ns)

        _collect_facets(program)

        assert "BuildLogicalGraph" in facet_names
        assert "BuildAnchors" in facet_names
        assert "ComputeSBS" in facet_names
        assert "ComputeScores" in facet_names
        assert "DetectBypasses" in facet_names
        assert "DetectRings" in facet_names
        assert "SelectEdges" in facet_names
        assert "ExportZoomLayers" in facet_names
        assert "BuildZoomLayers" in facet_names

    def test_build_zoom_layers_params(self):
        """BuildZoomLayers has the expected parameters."""
        program = _compile("osmzoombuilder.afl", "osmtypes.afl")

        facet = None

        def _find_facet(node):
            nonlocal facet
            for f in node.get("eventFacets", []):
                if f["name"] == "BuildZoomLayers":
                    facet = f
                    return
            for ns in node.get("namespaces", []):
                _find_facet(ns)

        _find_facet(program)

        assert facet is not None
        param_names = [p["name"] for p in facet["params"]]
        assert "cache" in param_names
        assert "graph" in param_names
        assert "min_population" in param_names
        assert "output_dir" in param_names
        assert "max_concurrent" in param_names

    def test_build_zoom_layers_defaults(self):
        """BuildZoomLayers has correct default values."""
        program = _compile("osmzoombuilder.afl", "osmtypes.afl")

        facet = None

        def _find_facet(node):
            nonlocal facet
            for f in node.get("eventFacets", []):
                if f["name"] == "BuildZoomLayers":
                    facet = f
                    return
            for ns in node.get("namespaces", []):
                _find_facet(ns)

        _find_facet(program)

        assert facet is not None
        defaults = {p["name"]: p.get("default") for p in facet["params"] if "default" in p}
        assert "min_population" in defaults
        assert "output_dir" in defaults
        assert "max_concurrent" in defaults

    def test_cli_check_osmzoombuilder(self, tmp_path):
        """The CLI --check flag succeeds for osmzoombuilder.afl."""
        result = main([
            "--primary", str(_OSM_AFL_DIR / "osmzoombuilder.afl"),
            "--library", str(_OSM_AFL_DIR / "osmtypes.afl"),
            "--check",
        ])
        assert result == 0


class TestComposedZoomWorkflow:
    """Tests for the RoadZoomBuilder composed workflow."""

    def test_compile_all_afl_files(self):
        """All AFL files compile together without errors."""
        all_afl = sorted(_OSM_AFL_DIR.glob("*.afl"))
        filenames = [f.name for f in all_afl]

        # Put osmworkflows_composed.afl first as primary
        filenames.remove("osmworkflows_composed.afl")
        filenames.insert(0, "osmworkflows_composed.afl")

        program = _compile(*filenames)
        assert program["type"] == "Program"

    def test_road_zoom_builder_workflow(self):
        """The RoadZoomBuilder workflow compiles with 3 steps."""
        all_afl = sorted(_OSM_AFL_DIR.glob("*.afl"))
        filenames = [f.name for f in all_afl]

        filenames.remove("osmworkflows_composed.afl")
        filenames.insert(0, "osmworkflows_composed.afl")

        program = _compile(*filenames)

        workflow = None

        def _find_wf(node):
            nonlocal workflow
            for wf in node.get("workflows", []):
                if wf["name"] == "RoadZoomBuilder":
                    workflow = wf
                    return
            for ns in node.get("namespaces", []):
                _find_wf(ns)

        _find_wf(program)

        assert workflow is not None
        assert workflow["name"] == "RoadZoomBuilder"

        # Should have 3 steps: cache, graph, zoom
        steps = workflow["body"]["steps"]
        assert len(steps) == 3
        step_names = [s["name"] for s in steps]
        assert "cache" in step_names
        assert "graph" in step_names
        assert "zoom" in step_names
