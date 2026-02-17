"""Tests for AWS Lambda handler dispatch adapter pattern.

Verifies that each handler module's handle() function dispatches correctly
using the _facet_name key, that _DISPATCH dicts have the expected keys,
and that register_handlers() calls runner.register_handler the expected
number of times.

Note: These tests do NOT call actual handlers (no LocalStack needed).
They only verify _DISPATCH dict keys, unknown facet errors, and
registration call counts.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

boto3 = pytest.importorskip("boto3")

AWS_LAMBDA_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)


def _aws_import(module_name: str):
    """Import an AWS Lambda handlers submodule, ensuring correct sys.path."""
    if AWS_LAMBDA_DIR in sys.path:
        sys.path.remove(AWS_LAMBDA_DIR)
    sys.path.insert(0, AWS_LAMBDA_DIR)

    full_name = f"handlers.{module_name}"

    # If module is already loaded from the right location, return it
    if full_name in sys.modules:
        mod = sys.modules[full_name]
        mod_file = getattr(mod, "__file__", "")
        if mod_file and "aws-lambda" in mod_file:
            return mod
        del sys.modules[full_name]

    # Ensure the handlers package itself is from aws-lambda
    if "handlers" in sys.modules:
        pkg = sys.modules["handlers"]
        pkg_file = getattr(pkg, "__file__", "")
        if pkg_file and "aws-lambda" not in pkg_file:
            stale = [k for k in sys.modules if k == "handlers" or k.startswith("handlers.")]
            for k in stale:
                del sys.modules[k]

    return importlib.import_module(full_name)


class TestAwsLambdaHandlers:
    def test_dispatch_keys(self):
        mod = _aws_import("lambda_handlers")
        assert len(mod._DISPATCH) == 7
        assert "aws.lambda.CreateFunction" in mod._DISPATCH
        assert "aws.lambda.InvokeFunction" in mod._DISPATCH
        assert "aws.lambda.UpdateFunctionCode" in mod._DISPATCH
        assert "aws.lambda.DeleteFunction" in mod._DISPATCH
        assert "aws.lambda.ListFunctions" in mod._DISPATCH
        assert "aws.lambda.GetFunctionInfo" in mod._DISPATCH
        assert "aws.lambda.PublishLayer" in mod._DISPATCH

    def test_handle_unknown_facet(self):
        mod = _aws_import("lambda_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "aws.lambda.NonExistent"})

    def test_register_handlers(self):
        mod = _aws_import("lambda_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 7

    def test_namespace_constant(self):
        mod = _aws_import("lambda_handlers")
        assert mod.NAMESPACE == "aws.lambda"


class TestAwsStepFunctionsHandlers:
    def test_dispatch_keys(self):
        mod = _aws_import("stepfunctions_handlers")
        assert len(mod._DISPATCH) == 5
        assert "aws.stepfunctions.CreateStateMachine" in mod._DISPATCH
        assert "aws.stepfunctions.StartExecution" in mod._DISPATCH
        assert "aws.stepfunctions.DescribeExecution" in mod._DISPATCH
        assert "aws.stepfunctions.DeleteStateMachine" in mod._DISPATCH
        assert "aws.stepfunctions.ListExecutions" in mod._DISPATCH

    def test_handle_unknown_facet(self):
        mod = _aws_import("stepfunctions_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "aws.stepfunctions.NonExistent"})

    def test_register_handlers(self):
        mod = _aws_import("stepfunctions_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 5

    def test_namespace_constant(self):
        mod = _aws_import("stepfunctions_handlers")
        assert mod.NAMESPACE == "aws.stepfunctions"


class TestAwsLambdaInitRegistryHandlers:
    def test_register_all_registry_handlers(self):
        mod = _aws_import("__init__")
        runner = MagicMock()
        mod.register_all_registry_handlers(runner)
        # 7 lambda + 5 stepfunctions = 12
        assert runner.register_handler.call_count == 12

    def test_register_all_handlers(self):
        mod = _aws_import("__init__")
        poller = MagicMock()
        mod.register_all_handlers(poller)
        # 7 lambda + 5 stepfunctions = 12
        assert poller.register.call_count == 12
