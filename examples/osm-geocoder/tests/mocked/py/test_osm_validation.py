"""Tests for the OSM cache validation AFL file.

Verifies that osmvalidation.afl parses, validates, and compiles correctly,
and that the composed workflow in osmworkflows_composed.afl using the
validation facets also compiles.
"""

from pathlib import Path

from afl.cli import main
from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

_OSM_AFL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "afl"


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


class TestOsmValidationCompilation:
    """Compilation tests for osmvalidation.afl."""

    def test_parse_osmvalidation(self):
        """osmvalidation.afl parses and validates with its dependency."""
        program = _compile("osmvalidation.afl", "osmtypes.afl")
        assert program["type"] == "Program"

    def test_validation_namespace_exists(self):
        """The Validation namespace is emitted."""
        program = _compile("osmvalidation.afl", "osmtypes.afl")

        ns_names = []

        def _collect_ns(node, prefix=""):
            name = node.get("name", "")
            full = f"{prefix}.{name}" if prefix else name
            ns_names.append(full)
            for child in node.get("namespaces", []):
                _collect_ns(child, full)

        for ns in program.get("namespaces", []):
            _collect_ns(ns)

        assert any("Validation" in n for n in ns_names)

    def test_validation_schemas(self):
        """Both schemas (ValidationStats, ValidationResult) are emitted."""
        program = _compile("osmvalidation.afl", "osmtypes.afl")

        schema_names = []

        def _collect_schemas(node):
            for s in node.get("schemas", []):
                schema_names.append(s["name"])
            for ns in node.get("namespaces", []):
                _collect_schemas(ns)

        _collect_schemas(program)

        assert "ValidationStats" in schema_names
        assert "ValidationResult" in schema_names

    def test_validation_event_facets(self):
        """All five event facets are emitted."""
        program = _compile("osmvalidation.afl", "osmtypes.afl")

        facet_names = []

        def _collect_facets(node):
            for f in node.get("eventFacets", []):
                facet_names.append(f["name"])
            for ns in node.get("namespaces", []):
                _collect_facets(ns)

        _collect_facets(program)

        assert "ValidateCache" in facet_names
        assert "ValidateGeometry" in facet_names
        assert "ValidateTags" in facet_names
        assert "ValidateBounds" in facet_names
        assert "ValidationSummary" in facet_names

    def test_validate_cache_params(self):
        """ValidateCache has the expected parameters with defaults."""
        program = _compile("osmvalidation.afl", "osmtypes.afl")

        facet = None

        def _find_facet(node):
            nonlocal facet
            for f in node.get("eventFacets", []):
                if f["name"] == "ValidateCache":
                    facet = f
                    return
            for ns in node.get("namespaces", []):
                _find_facet(ns)

        _find_facet(program)

        assert facet is not None
        param_names = [p["name"] for p in facet["params"]]
        assert "cache" in param_names
        assert "output_dir" in param_names
        assert "use_hdfs" in param_names

    def test_validate_bounds_defaults(self):
        """ValidateBounds has lat/lon defaults."""
        program = _compile("osmvalidation.afl", "osmtypes.afl")

        facet = None

        def _find_facet(node):
            nonlocal facet
            for f in node.get("eventFacets", []):
                if f["name"] == "ValidateBounds":
                    facet = f
                    return
            for ns in node.get("namespaces", []):
                _find_facet(ns)

        _find_facet(program)

        assert facet is not None
        param_names = [p["name"] for p in facet["params"]]
        assert "min_lat" in param_names
        assert "max_lat" in param_names
        assert "min_lon" in param_names
        assert "max_lon" in param_names

    def test_cli_check_osmvalidation(self, tmp_path):
        """The CLI --check flag succeeds for osmvalidation.afl."""
        result = main([
            "--primary", str(_OSM_AFL_DIR / "osmvalidation.afl"),
            "--library", str(_OSM_AFL_DIR / "osmtypes.afl"),
            "--check",
        ])
        assert result == 0


class TestComposedValidationWorkflow:
    """Tests for the Pattern 11 composed workflow."""

    def test_compile_validate_and_summarize(self):
        """The ValidateAndSummarize workflow compiles with all dependencies."""
        # Collect all AFL files needed (the composed workflows reference many namespaces)
        all_afl = sorted(_OSM_AFL_DIR.glob("*.afl"))
        filenames = [f.name for f in all_afl]

        # Put osmworkflows_composed.afl first as primary
        filenames.remove("osmworkflows_composed.afl")
        filenames.insert(0, "osmworkflows_composed.afl")

        program = _compile(*filenames)

        # Find the ValidateAndSummarize workflow
        workflow = None

        def _find_wf(node):
            nonlocal workflow
            for wf in node.get("workflows", []):
                if wf["name"] == "ValidateAndSummarize":
                    workflow = wf
                    return
            for ns in node.get("namespaces", []):
                _find_wf(ns)

        _find_wf(program)

        assert workflow is not None
        assert workflow["name"] == "ValidateAndSummarize"

        # Should have 3 steps: cache, validation, summary
        steps = workflow["body"]["steps"]
        assert len(steps) == 3
        step_names = [s["name"] for s in steps]
        assert "cache" in step_names
        assert "validation" in step_names
        assert "summary" in step_names
