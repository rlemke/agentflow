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

"""Tests for AFL Claude agent runner.

Tests ToolRegistry, ToolDefinition extraction, and ClaudeAgentRunner
with both custom handlers and mock Anthropic client.
"""

import pytest

from afl.runtime import (
    Evaluator,
    ExecutionStatus,
    MemoryStore,
    Telemetry,
)
from afl.runtime.agent import (
    ClaudeAgentRunner,
    ToolRegistry,
)

# =========================================================================
# ToolRegistry unit tests
# =========================================================================


class TestToolRegistry:
    """Unit tests for ToolRegistry."""

    def test_register_and_handle(self):
        """Custom handler called with correct payload."""
        registry = ToolRegistry()
        registry.register("CountDocuments", lambda p: {"output": p["input"] * 2})

        result = registry.handle("CountDocuments", {"input": 5})
        assert result == {"output": 10}

    def test_unregistered_returns_none(self):
        """No handler returns None."""
        registry = ToolRegistry()
        result = registry.handle("Unknown", {"input": 1})
        assert result is None

    def test_default_handler(self):
        """Fallback default handler works."""
        registry = ToolRegistry()
        registry.set_default_handler(lambda event_type, payload: {"handled": event_type})

        result = registry.handle("SomeEvent", {"input": 1})
        assert result == {"handled": "SomeEvent"}

    def test_specific_overrides_default(self):
        """Specific handler takes priority over default."""
        registry = ToolRegistry()
        registry.register("Specific", lambda p: {"source": "specific"})
        registry.set_default_handler(lambda t, p: {"source": "default"})

        result = registry.handle("Specific", {})
        assert result == {"source": "specific"}

        result2 = registry.handle("Other", {})
        assert result2 == {"source": "default"}

    def test_has_handler_specific(self):
        registry = ToolRegistry()
        assert registry.has_handler("Foo") is False
        registry.register("Foo", lambda p: {})
        assert registry.has_handler("Foo") is True

    def test_has_handler_default(self):
        registry = ToolRegistry()
        assert registry.has_handler("Anything") is False
        registry.set_default_handler(lambda t, p: {})
        assert registry.has_handler("Anything") is True


# =========================================================================
# ToolDefinition extraction tests
# =========================================================================


