"""Tests for Maven handler dispatch adapter pattern.

Verifies that each Maven handler module's handle() function dispatches correctly
using the _facet_name key, that _DISPATCH dicts have the expected keys,
and that register_handlers() calls runner.register_handler the expected
number of times.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

MAVEN_DIR = str(Path(__file__).parent.parent / "examples" / "maven")


def _maven_import(module_name: str):
    """Import a Maven handlers submodule, ensuring correct sys.path."""
    if MAVEN_DIR in sys.path:
        sys.path.remove(MAVEN_DIR)
    sys.path.insert(0, MAVEN_DIR)

    full_name = f"handlers.{module_name}"

    # If module is already loaded from the right location, return it
    if full_name in sys.modules:
        mod = sys.modules[full_name]
        mod_file = getattr(mod, "__file__", "")
        if mod_file and "maven" in mod_file:
            return mod
        del sys.modules[full_name]

    # Ensure the handlers package itself is from maven
    if "handlers" in sys.modules:
        pkg = sys.modules["handlers"]
        pkg_file = getattr(pkg, "__file__", "")
        if pkg_file and "maven" not in pkg_file:
            stale = [k for k in sys.modules if k == "handlers" or k.startswith("handlers.")]
            for k in stale:
                del sys.modules[k]

    return importlib.import_module(full_name)


class TestMavenResolveHandlers:
    def test_dispatch_keys(self):
        mod = _maven_import("resolve_handlers")
        assert len(mod._DISPATCH) == 3
        assert "maven.resolve.ResolveDependencies" in mod._DISPATCH
        assert "maven.resolve.DownloadArtifact" in mod._DISPATCH
        assert "maven.resolve.AnalyzeDependencyTree" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _maven_import("resolve_handlers")
        result = mod.handle({"_facet_name": "maven.resolve.ResolveDependencies", "group_id": "com.example", "artifact_id": "app", "version": "1.0.0"})
        assert isinstance(result, dict)
        assert "info" in result

    def test_handle_unknown_facet(self):
        mod = _maven_import("resolve_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "maven.resolve.NonExistent"})

    def test_register_handlers(self):
        mod = _maven_import("resolve_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 3


class TestMavenBuildHandlers:
    def test_dispatch_keys(self):
        mod = _maven_import("build_handlers")
        assert len(mod._DISPATCH) == 4
        assert "maven.build.CompileProject" in mod._DISPATCH
        assert "maven.build.RunUnitTests" in mod._DISPATCH
        assert "maven.build.PackageArtifact" in mod._DISPATCH
        assert "maven.build.GenerateJavadoc" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _maven_import("build_handlers")
        result = mod.handle({"_facet_name": "maven.build.CompileProject", "workspace_path": "/ws"})
        assert isinstance(result, dict)
        assert "result" in result

    def test_handle_unknown_facet(self):
        mod = _maven_import("build_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "maven.build.NonExistent"})

    def test_register_handlers(self):
        mod = _maven_import("build_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 4


class TestMavenPublishHandlers:
    def test_dispatch_keys(self):
        mod = _maven_import("publish_handlers")
        assert len(mod._DISPATCH) == 3
        assert "maven.publish.DeployToRepository" in mod._DISPATCH
        assert "maven.publish.PublishSnapshot" in mod._DISPATCH
        assert "maven.publish.PromoteRelease" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _maven_import("publish_handlers")
        result = mod.handle({"_facet_name": "maven.publish.DeployToRepository", "artifact_path": "/tmp/app.jar", "repository_url": "https://repo.example.com"})
        assert isinstance(result, dict)
        assert "result" in result

    def test_handle_unknown_facet(self):
        mod = _maven_import("publish_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "maven.publish.NonExistent"})

    def test_register_handlers(self):
        mod = _maven_import("publish_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 3


class TestMavenQualityHandlers:
    def test_dispatch_keys(self):
        mod = _maven_import("quality_handlers")
        assert len(mod._DISPATCH) == 2
        assert "maven.quality.CheckstyleAnalysis" in mod._DISPATCH
        assert "maven.quality.DependencyCheck" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _maven_import("quality_handlers")
        result = mod.handle({"_facet_name": "maven.quality.CheckstyleAnalysis", "workspace_path": "/ws"})
        assert isinstance(result, dict)
        assert "report" in result

    def test_handle_unknown_facet(self):
        mod = _maven_import("quality_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "maven.quality.NonExistent"})

    def test_register_handlers(self):
        mod = _maven_import("quality_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 2


class TestMavenInitRegistryHandlers:
    def test_register_all_registry_handlers(self):
        mod = _maven_import("__init__")
        runner = MagicMock()
        mod.register_all_registry_handlers(runner)
        # 3 resolve + 4 build + 3 publish + 2 quality = 12
        assert runner.register_handler.call_count == 12
