# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for script phase handlers.

Tests FacetScriptsBeginHandler execution of ScriptBlock bodies.
"""

from unittest.mock import MagicMock

from afl.runtime.changers.base import StateChangeResult
from afl.runtime.handlers.scripts import FacetScriptsBeginHandler
from afl.runtime.step import StepDefinition
from afl.runtime.types import ObjectType


def _make_step(facet_name: str = "TestFacet", params: dict | None = None) -> StepDefinition:
    """Create a test step with optional params."""
    step = StepDefinition.create(
        workflow_id="wf-test",
        object_type=ObjectType.VARIABLE_ASSIGNMENT,
        facet_name=facet_name,
    )
    if params:
        for name, value in params.items():
            step.set_attribute(name, value, is_return=False)
    return step


def _make_context(facet_def: dict | None = None) -> MagicMock:
    """Create a mock ExecutionContext."""
    context = MagicMock()
    context.get_facet_definition.return_value = facet_def
    context.telemetry = MagicMock()
    return context


class TestFacetScriptsBeginHandler:
    """Tests for FacetScriptsBeginHandler with ScriptBlock execution."""

    def test_basic_execution(self):
        """Script block executes and writes results to step returns."""
        step = _make_step("Compute", params={"x": 5})
        facet_def = {
            "type": "FacetDecl",
            "name": "Compute",
            "body": {
                "type": "ScriptBlock",
                "code": 'result["output"] = params["x"] * 2',
                "language": "python",
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        result = handler.process_state()

        assert isinstance(result, StateChangeResult)
        assert step.get_attribute("output") == 10

    def test_params_available(self):
        """Script has access to all step params."""
        step = _make_step("Process", params={"a": 3, "b": 7})
        facet_def = {
            "type": "FacetDecl",
            "name": "Process",
            "body": {
                "type": "ScriptBlock",
                "code": 'result["sum"] = params["a"] + params["b"]',
                "language": "python",
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        handler.process_state()

        assert step.get_attribute("sum") == 10

    def test_runtime_error_returns_error(self):
        """Runtime error in script returns error result."""
        step = _make_step("Fail")
        facet_def = {
            "type": "FacetDecl",
            "name": "Fail",
            "body": {
                "type": "ScriptBlock",
                "code": '1 / 0',
                "language": "python",
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        result = handler.process_state()

        assert result.success is False
        assert result.error is not None

    def test_syntax_error_returns_error(self):
        """Syntax error in script returns error result."""
        step = _make_step("BadSyntax")
        facet_def = {
            "type": "FacetDecl",
            "name": "BadSyntax",
            "body": {
                "type": "ScriptBlock",
                "code": 'def (broken',
                "language": "python",
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        result = handler.process_state()

        assert result.success is False
        assert result.error is not None

    def test_no_script_passthrough(self):
        """No ScriptBlock body — passes through."""
        step = _make_step("NoScript")
        facet_def = {
            "type": "FacetDecl",
            "name": "NoScript",
            "body": {
                "type": "AndThenBlock",
                "steps": [],
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        result = handler.process_state()

        assert isinstance(result, StateChangeResult)
        # Step should still request transition
        assert step.transition.request_transition is True

    def test_no_facet_passthrough(self):
        """No facet definition found — passes through."""
        step = _make_step("Unknown")
        context = _make_context(None)

        handler = FacetScriptsBeginHandler(step, context)
        result = handler.process_state()

        assert isinstance(result, StateChangeResult)
        assert step.transition.request_transition is True

    def test_event_facet_with_script(self):
        """EventFacetDecl with ScriptBlock body works."""
        step = _make_step("Transform", params={"text": "hello"})
        facet_def = {
            "type": "EventFacetDecl",
            "name": "Transform",
            "body": {
                "type": "ScriptBlock",
                "code": 'result["upper"] = params["text"].upper()',
                "language": "python",
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        handler.process_state()

        assert step.get_attribute("upper") == "HELLO"

    def test_result_type_preservation(self):
        """Script results preserve types (int, list, dict, bool)."""
        step = _make_step("Types", params={"x": 5})
        facet_def = {
            "type": "FacetDecl",
            "name": "Types",
            "body": {
                "type": "ScriptBlock",
                "code": (
                    'result["count"] = params["x"]\n'
                    'result["items"] = [1, 2, 3]\n'
                    'result["meta"] = {"key": "value"}\n'
                    'result["flag"] = True'
                ),
                "language": "python",
            },
        }
        context = _make_context(facet_def)

        handler = FacetScriptsBeginHandler(step, context)
        handler.process_state()

        assert step.get_attribute("count") == 5
        assert step.get_attribute("items") == [1, 2, 3]
        assert step.get_attribute("meta") == {"key": "value"}
        assert step.get_attribute("flag") is True
