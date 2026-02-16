"""Tests for the Maven build lifecycle example AFL files.

Verifies that all 8 AFL files parse, validate, and compile correctly,
and that the 5 workflow pipelines using mixin composition compile with
all dependencies.
"""

from pathlib import Path

from afl.cli import main
from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

_AFL_DIR = Path(__file__).resolve().parent.parent / "examples" / "maven" / "afl"


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
        """All 9 schemas are emitted."""
        program = _compile("maven_types.afl")
        schema_names = _collect_names(program, "schemas")
        expected = [
            "ArtifactInfo", "DependencyTree", "BuildResult", "TestReport",
            "PublishResult", "QualityReport", "ProjectInfo", "ExecutionResult",
            "PluginExecutionResult",
        ]
        for name in expected:
            assert name in schema_names, f"Missing schema: {name}"
        assert len([n for n in schema_names if n in expected]) == 9


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------
class TestMavenMixins:
    """Compilation tests for maven_mixins.afl."""

    def test_parse_mixins(self):
        """maven_mixins.afl parses and validates."""
        program = _compile("maven_mixins.afl")
        assert program["type"] == "Program"

    def test_mixin_facets_present(self):
        """All 6 mixin facets are emitted."""
        program = _compile("maven_mixins.afl")
        facet_names = _collect_names(program, "facets")
        expected = ["Retry", "Timeout", "Repository", "Profile",
                     "JvmArgs", "Settings"]
        for name in expected:
            assert name in facet_names, f"Missing mixin facet: {name}"

    def test_implicits_present(self):
        """All 3 implicit declarations are emitted."""
        program = _compile("maven_mixins.afl")
        implicit_names = _collect_names(program, "implicits")
        expected = ["defaultRetry", "defaultTimeout", "defaultRepository"]
        for name in expected:
            assert name in implicit_names, f"Missing implicit: {name}"


