"""Tests for Jenkins handler dispatch adapter pattern.

Verifies that each Jenkins handler module's handle() function dispatches correctly
using the _facet_name key, that _DISPATCH dicts have the expected keys,
and that register_handlers() calls runner.register_handler the expected
number of times.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

JENKINS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)


def _jenkins_import(module_name: str):
    """Import a Jenkins handlers submodule, ensuring correct sys.path."""
    if JENKINS_DIR in sys.path:
        sys.path.remove(JENKINS_DIR)
    sys.path.insert(0, JENKINS_DIR)

    full_name = f"handlers.{module_name}"

    # If module is already loaded from the right location, return it
    if full_name in sys.modules:
        mod = sys.modules[full_name]
        mod_file = getattr(mod, "__file__", "")
        if mod_file and "jenkins" in mod_file:
            return mod
        del sys.modules[full_name]

    # Ensure the handlers package itself is from jenkins
    if "handlers" in sys.modules:
        pkg = sys.modules["handlers"]
        pkg_file = getattr(pkg, "__file__", "")
        if pkg_file and "jenkins" not in pkg_file:
            stale = [k for k in sys.modules if k == "handlers" or k.startswith("handlers.")]
            for k in stale:
                del sys.modules[k]

    return importlib.import_module(full_name)


class TestJenkinsScmHandlers:
    def test_dispatch_keys(self):
        mod = _jenkins_import("scm_handlers")
        assert len(mod._DISPATCH) == 2
        assert "jenkins.scm.GitCheckout" in mod._DISPATCH
        assert "jenkins.scm.GitMerge" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _jenkins_import("scm_handlers")
        result = mod.handle({"_facet_name": "jenkins.scm.GitCheckout", "repo": "org/app", "branch": "main"})
        assert isinstance(result, dict)
        assert "info" in result

    def test_handle_unknown_facet(self):
        mod = _jenkins_import("scm_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "jenkins.scm.NonExistent"})

    def test_register_handlers(self):
        mod = _jenkins_import("scm_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 2


class TestJenkinsBuildHandlers:
    def test_dispatch_keys(self):
        mod = _jenkins_import("build_handlers")
        assert len(mod._DISPATCH) == 4
        assert "jenkins.build.MavenBuild" in mod._DISPATCH
        assert "jenkins.build.GradleBuild" in mod._DISPATCH
        assert "jenkins.build.NpmBuild" in mod._DISPATCH
        assert "jenkins.build.DockerBuild" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _jenkins_import("build_handlers")
        result = mod.handle({"_facet_name": "jenkins.build.MavenBuild", "workspace_path": "/ws"})
        assert isinstance(result, dict)
        assert "result" in result

    def test_handle_unknown_facet(self):
        mod = _jenkins_import("build_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "jenkins.build.NonExistent"})

    def test_register_handlers(self):
        mod = _jenkins_import("build_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 4


class TestJenkinsTestHandlers:
    def test_dispatch_keys(self):
        mod = _jenkins_import("test_handlers")
        assert len(mod._DISPATCH) == 3
        assert "jenkins.test.RunTests" in mod._DISPATCH
        assert "jenkins.test.CodeQuality" in mod._DISPATCH
        assert "jenkins.test.SecurityScan" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _jenkins_import("test_handlers")
        result = mod.handle({"_facet_name": "jenkins.test.RunTests", "workspace_path": "/ws"})
        assert isinstance(result, dict)
        assert "report" in result

    def test_handle_unknown_facet(self):
        mod = _jenkins_import("test_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "jenkins.test.NonExistent"})

    def test_register_handlers(self):
        mod = _jenkins_import("test_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 3


class TestJenkinsArtifactHandlers:
    def test_dispatch_keys(self):
        mod = _jenkins_import("artifact_handlers")
        assert len(mod._DISPATCH) == 3
        assert "jenkins.artifact.ArchiveArtifacts" in mod._DISPATCH
        assert "jenkins.artifact.PublishToRegistry" in mod._DISPATCH
        assert "jenkins.artifact.DockerPush" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _jenkins_import("artifact_handlers")
        result = mod.handle({"_facet_name": "jenkins.artifact.ArchiveArtifacts", "workspace_path": "/ws"})
        assert isinstance(result, dict)
        assert "artifact" in result

    def test_handle_unknown_facet(self):
        mod = _jenkins_import("artifact_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "jenkins.artifact.NonExistent"})

    def test_register_handlers(self):
        mod = _jenkins_import("artifact_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 3


class TestJenkinsDeployHandlers:
    def test_dispatch_keys(self):
        mod = _jenkins_import("deploy_handlers")
        assert len(mod._DISPATCH) == 3
        assert "jenkins.deploy.DeployToEnvironment" in mod._DISPATCH
        assert "jenkins.deploy.DeployToK8s" in mod._DISPATCH
        assert "jenkins.deploy.RollbackDeploy" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _jenkins_import("deploy_handlers")
        result = mod.handle({"_facet_name": "jenkins.deploy.DeployToEnvironment", "environment": "staging"})
        assert isinstance(result, dict)
        assert "result" in result

    def test_handle_unknown_facet(self):
        mod = _jenkins_import("deploy_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "jenkins.deploy.NonExistent"})

    def test_register_handlers(self):
        mod = _jenkins_import("deploy_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 3


class TestJenkinsNotifyHandlers:
    def test_dispatch_keys(self):
        mod = _jenkins_import("notify_handlers")
        assert len(mod._DISPATCH) == 2
        assert "jenkins.notify.SlackNotify" in mod._DISPATCH
        assert "jenkins.notify.EmailNotify" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _jenkins_import("notify_handlers")
        result = mod.handle({"_facet_name": "jenkins.notify.SlackNotify", "channel": "#test"})
        assert isinstance(result, dict)
        assert "sent" in result

    def test_handle_unknown_facet(self):
        mod = _jenkins_import("notify_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "jenkins.notify.NonExistent"})

    def test_register_handlers(self):
        mod = _jenkins_import("notify_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 2


class TestJenkinsInitRegistryHandlers:
    def test_register_all_registry_handlers(self):
        mod = _jenkins_import("__init__")
        runner = MagicMock()
        mod.register_all_registry_handlers(runner)
        # 2 scm + 4 build + 3 test + 3 artifact + 3 deploy + 2 notify = 17
        assert runner.register_handler.call_count == 17
