"""Tests for the Jenkins CI/CD example AFL files.

Verifies that all 9 AFL files parse, validate, and compile correctly,
and that the 4 workflow pipelines using mixin composition compile with
all dependencies.
"""

from pathlib import Path

from afl.cli import main
from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

_AFL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "afl"


def _compile(*filenames: str) -> dict:
    """Compile one or more AFL files from the Jenkins example directory."""
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
class TestJenkinsTypes:
    """Compilation tests for jenkins_types.afl."""

    def test_parse_types(self):
        """jenkins_types.afl parses and validates."""
        program = _compile("jenkins_types.afl")
        assert program["type"] == "Program"

    def test_all_schemas_present(self):
        """All 7 schemas are emitted."""
        program = _compile("jenkins_types.afl")
        schema_names = _collect_names(program, "schemas")
        expected = [
            "ScmInfo", "BuildResult", "TestReport", "QualityReport",
            "Artifact", "DeployResult", "PipelineStatus",
        ]
        for name in expected:
            assert name in schema_names, f"Missing schema: {name}"
        assert len([n for n in schema_names if n in expected]) == 7


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------
class TestJenkinsMixins:
    """Compilation tests for jenkins_mixins.afl."""

    def test_parse_mixins(self):
        """jenkins_mixins.afl parses and validates."""
        program = _compile("jenkins_mixins.afl")
        assert program["type"] == "Program"

    def test_mixin_facets_present(self):
        """All 6 mixin facets are emitted."""
        program = _compile("jenkins_mixins.afl")
        facet_names = _collect_names(program, "facets")
        expected = ["Retry", "Timeout", "Credentials", "Notification",
                     "AgentLabel", "Stash"]
        for name in expected:
            assert name in facet_names, f"Missing mixin facet: {name}"

    def test_implicits_present(self):
        """All 3 implicit declarations are emitted."""
        program = _compile("jenkins_mixins.afl")
        implicit_names = _collect_names(program, "implicits")
        expected = ["defaultRetry", "defaultTimeout", "defaultAgent"]
        for name in expected:
            assert name in implicit_names, f"Missing implicit: {name}"


# ---------------------------------------------------------------------------
# Event Facets (domain files)
# ---------------------------------------------------------------------------
class TestJenkinsEventFacets:
    """Compilation tests for domain event facet files."""

    def test_scm_facets(self):
        """jenkins_scm.afl compiles with types and mixins dependencies."""
        program = _compile("jenkins_scm.afl", "jenkins_types.afl", "jenkins_mixins.afl")
        facet_names = _collect_names(program, "eventFacets")
        assert "GitCheckout" in facet_names
        assert "GitMerge" in facet_names
        assert len([n for n in facet_names if n in ("GitCheckout", "GitMerge")]) == 2

    def test_build_facets(self):
        """jenkins_build.afl compiles with types dependency."""
        program = _compile("jenkins_build.afl", "jenkins_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["MavenBuild", "GradleBuild", "NpmBuild", "DockerBuild"]
        for name in expected:
            assert name in facet_names, f"Missing build facet: {name}"

    def test_test_facets(self):
        """jenkins_test.afl compiles with types dependency."""
        program = _compile("jenkins_test.afl", "jenkins_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["RunTests", "CodeQuality", "SecurityScan"]
        for name in expected:
            assert name in facet_names, f"Missing test facet: {name}"

    def test_artifact_facets(self):
        """jenkins_artifacts.afl compiles with types dependency."""
        program = _compile("jenkins_artifacts.afl", "jenkins_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["ArchiveArtifacts", "PublishToRegistry", "DockerPush"]
        for name in expected:
            assert name in facet_names, f"Missing artifact facet: {name}"

    def test_deploy_facets(self):
        """jenkins_deploy.afl compiles with types dependency."""
        program = _compile("jenkins_deploy.afl", "jenkins_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["DeployToEnvironment", "DeployToK8s", "RollbackDeploy"]
        for name in expected:
            assert name in facet_names, f"Missing deploy facet: {name}"

    def test_notify_facets(self):
        """jenkins_notify.afl compiles with types dependency."""
        program = _compile("jenkins_notify.afl", "jenkins_types.afl")
        facet_names = _collect_names(program, "eventFacets")
        expected = ["SlackNotify", "EmailNotify"]
        for name in expected:
            assert name in facet_names, f"Missing notify facet: {name}"


# ---------------------------------------------------------------------------
# Pipelines (workflows with mixin composition)
# ---------------------------------------------------------------------------
class TestJenkinsPipelines:
    """Compilation tests for jenkins_pipelines.afl with mixin composition."""

    _DEPS = [
        "jenkins_types.afl",
        "jenkins_mixins.afl",
        "jenkins_scm.afl",
        "jenkins_build.afl",
        "jenkins_test.afl",
        "jenkins_artifacts.afl",
        "jenkins_deploy.afl",
        "jenkins_notify.afl",
    ]

    def _compile_pipelines(self) -> dict:
        return _compile("jenkins_pipelines.afl", *self._DEPS)

    def test_pipelines_compile(self):
        """jenkins_pipelines.afl compiles with all dependencies."""
        program = self._compile_pipelines()
        assert program["type"] == "Program"

    def test_all_workflows_present(self):
        """All 4 workflow names are emitted."""
        program = self._compile_pipelines()
        wf_names = _collect_names(program, "workflows")
        expected = ["JavaMavenCI", "DockerK8sDeploy",
                     "MultiModuleBuild", "FullCIPipeline"]
        for name in expected:
            assert name in wf_names, f"Missing workflow: {name}"

    def test_java_maven_ci_steps(self):
        """JavaMavenCI has the expected step names."""
        program = self._compile_pipelines()
        wf = self._find_workflow(program, "JavaMavenCI")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "src" in step_names
        assert "build" in step_names
        assert "tests" in step_names
        assert "deploy" in step_names

    def test_multi_module_foreach(self):
        """MultiModuleBuild uses foreach iteration."""
        program = self._compile_pipelines()
        wf = self._find_workflow(program, "MultiModuleBuild")
        assert wf is not None
        body = wf["body"]
        foreach = body.get("foreach")
        assert foreach is not None
        assert foreach["variable"] == "mod"

    def test_full_ci_pipeline_steps(self):
        """FullCIPipeline has all expected steps."""
        program = self._compile_pipelines()
        wf = self._find_workflow(program, "FullCIPipeline")
        assert wf is not None
        step_names = [s["name"] for s in wf["body"]["steps"]]
        assert "src" in step_names
        assert "build" in step_names
        assert "tests" in step_names
        assert "quality" in step_names
        assert "security" in step_names
        assert "archive" in step_names
        assert "deploy" in step_names
        assert "notify" in step_names

    def test_cli_check_pipelines(self):
        """The CLI --check flag succeeds for jenkins_pipelines.afl."""
        args = [
            "--primary", str(_AFL_DIR / "jenkins_pipelines.afl"),
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
