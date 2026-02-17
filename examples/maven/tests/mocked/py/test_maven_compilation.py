"""Tests for the Maven runner example AFL files.

Verifies that the runner AFL files parse, validate, and compile correctly.
"""

from pathlib import Path

from afl.cli import main
from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

_AFL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "afl"


def _compile(*filenames: str) -> dict:
    """Compile one or more AFL files from the Maven example directory."""
    entries = []
    for i, name in enumerate(filenames):
        path = _AFL_DIR / name
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


def _collect_names(program: dict, key: str) -> list[str]:
    """Recursively collect names from a given node type across all namespaces."""
    names = []

    def _walk(node):
        for item in node.get(key, []):
            names.append(item["name"])
        for ns in node.get("namespaces", []):
            _walk(ns)

    _walk(program)
    return names


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
class TestMavenTypes:
    """Compilation tests for maven_types.afl."""

    def test_parse_types(self):
        """maven_types.afl parses and validates."""
        program = _compile("maven_types.afl")
        assert program["type"] == "Program"

    def test_all_schemas_present(self):
        """All 2 schemas are emitted."""
        program = _compile("maven_types.afl")
        schema_names = _collect_names(program, "schemas")
        expected = ["ExecutionResult", "PluginExecutionResult"]
        for name in expected:
            assert name in schema_names, f"Missing schema: {name}"
        assert len([n for n in schema_names if n in expected]) == 2


# ---------------------------------------------------------------------------
# Event Facets (runner)
# ---------------------------------------------------------------------------
class TestMavenEventFacets:
    """Compilation tests for runner event facet files."""

    def test_runner_facets(self):
        """maven_runner.afl compiles with types dependency."""
        program = _compile("maven_runner.afl", "maven_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        assert "RunMavenArtifact" in facet_names

    def test_runner_facet_params(self):
        """RunMavenArtifact has expected parameters."""
        program = _compile("maven_runner.afl", "maven_types.afl")
        # Find the event facet
        def _find_event_facet(node, name):
            for ef in node.get("eventFacets", []):
                if ef["name"] == name:
                    return ef
            for ns in node.get("namespaces", []):
                found = _find_event_facet(ns, name)
                if found:
                    return found
            return None
        ef = _find_event_facet(program, "RunMavenArtifact")
        assert ef is not None
        param_names = [p["name"] for p in ef["params"]]
        assert "step_id" in param_names
        assert "group_id" in param_names
        assert "artifact_id" in param_names
        assert "version" in param_names

    def test_run_maven_plugin_facet(self):
        """RunMavenPlugin event facet is present with expected params."""
        program = _compile("maven_runner.afl", "maven_types.afl")

        def _find_event_facet(node, name):
            for ef in node.get("eventFacets", []):
                if ef["name"] == name:
                    return ef
            for ns in node.get("namespaces", []):
                found = _find_event_facet(ns, name)
                if found:
                    return found
            return None

        ef = _find_event_facet(program, "RunMavenPlugin")
        assert ef is not None
        param_names = [p["name"] for p in ef["params"]]
        assert "workspace_path" in param_names
        assert "plugin_group_id" in param_names
        assert "plugin_artifact_id" in param_names
        assert "plugin_version" in param_names
        assert "goal" in param_names