# ---------------------------------------------------------------------------
# Event Facets (domain files)
# ---------------------------------------------------------------------------
class TestMavenEventFacets:
    """Compilation tests for domain event facet files."""

    def test_resolve_facets(self):
        """maven_resolve.afl compiles with types dependency."""
        program = _compile("maven_resolve.afl", "maven_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["ResolveDependencies", "DownloadArtifact", "AnalyzeDependencyTree"]
        for name in expected:
            assert name in facet_names, f"Missing resolve facet: {name}"
        assert len([n for n in facet_names if n in expected]) == 3

    def test_build_facets(self):
        """maven_build.afl compiles with types dependency."""
        program = _compile("maven_build.afl", "maven_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["CompileProject", "RunUnitTests", "PackageArtifact", "GenerateJavadoc"]
        for name in expected:
            assert name in facet_names, f"Missing build facet: {name}"

    def test_publish_facets(self):
        """maven_publish.afl compiles with types dependency."""
        program = _compile("maven_publish.afl", "maven_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["DeployToRepository", "PublishSnapshot", "PromoteRelease"]
        for name in expected:
            assert name in facet_names, f"Missing publish facet: {name}"

    def test_quality_facets(self):
        """maven_quality.afl compiles with types dependency."""
        program = _compile("maven_quality.afl", "maven_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["CheckstyleAnalysis", "DependencyCheck"]
        for name in expected:
            assert name in facet_names, f"Missing quality facet: {name}"

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


# ---------------------------------------------------------------------------
# Workflows (with mixin composition)
# ---------------------------------------------------------------------------
class TestMavenWorkflows:
    """Compilation tests for maven_workflows.afl with mixin composition."""

    _DEPS = [
        "maven_types.afl",
        "maven_mixins.afl",
        "maven_resolve.afl",
        "maven_build.afl",
        "maven_publish.afl",
        "maven_quality.afl",
        "maven_runner.afl",
    ]

    def _compile_workflows(self) -> dict:
        return _compile("maven_workflows.afl", *self._DEPS)

    def test_workflows_compile(self):
        """maven_workflows.afl compiles with all dependencies."""
        program = self._compile_workflows()
        assert program["type"] == "Program"

    def test_all_workflows_present(self):
        """All 5 workflow names are emitted."""
        program = self._compile_workflows()
        wf_names = _collect_names(program, "workflows")
        expected = ["BuildAndTest", "ReleaseArtifact",
                     "DependencyAudit", "MultiModuleBuild",
                     "RunArtifactPipeline"]
        for name in expected:
            assert name in wf_names, f"Missing workflow: {name}"

    def test_build_and_test_steps(self):
        """BuildAndTest has the expected step names."""
        program = self._compile_workflows()
        wf = self._find_workflow(program, "BuildAndTest")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "deps" in step_names
        assert "build" in step_names
        assert "tests" in step_names
        assert "pkg" in step_names

    def test_multi_module_foreach(self):
        """MultiModuleBuild uses foreach iteration."""
        program = self._compile_workflows()
        wf = self._find_workflow(program, "MultiModuleBuild")
        assert wf is not None
        body = wf["body"]
        foreach = body.get("foreach")
        assert foreach is not None
        assert foreach["variable"] == "mod"

    def test_release_artifact_steps(self):
        """ReleaseArtifact has all expected steps."""
        program = self._compile_workflows()
        wf = self._find_workflow(program, "ReleaseArtifact")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "deps" in step_names
        assert "build" in step_names
        assert "tests" in step_names
        assert "pkg" in step_names
        assert "deploy" in step_names

    def test_run_artifact_pipeline_steps(self):
        """RunArtifactPipeline has the expected step names."""
        program = self._compile_workflows()
        wf = self._find_workflow(program, "RunArtifactPipeline")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "deps" in step_names
        assert "run" in step_names

    def test_cli_check_workflows(self):
        """The CLI --check flag succeeds for maven_workflows.afl."""
        args = [
            "--primary", str(_AFL_DIR / "maven_workflows.afl"),
        ]
        for dep in self._DEPS:
            args.extend(["--library", str(_AFL_DIR / dep)])
        args.append("--check")
        result = main(args)
        assert result == 0

    @staticmethod
    def _find_workflow(program: dict, name: str) -> dict | None:
        """Find a workflow by name in the emitted program."""
        def _walk(node):
            for wf in node.get("workflows", []):
                if wf["name"] == name:
                    return wf
            for ns in node.get("namespaces", []):
                found = _walk(ns)
                if found:
                    return found
            return None
        return _walk(program)


# ---------------------------------------------------------------------------
# Orchestrator workflows (workflow-as-step)
# ---------------------------------------------------------------------------
class TestMavenOrchestratorWorkflows:
    """Compilation tests for maven_orchestrator.afl with workflow-as-step."""

    _ALL_DEPS = [
        "maven_types.afl",
        "maven_mixins.afl",
        "maven_resolve.afl",
        "maven_build.afl",
        "maven_publish.afl",
        "maven_quality.afl",
        "maven_runner.afl",
        "maven_workflows.afl",
    ]

    def _compile_orchestrator(self) -> dict:
        return _compile("maven_orchestrator.afl", *self._ALL_DEPS)

    def test_orchestrator_compiles(self):
        """maven_orchestrator.afl parses and validates with all deps."""
        program = self._compile_orchestrator()
        assert program["type"] == "Program"

    def test_both_workflows_present(self):
        """BuildTestAndRun and PluginVerifyAndRun are emitted."""
        program = self._compile_orchestrator()
        wf_names = _collect_names(program, "workflows")
        assert "BuildTestAndRun" in wf_names
        assert "PluginVerifyAndRun" in wf_names

    def test_build_test_and_run_steps(self):
        """BuildTestAndRun has steps build and run."""
        program = self._compile_orchestrator()
        wf = self._find_workflow(program, "BuildTestAndRun")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "build" in step_names
        assert "run" in step_names

    def test_plugin_verify_and_run_steps(self):
        """PluginVerifyAndRun has steps checkstyle, spotbugs, run."""
        program = self._compile_orchestrator()
        wf = self._find_workflow(program, "PluginVerifyAndRun")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "checkstyle" in step_names
        assert "spotbugs" in step_names
        assert "run" in step_names

    def test_build_test_and_run_returns(self):
        """BuildTestAndRun yield has expected return field names."""
        program = self._compile_orchestrator()
        wf = self._find_workflow(program, "BuildTestAndRun")
        assert wf is not None
        ret_names = [r["name"] for r in wf["returns"]]
        assert "artifact_path" in ret_names
        assert "test_passed" in ret_names
        assert "run_success" in ret_names
        assert "run_exit_code" in ret_names

    def test_plugin_verify_and_run_returns(self):
        """PluginVerifyAndRun yield has expected return field names."""
        program = self._compile_orchestrator()
        wf = self._find_workflow(program, "PluginVerifyAndRun")
        assert wf is not None
        ret_names = [r["name"] for r in wf["returns"]]
        assert "checkstyle_success" in ret_names
        assert "spotbugs_success" in ret_names
        assert "run_success" in ret_names
        assert "run_exit_code" in ret_names

    def test_plugin_verify_steps_have_mixins(self):
        """Checkstyle and spotbugs steps have Timeout mixins."""
        program = self._compile_orchestrator()
        wf = self._find_workflow(program, "PluginVerifyAndRun")
        assert wf is not None
        for step in wf["body"]["steps"]:
            if step["name"] in ("checkstyle", "spotbugs"):
                call_mixins = step.get("call", {}).get("mixins", [])
                assert len(call_mixins) > 0, (
                    f"Step {step['name']} should have mixins"
                )

    def test_cli_check_orchestrator(self):
        """The CLI --check flag succeeds for maven_orchestrator.afl."""
        args = [
            "--primary", str(_AFL_DIR / "maven_orchestrator.afl"),
        ]
        for dep in self._ALL_DEPS:
            args.extend(["--library", str(_AFL_DIR / dep)])
        args.append("--check")
        result = main(args)
        assert result == 0

    @staticmethod
    def _find_workflow(program: dict, name: str) -> dict | None:
        """Find a workflow by name in the emitted program."""
        def _walk(node):
            for wf in node.get("workflows", []):
                if wf["name"] == name:
                    return wf
            for ns in node.get("namespaces", []):
                found = _walk(ns)
                if found:
                    return found
            return None
        return _walk(program)