class TestToolDefinitionExtraction:
    """Tests for extracting ToolDefinitions from program AST."""

    def _make_runner(self):
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))
        return ClaudeAgentRunner(evaluator=evaluator, persistence=store)

    def test_extract_event_facet_decl(self):
        """EventFacetDecl found, FacetDecl ignored."""
        runner = self._make_runner()
        program_ast = {
            "type": "Program",
            "declarations": [
                {
                    "type": "FacetDecl",
                    "name": "Value",
                    "params": [{"name": "input", "type": "Long"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "CountDocuments",
                    "params": [{"name": "input", "type": "Long"}],
                    "returns": [{"name": "output", "type": "Long"}],
                },
            ],
        }

        tool_defs = runner._extract_tool_definitions(program_ast)
        assert len(tool_defs) == 1
        assert tool_defs[0].name == "CountDocuments"
        assert tool_defs[0].param_names == ["input"]
        assert tool_defs[0].return_names == ["output"]

    def test_nested_namespace_extraction(self):
        """EventFacetDecl inside Namespace found."""
        runner = self._make_runner()
        program_ast = {
            "type": "Program",
            "declarations": [
                {
                    "type": "Namespace",
                    "name": "example.ns",
                    "declarations": [
                        {
                            "type": "EventFacetDecl",
                            "name": "ProcessData",
                            "params": [{"name": "data", "type": "String"}],
                            "returns": [{"name": "result", "type": "String"}],
                        },
                    ],
                },
            ],
        }

        tool_defs = runner._extract_tool_definitions(program_ast)
        assert len(tool_defs) == 1
        assert tool_defs[0].name == "ProcessData"

    def test_type_mapping(self):
        """AFL types map to correct JSON Schema types."""
        runner = self._make_runner()
        program_ast = {
            "type": "Program",
            "declarations": [
                {
                    "type": "EventFacetDecl",
                    "name": "MultiType",
                    "params": [],
                    "returns": [
                        {"name": "count", "type": "Long"},
                        {"name": "ratio", "type": "Double"},
                        {"name": "label", "type": "String"},
                        {"name": "active", "type": "Boolean"},
                    ],
                },
            ],
        }

        tool_defs = runner._extract_tool_definitions(program_ast)
        assert len(tool_defs) == 1
        schema = tool_defs[0].input_schema
        assert schema["properties"]["count"] == {"type": "integer"}
        assert schema["properties"]["ratio"] == {"type": "number"}
        assert schema["properties"]["label"] == {"type": "string"}
        assert schema["properties"]["active"] == {"type": "boolean"}
        assert schema["required"] == ["count", "ratio", "label", "active"]

    def test_no_program_ast(self):
        """None program_ast yields empty list."""
        runner = self._make_runner()
        assert runner._extract_tool_definitions(None) == []


# =========================================================================
# Example 4 fixtures (reused from test_evaluator.py)
# =========================================================================


@pytest.fixture
def example4_program_ast():
    """Program AST with Value, SomeFacet, CountDocuments (event), and Adder."""
    return {
        "type": "Program",
        "declarations": [
            {
                "type": "FacetDecl",
                "name": "Value",
                "params": [{"name": "input", "type": "Long"}],
            },
            {
                "type": "FacetDecl",
                "name": "SomeFacet",
                "params": [{"name": "input", "type": "Long"}],
                "returns": [{"name": "output", "type": "Long"}],
            },
            {
                "type": "EventFacetDecl",
                "name": "CountDocuments",
                "params": [{"name": "input", "type": "Long"}],
                "returns": [{"name": "output", "type": "Long"}],
            },
            {
                "type": "FacetDecl",
                "name": "Adder",
                "params": [
                    {"name": "a", "type": "Long"},
                    {"name": "b", "type": "Long"},
                ],
                "returns": [{"name": "sum", "type": "Long"}],
                "body": {
                    "type": "AndThenBlock",
                    "steps": [
                        {
                            "type": "StepStmt",
                            "id": "step-s1",
                            "name": "s1",
                            "call": {
                                "type": "CallExpr",
                                "target": "SomeFacet",
                                "args": [
                                    {
                                        "name": "input",
                                        "value": {"type": "InputRef", "path": ["a"]},
                                    }
                                ],
                            },
                            "body": {
                                "type": "AndThenBlock",
                                "steps": [
                                    {
                                        "type": "StepStmt",
                                        "id": "step-subStep1",
                                        "name": "subStep1",
                                        "call": {
                                            "type": "CallExpr",
                                            "target": "CountDocuments",
                                            "args": [
                                                {
                                                    "name": "input",
                                                    "value": {"type": "Int", "value": 3},
                                                }
                                            ],
                                        },
                                    },
                                ],
                                "yield": {
                                    "type": "YieldStmt",
                                    "id": "yield-SF",
                                    "call": {
                                        "type": "CallExpr",
                                        "target": "SomeFacet",
                                        "args": [
                                            {
                                                "name": "output",
                                                "value": {
                                                    "type": "BinaryExpr",
                                                    "operator": "+",
                                                    "left": {
                                                        "type": "StepRef",
                                                        "path": ["subStep1", "input"],
                                                    },
                                                    "right": {"type": "Int", "value": 10},
                                                },
                                            }
                                        ],
                                    },
                                },
                            },
                        },
                        {
                            "type": "StepStmt",
                            "id": "step-s2",
                            "name": "s2",
                            "call": {
                                "type": "CallExpr",
                                "target": "Value",
                                "args": [
                                    {
                                        "name": "input",
                                        "value": {"type": "InputRef", "path": ["b"]},
                                    }
                                ],
                            },
                        },
                    ],
                    "yield": {
                        "type": "YieldStmt",
                        "id": "yield-Adder",
                        "call": {
                            "type": "CallExpr",
                            "target": "Adder",
                            "args": [
                                {
                                    "name": "sum",
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "StepRef", "path": ["s1", "output"]},
                                        "right": {"type": "StepRef", "path": ["s2", "input"]},
                                    },
                                }
                            ],
                        },
                    },
                },
            },
        ],
    }


