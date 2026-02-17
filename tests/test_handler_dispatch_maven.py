"""Tests for Maven handler dispatch adapter pattern.

Verifies that the runner handler module's handle() function dispatches correctly
using the _facet_name key, that _DISPATCH dict has the expected keys,
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


class TestMavenRunnerHandlers:
    def test_dispatch_keys(self):
        mod = _maven_import("runner_handlers")
        assert len(mod._DISPATCH) == 2
        assert "maven.runner.RunMavenArtifact" in mod._DISPATCH
        assert "maven.runner.RunMavenPlugin" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _maven_import("runner_handlers")
        result = mod.handle({"_facet_name": "maven.runner.RunMavenArtifact", "step_id": "step-1", "group_id": "com.example", "artifact_id": "app", "version": "1.0.0"})
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"]["success"] is True
        assert result["result"]["exit_code"] == 0

    def test_handle_plugin_dispatches(self):
        mod = _maven_import("runner_handlers")
        result = mod.handle({
            "_facet_name": "maven.runner.RunMavenPlugin",
            "workspace_path": "/tmp/ws",
            "plugin_group_id": "org.apache.maven.plugins",
            "plugin_artifact_id": "maven-checkstyle-plugin",
            "plugin_version": "3.3.1",
            "goal": "check",
        })
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"]["success"] is True
        assert result["result"]["exit_code"] == 0
        assert result["result"]["goal"] == "check"
        assert result["result"]["phase"] == "verify"

    def test_handle_unknown_facet(self):
        mod = _maven_import("runner_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "maven.runner.NonExistent"})

    def test_register_handlers(self):
        mod = _maven_import("runner_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 2


class TestMavenInitRegistryHandlers:
    def test_register_all_registry_handlers(self):
        mod = _maven_import("__init__")
        runner = MagicMock()
        mod.register_all_registry_handlers(runner)
        # 2 runner handlers only
        assert runner.register_handler.call_count == 2