@pytest.fixture
def example4_workflow_ast():
    """AST for AddWorkflow (Example 4)."""
    return {
        "type": "WorkflowDecl",
        "name": "AddWorkflow",
        "params": [
            {"name": "x", "type": "Long"},
            {"name": "y", "type": "Long"},
        ],
        "returns": [{"name": "result", "type": "Long"}],
        "body": {
            "type": "AndThenBlock",
            "steps": [
                {
                    "type": "StepStmt",
                    "id": "step-addition",
                    "name": "addition",
                    "call": {
                        "type": "CallExpr",
                        "target": "Adder",
                        "args": [
                            {
                                "name": "a",
                                "value": {"type": "InputRef", "path": ["x"]},
                            },
                            {
                                "name": "b",
                                "value": {"type": "InputRef", "path": ["y"]},
                            },
                        ],
                    },
                },
            ],
            "yield": {
                "type": "YieldStmt",
                "id": "yield-AW",
                "call": {
                    "type": "CallExpr",
                    "target": "AddWorkflow",
                    "args": [
                        {
                            "name": "result",
                            "value": {"type": "StepRef", "path": ["addition", "sum"]},
                        }
                    ],
                },
            },
        },
    }


# =========================================================================
# ClaudeAgentRunner with custom handlers (no API calls)
# =========================================================================


class TestClaudeAgentRunnerWithCustomHandlers:
    """Integration tests using custom handlers, no Anthropic API."""

    def test_full_workflow_with_custom_handler(self, example4_workflow_ast, example4_program_ast):
        """Example 4 workflow completes end-to-end using registered handler."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        registry = ToolRegistry()
        # CountDocuments handler: just passes through (no transformation)
        registry.register("CountDocuments", lambda payload: {})

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            tool_registry=registry,
        )

        result = runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        assert result.success is True
        assert result.status == ExecutionStatus.COMPLETED
        # subStep1.input = 3
        # yield SomeFacet(output = 3 + 10 = 13)
        # s1.output = 13, s2.input = 2
        # yield Adder(sum = 13 + 2 = 15)
        # yield AddWorkflow(result = 15)
        assert result.outputs["result"] == 15

    def test_no_handler_no_client_raises(self, example4_workflow_ast, example4_program_ast):
        """Missing handler + no client raises RuntimeError."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            # No registry, no anthropic_client
        )

        with pytest.raises(RuntimeError, match="No handler registered"):
            runner.run(
                example4_workflow_ast,
                inputs={"x": 1, "y": 2},
                program_ast=example4_program_ast,
            )

    def test_max_dispatches_exceeded(self, example4_workflow_ast, example4_program_ast):
        """Safety limit stops dispatching and returns current result."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        registry = ToolRegistry()
        # Handler that never actually unblocks (returns empty — step still completes)
        registry.register("CountDocuments", lambda payload: {})

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            tool_registry=registry,
            max_dispatches=0,  # Zero dispatches allowed
        )

        result = runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        # Should be PAUSED since we didn't dispatch anything
        assert result.status == ExecutionStatus.PAUSED

    def test_default_handler_used(self, example4_workflow_ast, example4_program_ast):
        """Default handler is used when no specific handler is registered."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        registry = ToolRegistry()
        registry.set_default_handler(lambda event_type, payload: {})

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            tool_registry=registry,
        )

        result = runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        assert result.success is True
        assert result.status == ExecutionStatus.COMPLETED


# =========================================================================
# Mock Anthropic client
# =========================================================================


class MockToolUseBlock:
    """Mock tool_use content block from Anthropic API."""

    def __init__(self, name: str, input_data: dict):
        self.type = "tool_use"
        self.id = "toolu_mock"
        self.name = name
        self.input = input_data


class MockTextBlock:
    """Mock text content block from Anthropic API."""

    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class MockResponse:
    """Mock Anthropic messages.create() response."""

    def __init__(self, content: list):
        self.content = content
        self.model = "claude-sonnet-4-20250514"
        self.role = "assistant"
        self.stop_reason = (
            "tool_use"
            if any(getattr(b, "type", None) == "tool_use" for b in content)
            else "end_turn"
        )


class MockMessages:
    """Mock messages namespace on the Anthropic client."""

    def __init__(self):
        self.calls: list[dict] = []
        self._responses: list[MockResponse] = []
        self._default_response: MockResponse | None = None

    def set_response(self, response: MockResponse) -> None:
        """Set a single response for all calls."""
        self._default_response = response

    def add_response(self, response: MockResponse) -> None:
        """Queue a response for the next call."""
        self._responses.append(response)

    def create(self, **kwargs) -> MockResponse:
        self.calls.append(kwargs)
        if self._responses:
            return self._responses.pop(0)
        if self._default_response:
            return self._default_response
        raise ValueError("No mock response configured")


class MockAnthropicClient:
    """Mock anthropic.Anthropic() client."""

    def __init__(self):
        self.messages = MockMessages()


# =========================================================================
# ClaudeAgentRunner with mock Claude client
# =========================================================================


class TestClaudeAgentRunnerWithMockClient:
    """Tests with mock Anthropic API client."""

    def test_claude_receives_correct_tools(self, example4_workflow_ast, example4_program_ast):
        """Verify tools passed to Claude match EventFacetDecl schemas."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        client = MockAnthropicClient()
        client.messages.set_response(
            MockResponse([MockToolUseBlock("CountDocuments", {"output": 42})])
        )

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            anthropic_client=client,
        )

        runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        # Verify Claude was called
        assert len(client.messages.calls) == 1
        call = client.messages.calls[0]

        # Verify tools contain CountDocuments
        tools = call["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "CountDocuments"
        assert tools[0]["input_schema"]["properties"]["output"] == {"type": "integer"}
        assert tools[0]["input_schema"]["required"] == ["output"]

    def test_tool_use_response_mapped_to_result(self, example4_workflow_ast, example4_program_ast):
        """Claude's tool_use input becomes continue_step result."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        client = MockAnthropicClient()
        # Claude returns output=99 for CountDocuments
        client.messages.set_response(
            MockResponse([MockToolUseBlock("CountDocuments", {"output": 99})])
        )

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            anthropic_client=client,
        )

        result = runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        assert result.success is True
        assert result.status == ExecutionStatus.COMPLETED

    def test_text_only_response(self, example4_workflow_ast, example4_program_ast):
        """Claude doesn't call tool — empty result dict used."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        client = MockAnthropicClient()
        # Claude returns text only, no tool use
        client.messages.set_response(MockResponse([MockTextBlock("I cannot process this.")]))

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            anthropic_client=client,
        )

        result = runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        # Workflow should still complete (empty result for step)
        assert result.success is True
        assert result.status == ExecutionStatus.COMPLETED

    def test_system_prompt_passed(self, example4_workflow_ast, example4_program_ast):
        """Custom system prompt is passed to Claude."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        client = MockAnthropicClient()
        client.messages.set_response(MockResponse([MockToolUseBlock("CountDocuments", {})]))

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            anthropic_client=client,
            system_prompt="Custom system prompt here.",
        )

        runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
        )

        call = client.messages.calls[0]
        assert call["system"] == "Custom system prompt here."

    def test_task_description_in_message(self, example4_workflow_ast, example4_program_ast):
        """Task description appears in the user message."""
        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        client = MockAnthropicClient()
        client.messages.set_response(MockResponse([MockToolUseBlock("CountDocuments", {})]))

        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            anthropic_client=client,
        )

        runner.run(
            example4_workflow_ast,
            inputs={"x": 1, "y": 2},
            program_ast=example4_program_ast,
            task_description="Count all documents in the database",
        )

        call = client.messages.calls[0]
        user_msg = call["messages"][0]["content"]
        assert "Count all documents in the database" in user_msg
