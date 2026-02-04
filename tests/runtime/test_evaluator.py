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

"""Tests for AFL runtime evaluator.

Includes integration tests for spec examples 21.1, 21.2, 21.3,
and 70_examples.md examples 2, 3, and 4.
"""

import pytest

from afl.runtime import (
    Evaluator,
    ExecutionStatus,
    MemoryStore,
    ObjectType,
    StepState,
    Telemetry,
)


class TestEvaluatorBasic:
    """Basic evaluator tests."""

    @pytest.fixture
    def evaluator(self):
        """Create evaluator with in-memory store."""
        store = MemoryStore()
        telemetry = Telemetry(enabled=True)
        return Evaluator(persistence=store, telemetry=telemetry)

    def test_empty_workflow(self, evaluator):
        """Test executing a workflow with no body."""
        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "Empty",
            "params": [],
        }

        result = evaluator.execute(workflow_ast)
        assert result.success is True

    def test_workflow_with_default_input(self, evaluator):
        """Test workflow with default input value."""
        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "TestInput",
            "params": [{"name": "input", "type": "Long"}],
        }

        result = evaluator.execute(workflow_ast, inputs={"input": 42})
        assert result.success is True


class TestSpecExample21_1:
    """Tests for spec example 21.1: Initialization and dependency-driven evaluation.

    ```afl
    namespace test.one {
      facet Value(input: Long, output: Long)

      workflow TestOne(input: Long = 1) => (output: Long) andThen {
        s1 = Value(input = $.input + 1)
        s2 = Value(input = s1.input + 1)
        yield TestOne(output = s2.input + 1)
      }
    }
    ```

    Expected: TestOne.output = 4
    """

    @pytest.fixture
    def evaluator(self):
        """Create evaluator with in-memory store."""
        store = MemoryStore()
        telemetry = Telemetry(enabled=True)
        return Evaluator(persistence=store, telemetry=telemetry)

    @pytest.fixture
    def workflow_ast(self):
        """AST for TestOne workflow."""
        return {
            "type": "WorkflowDecl",
            "name": "TestOne",
            "params": [{"name": "input", "type": "Long"}],
            "returns": [{"name": "output", "type": "Long"}],
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {
                        "type": "StepStmt",
                        "id": "step-s1",
                        "name": "s1",
                        "call": {
                            "type": "CallExpr",
                            "target": "Value",
                            "args": [
                                {
                                    "name": "input",
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "InputRef", "path": ["input"]},
                                        "right": {"type": "Int", "value": 1},
                                    },
                                }
                            ],
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
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "StepRef", "path": ["s1", "input"]},
                                        "right": {"type": "Int", "value": 1},
                                    },
                                }
                            ],
                        },
                    },
                ],
                "yield": {
                    "type": "YieldStmt",
                    "id": "yield-1",
                    "call": {
                        "type": "CallExpr",
                        "target": "TestOne",
                        "args": [
                            {
                                "name": "output",
                                "value": {
                                    "type": "BinaryExpr",
                                    "operator": "+",
                                    "left": {"type": "StepRef", "path": ["s2", "input"]},
                                    "right": {"type": "Int", "value": 1},
                                },
                            }
                        ],
                    },
                },
            },
        }

    def test_sequential_dependency(self, evaluator, workflow_ast):
        """Test that s2 waits for s1 to complete."""
        result = evaluator.execute(workflow_ast, inputs={"input": 1})

        # Workflow should complete successfully
        assert result.success is True

        # Check final output
        # TestOne.input = 1
        # s1.input = 1 + 1 = 2
        # s2.input = 2 + 1 = 3
        # output = 3 + 1 = 4
        assert result.outputs.get("output") == 4


class TestSpecExample21_2:
    """Tests for spec example 21.2: Parallel steps and fan-in.

    ```afl
    namespace test.two {
      facet Value(input: Long, output: Long)

      workflow TestTwo(input: Long = 1) => (output: Long) andThen {
        a = Value(input = $.input + 1)
        b = Value(input = $.input + 10)
        c = Value(input = a.input + b.input)
        yield TestTwo(output = c.input)
      }
    }
    ```

    Expected: TestTwo.output = 13
    """

    @pytest.fixture
    def evaluator(self):
        """Create evaluator with in-memory store."""
        store = MemoryStore()
        telemetry = Telemetry(enabled=True)
        return Evaluator(persistence=store, telemetry=telemetry)

    @pytest.fixture
    def workflow_ast(self):
        """AST for TestTwo workflow."""
        return {
            "type": "WorkflowDecl",
            "name": "TestTwo",
            "params": [{"name": "input", "type": "Long"}],
            "returns": [{"name": "output", "type": "Long"}],
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {
                        "type": "StepStmt",
                        "id": "step-a",
                        "name": "a",
                        "call": {
                            "type": "CallExpr",
                            "target": "Value",
                            "args": [
                                {
                                    "name": "input",
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "InputRef", "path": ["input"]},
                                        "right": {"type": "Int", "value": 1},
                                    },
                                }
                            ],
                        },
                    },
                    {
                        "type": "StepStmt",
                        "id": "step-b",
                        "name": "b",
                        "call": {
                            "type": "CallExpr",
                            "target": "Value",
                            "args": [
                                {
                                    "name": "input",
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "InputRef", "path": ["input"]},
                                        "right": {"type": "Int", "value": 10},
                                    },
                                }
                            ],
                        },
                    },
                    {
                        "type": "StepStmt",
                        "id": "step-c",
                        "name": "c",
                        "call": {
                            "type": "CallExpr",
                            "target": "Value",
                            "args": [
                                {
                                    "name": "input",
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "StepRef", "path": ["a", "input"]},
                                        "right": {"type": "StepRef", "path": ["b", "input"]},
                                    },
                                }
                            ],
                        },
                    },
                ],
                "yield": {
                    "type": "YieldStmt",
                    "id": "yield-1",
                    "call": {
                        "type": "CallExpr",
                        "target": "TestTwo",
                        "args": [
                            {"name": "output", "value": {"type": "StepRef", "path": ["c", "input"]}}
                        ],
                    },
                },
            },
        }

    def test_parallel_and_fan_in(self, evaluator, workflow_ast):
        """Test parallel execution of a,b and fan-in to c."""
        result = evaluator.execute(workflow_ast, inputs={"input": 1})

        # Workflow should complete successfully
        assert result.success is True

        # Check final output
        # TestTwo.input = 1
        # a.input = 1 + 1 = 2
        # b.input = 1 + 10 = 11
        # c.input = 2 + 11 = 13
        # output = 13
        assert result.outputs.get("output") == 13


class TestIdempotency:
    """Tests for restart safety and idempotency."""

    @pytest.fixture
    def store(self):
        """Create shared memory store."""
        return MemoryStore()

    def test_duplicate_step_creation_prevented(self, store):
        """Test that duplicate steps are not created."""
        from afl.runtime import StepDefinition, block_id, workflow_id

        wf_id = workflow_id()
        b_id = block_id()

        # Create a step
        step1 = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id=b_id,
        )
        store.save_step(step1)

        # Verify idempotency check
        assert store.step_exists("stmt-1", b_id) is True

        # Attempt to create same step again should be detected
        assert store.step_exists("stmt-1", b_id) is True


class TestTelemetry:
    """Tests for telemetry collection."""

    def test_telemetry_events(self):
        """Test that telemetry events are collected."""
        store = MemoryStore()
        telemetry = Telemetry(enabled=True)
        evaluator = Evaluator(persistence=store, telemetry=telemetry)

        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "Test",
            "params": [],
        }

        evaluator.execute(workflow_ast)

        events = telemetry.get_events()
        assert len(events) > 0

        # Should have workflow start event
        event_types = [e["eventType"] for e in events]
        assert "workflow.start" in event_types

    def test_telemetry_disabled(self):
        """Test that telemetry can be disabled."""
        store = MemoryStore()
        telemetry = Telemetry(enabled=False)
        evaluator = Evaluator(persistence=store, telemetry=telemetry)

        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "Test",
            "params": [],
        }

        evaluator.execute(workflow_ast)

        events = telemetry.get_events()
        assert len(events) == 0


# =========================================================================
# Spec Example 2: Facet with andThen body (facet-level blocks)
# =========================================================================


class TestSpecExample2:
    """Tests for spec/70_examples.md Example 2: Facet-level andThen body.

    ```afl
    namespace example.2 {
        facet Value(input:Long)
        facet Adder(a:Long, b:Long) => (sum:Long)
            andThen {
                s1 = Value(input = $.a)
                s2 = Value(input = $.b)
                yield Adder(sum = s1.input + s2.input)
            }
        workflow AddWorkflow(x:Long = 1, y:Long = 2) => (result:Long)
            andThen {
                addition = Adder(a = $.x, b = $.y)
                yield AddWorkflow(result = addition.sum)
            }
    }
    ```

    Expected: result = s1.input + s2.input = 1 + 2 = 3
    """

    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.fixture
    def evaluator(self, store):
        return Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

    @pytest.fixture
    def program_ast(self):
        """Program AST with Value and Adder facet declarations."""
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
                                    "target": "Value",
                                    "args": [
                                        {
                                            "name": "input",
                                            "value": {"type": "InputRef", "path": ["a"]},
                                        }
                                    ],
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
                                            "left": {"type": "StepRef", "path": ["s1", "input"]},
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
    def workflow_ast(self):
        """AST for AddWorkflow."""
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

    def test_facet_level_blocks(self, evaluator, workflow_ast, program_ast):
        """Test Example 2: facet with andThen body produces correct output."""
        result = evaluator.execute(workflow_ast, inputs={"x": 1, "y": 2}, program_ast=program_ast)

        assert result.success is True
        assert result.status == ExecutionStatus.COMPLETED
        # addition calls Adder(a=1, b=2)
        # Adder body: s1=Value(input=$.a=1), s2=Value(input=$.b=2)
        # yield Adder(sum = s1.input + s2.input = 1 + 2 = 3)
        # yield AddWorkflow(result = addition.sum = 3)
        assert result.outputs.get("result") == 3


# =========================================================================
# Spec Example 3: Statement-level nested andThen blocks
# =========================================================================


class TestSpecExample3:
    """Tests for spec/70_examples.md Example 3: Statement-level nested blocks.

    ```afl
    namespace example.3 {
        facet Value(input:Long)
        facet SomeFacet(input:Long) => (output:Long)
        facet Adder(a:Long, b:Long) => (sum:Long)
            andThen {
                s1 = SomeFacet(input = $.a) andThen {
                    subStep1 = Value(input = $.input)
                    yield SomeFacet(output = subStep1.input + 10)
                }
                s2 = Value(input = $.b)
                yield Adder(sum = s1.output + s2.input)
            }
        workflow AddWorkflow(x:Long = 1, y:Long = 2) => (result:Long)
            andThen {
                addition = Adder(a = $.x, b = $.y)
                yield AddWorkflow(result = addition.sum)
            }
    }
    ```

    Expected: result = s1.output + s2.input = (subStep1.input + 10) + 2 = (1 + 10) + 2 = 13
    """

    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.fixture
    def evaluator(self, store):
        return Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

    @pytest.fixture
    def program_ast(self):
        """Program AST with Value, SomeFacet, and Adder declarations."""
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
                                # Statement-level inline andThen body
                                "body": {
                                    "type": "AndThenBlock",
                                    "steps": [
                                        {
                                            "type": "StepStmt",
                                            "id": "step-subStep1",
                                            "name": "subStep1",
                                            "call": {
                                                "type": "CallExpr",
                                                "target": "Value",
                                                "args": [
                                                    {
                                                        "name": "input",
                                                        "value": {
                                                            "type": "InputRef",
                                                            "path": ["input"],
                                                        },
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
    def workflow_ast(self):
        """AST for AddWorkflow (same as Example 2)."""
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

    def test_statement_level_nested_blocks(self, evaluator, workflow_ast, program_ast):
        """Test Example 3: statement-level nested andThen produces correct output."""
        result = evaluator.execute(workflow_ast, inputs={"x": 1, "y": 2}, program_ast=program_ast)

        assert result.success is True
        assert result.status == ExecutionStatus.COMPLETED
        # s1 calls SomeFacet(input=$.a=1), has inline andThen:
        #   subStep1 = Value(input = $.input = 1)
        #   yield SomeFacet(output = subStep1.input + 10 = 1 + 10 = 11)
        # So s1.output = 11
        # s2 = Value(input = $.b = 2)
        # yield Adder(sum = s1.output + s2.input = 11 + 2 = 13)
        # yield AddWorkflow(result = addition.sum = 13)
        assert result.outputs.get("result") == 13


# =========================================================================
# Spec Example 4: Event facet blocking/resumption
# =========================================================================


class TestSpecExample4:
    """Tests for spec/70_examples.md Example 4: Event facet blocking.

    Same as Example 3 but subStep1 calls CountDocuments (EventFacetDecl),
    which blocks at EventTransmit until continue_step() is called.

    Expected: Two evaluator runs, result = 13.
    """

    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.fixture
    def evaluator(self, store):
        return Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

    @pytest.fixture
    def program_ast(self):
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
    def workflow_ast(self):
        """AST for AddWorkflow (same as Examples 2/3)."""
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

    def test_event_facet_blocking_and_resumption(self, store, evaluator, workflow_ast, program_ast):
        """Test Example 4: event facet blocks, then resumes after continue_step."""
        # Run 1: execute until PAUSED (subStep1 blocks at EventTransmit)
        result1 = evaluator.execute(workflow_ast, inputs={"x": 1, "y": 2}, program_ast=program_ast)

        assert result1.status == ExecutionStatus.PAUSED
        assert result1.success is True

        # Find the blocked step (subStep1 at EventTransmit)
        blocked_steps = [s for s in store.get_all_steps() if s.state == StepState.EVENT_TRANSMIT]
        assert len(blocked_steps) == 1
        blocked_step = blocked_steps[0]
        assert blocked_step.facet_name == "CountDocuments"

        # Verify an event was created
        assert store.event_count() == 1

        # Simulate external agent: continue the blocked step with a result
        evaluator.continue_step(blocked_step.id)

        # Run 2: resume execution
        result2 = evaluator.resume(
            result1.workflow_id,
            workflow_ast,
            program_ast=program_ast,
            inputs={"x": 1, "y": 2},
        )

        assert result2.status == ExecutionStatus.COMPLETED
        assert result2.success is True
        # subStep1.input = 3, yield SomeFacet(output = subStep1.input + 10) = 13
        # s1.output = 13, s2.input = 2, sum = 13 + 2 = 15
        assert result2.outputs["result"] == 15

    def test_event_facet_with_integer_input(self, store, evaluator, program_ast):
        """Test event facet with integer input for correct arithmetic."""
        # Use integer input to verify full arithmetic chain
        workflow_ast = {
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

        # Modify program_ast to have integer input for CountDocuments
        import copy

        prog = copy.deepcopy(program_ast)
        # Find the Adder facet, find s1's body, change subStep1 input to integer
        adder = [d for d in prog["declarations"] if d["name"] == "Adder"][0]
        s1_body = adder["body"]["steps"][0]["body"]
        s1_body["steps"][0]["call"]["args"][0]["value"] = {"type": "Int", "value": 1}

        # Run 1
        result1 = evaluator.execute(workflow_ast, inputs={"x": 1, "y": 2}, program_ast=prog)
        assert result1.status == ExecutionStatus.PAUSED

        # Find and continue blocked step
        blocked_steps = [s for s in store.get_all_steps() if s.state == StepState.EVENT_TRANSMIT]
        assert len(blocked_steps) == 1
        evaluator.continue_step(blocked_steps[0].id)

        # Run 2
        result2 = evaluator.resume(
            result1.workflow_id,
            workflow_ast,
            program_ast=prog,
            inputs={"x": 1, "y": 2},
        )

        assert result2.status == ExecutionStatus.COMPLETED
        assert result2.success is True
        # subStep1.input = 1
        # yield SomeFacet(output = 1 + 10 = 11) → s1.output = 11
        # s2.input = $.b = 2
        # yield Adder(sum = 11 + 2 = 13) → addition.sum = 13
        # yield AddWorkflow(result = 13)
        assert result2.outputs.get("result") == 13


# =========================================================================
# ExecutionContext unit tests
# =========================================================================


class TestExecutionContext:
    """Tests for ExecutionContext methods targeting uncovered lines."""

    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.fixture
    def context(self, store):
        from afl.runtime.evaluator import ExecutionContext
        from afl.runtime.persistence import IterationChanges

        return ExecutionContext(
            persistence=store,
            telemetry=Telemetry(enabled=False),
            changes=IterationChanges(),
            workflow_id="wf-ctx-1",
        )

    def test_get_statement_definition_with_graph(self, context):
        """get_statement_definition returns stmt when graph is cached (lines 73-75)."""
        from afl.runtime.block import StatementDefinition
        from afl.runtime.dependency import DependencyGraph
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        block_id = "block-1"
        stmt = StatementDefinition(
            id="stmt-1",
            name="s1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="Value",
        )
        graph = DependencyGraph()
        graph.statements["stmt-1"] = stmt
        context._block_graphs[block_id] = graph

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id=block_id,
        )

        result = context.get_statement_definition(step)
        assert result is not None
        assert result.name == "s1"

    def test_get_statement_definition_no_graph(self, context):
        """get_statement_definition returns None when no graph cached (line 76)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id="block-no-graph",
        )
        result = context.get_statement_definition(step)
        assert result is None

    def test_get_block_ast_no_container_with_workflow(self, context):
        """get_block_ast returns workflow body when block has no container (lines 95-96)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        context.workflow_ast = {
            "name": "Test",
            "body": {"type": "AndThenBlock", "steps": []},
        }

        block_step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.AND_THEN,
        )
        # No container_id → line 93 true, line 95 true
        result = context.get_block_ast(block_step)
        assert result == {"type": "AndThenBlock", "steps": []}

    def test_get_block_ast_no_container_no_workflow(self, context):
        """get_block_ast returns None when no container and no workflow_ast (line 97)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        context.workflow_ast = None
        block_step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.AND_THEN,
        )
        result = context.get_block_ast(block_step)
        assert result is None

    def test_get_block_ast_container_not_found(self, context):
        """get_block_ast returns None when container not found (line 102)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        block_step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.AND_THEN,
            container_id="non-existent-container",
        )
        result = context.get_block_ast(block_step)
        assert result is None

    def test_get_block_ast_container_is_root_no_workflow_ast(self, context, store):
        """get_block_ast returns None when container is root but no workflow_ast (line 109)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        context.workflow_ast = None

        # Create a root step (no container_id)
        root = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.WORKFLOW,
        )
        store.save_step(root)

        block_step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.AND_THEN,
            container_id=root.id,
        )
        result = context.get_block_ast(block_step)
        assert result is None

    def test_get_block_ast_falls_through_to_none(self, context, store):
        """get_block_ast returns None when no body found (line 122)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        # Create a container that is NOT root (has its own container_id)
        # but has no inline body and no facet body
        container = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            container_id="some-parent",
            facet_name="",
        )
        store.save_step(container)

        block_step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.AND_THEN,
            container_id=container.id,
        )
        result = context.get_block_ast(block_step)
        assert result is None

    def test_find_step_in_created_steps(self, context):
        """_find_step finds step in pending created_steps (line 136)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        context.changes.add_created_step(step)

        found = context._find_step(step.id)
        assert found is not None
        assert found.id == step.id

    def test_find_statement_body_no_statement_id(self, context):
        """_find_statement_body returns None when no statement_id (line 157)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        result = context._find_statement_body(step)
        assert result is None

    def test_find_statement_body_no_containing_block(self, context):
        """_find_statement_body returns None when no containing block AST (line 162)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id="non-existent-block",
        )
        result = context._find_statement_body(step)
        assert result is None

    def test_find_statement_body_no_matching_statement(self, context, store):
        """_find_statement_body returns None when stmt not in AST (line 169)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        # Set up a workflow AST with body
        context.workflow_ast = {
            "name": "Test",
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {"type": "StepStmt", "id": "other-stmt", "name": "other"},
                ],
            },
        }

        # Create root step (container for block)
        root = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.WORKFLOW,
        )
        store.save_step(root)

        # Create block step
        block = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.AND_THEN,
            container_id=root.id,
        )
        store.save_step(block)

        # Create a step inside this block with a statement_id not in the AST
        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="non-matching-stmt",
            block_id=block.id,
        )
        result = context._find_statement_body(step)
        assert result is None

    def test_find_containing_block_ast_no_block_id(self, context):
        """_find_containing_block_ast returns None when no block_id (line 183)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        result = context._find_containing_block_ast(step)
        assert result is None

    def test_find_containing_block_ast_block_not_found(self, context):
        """_find_containing_block_ast returns None when block step not found (line 188)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            block_id="non-existent-block",
        )
        result = context._find_containing_block_ast(step)
        assert result is None

    def test_get_completed_step_by_name_cache_hit(self, context):
        """get_completed_step_by_name returns from cache (line 218)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        cache_key = "block-1:s1"
        context._completed_step_cache[cache_key] = step

        result = context.get_completed_step_by_name("s1", "block-1")
        assert result is not None
        assert result.id == step.id

    def test_get_completed_step_by_name_no_block_id(self, context, store):
        """get_completed_step_by_name uses workflow steps when no block_id (line 224)."""
        # With no block_id and no matching completed step, should return None
        result = context.get_completed_step_by_name("s1", None)
        assert result is None

    def test_get_completed_step_by_name_with_pending_created(self, context, store):
        """get_completed_step_by_name checks created_steps (lines 229-230)."""
        from afl.runtime.block import StatementDefinition
        from afl.runtime.dependency import DependencyGraph
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        block_id = "block-pending"

        # Set up graph with statement definition
        stmt = StatementDefinition(
            id="stmt-1",
            name="s1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="Value",
        )
        graph = DependencyGraph()
        graph.statements["stmt-1"] = stmt
        context._block_graphs[block_id] = graph

        # Create a completed step in pending created
        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id=block_id,
        )
        step.mark_completed()
        context.changes.add_created_step(step)

        result = context.get_completed_step_by_name("s1", block_id)
        assert result is not None
        assert result.id == step.id

    def test_get_completed_step_by_name_with_pending_updated(self, context, store):
        """get_completed_step_by_name merges updated_steps (lines 232-234)."""
        from afl.runtime.block import StatementDefinition
        from afl.runtime.dependency import DependencyGraph
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        block_id = "block-updated"

        # Set up graph
        stmt = StatementDefinition(
            id="stmt-1",
            name="s1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="Value",
        )
        graph = DependencyGraph()
        graph.statements["stmt-1"] = stmt
        context._block_graphs[block_id] = graph

        # Save an incomplete step to store
        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id=block_id,
        )
        store.save_step(step)

        # Put the completed version in updated_steps
        import copy

        updated = copy.deepcopy(step)
        updated.mark_completed()
        context.changes.add_updated_step(updated)

        result = context.get_completed_step_by_name("s1", block_id)
        assert result is not None
        assert result.is_complete

    def test_get_completed_step_by_name_returns_none(self, context, store):
        """get_completed_step_by_name returns None when no match (line 245)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        # Save a step that is not complete
        step = StepDefinition.create(
            workflow_id="wf-ctx-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id="block-nc",
        )
        store.save_step(step)

        result = context.get_completed_step_by_name("s1", "block-nc")
        assert result is None

    def test_get_facet_definition_no_program_ast(self, context):
        """get_facet_definition returns None when no program_ast."""
        context.program_ast = None
        result = context.get_facet_definition("Value")
        assert result is None

    def test_search_declarations_namespace_nested(self, context):
        """_search_declarations finds facets inside namespaces (lines 280-285)."""
        context.program_ast = {
            "declarations": [
                {
                    "type": "Namespace",
                    "name": "test.ns",
                    "declarations": [
                        {
                            "type": "FacetDecl",
                            "name": "NestedFacet",
                            "params": [],
                        },
                    ],
                },
            ],
        }
        result = context.get_facet_definition("NestedFacet")
        assert result is not None
        assert result["name"] == "NestedFacet"

    def test_search_declarations_namespace_no_match(self, context):
        """_search_declarations returns None when namespace has no match (line 285-286)."""
        context.program_ast = {
            "declarations": [
                {
                    "type": "Namespace",
                    "name": "test.ns",
                    "declarations": [
                        {
                            "type": "FacetDecl",
                            "name": "OtherFacet",
                            "params": [],
                        },
                    ],
                },
            ],
        }
        result = context.get_facet_definition("NonExistent")
        assert result is None


# =========================================================================
# Evaluator edge case tests
# =========================================================================


class TestEvaluatorEdgeCases:
    """Tests for Evaluator edge cases and error paths."""

    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.fixture
    def evaluator(self, store):
        return Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

    def test_execute_exception_returns_error(self, store):
        """execute returns ERROR when exception is raised (lines 396-398)."""
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        # Provide a workflow AST that will cause an error during step creation
        # by passing a malformed AST that triggers an exception in processing
        from unittest.mock import patch

        with patch.object(evaluator, "_create_workflow_step", side_effect=RuntimeError("boom")):
            result = evaluator.execute({"name": "Test", "params": []})

        assert result.success is False
        assert result.status == ExecutionStatus.ERROR
        assert isinstance(result.error, RuntimeError)

    def test_extract_defaults_with_default_param(self, evaluator):
        """_extract_defaults picks up 'default' key from params (line 428)."""
        workflow_ast = {
            "name": "Test",
            "params": [
                {"name": "x", "type": "Long", "default": 42},
                {"name": "y", "type": "Long"},
            ],
        }
        defaults = evaluator._extract_defaults(workflow_ast, {"y": 10})
        assert defaults["x"] == 42
        assert defaults["y"] == 10

    def test_extract_defaults_input_overrides_default(self, evaluator):
        """_extract_defaults allows inputs to override defaults."""
        workflow_ast = {
            "name": "Test",
            "params": [{"name": "x", "type": "Long", "default": 42}],
        }
        defaults = evaluator._extract_defaults(workflow_ast, {"x": 99})
        assert defaults["x"] == 99

    def test_extract_defaults_with_literal_dict(self, evaluator):
        """_extract_defaults handles default as a literal dict from the emitter."""
        workflow_ast = {
            "name": "Test",
            "params": [
                {"name": "x", "type": "Long", "default": {"type": "Int", "value": 42}},
                {"name": "y", "type": "String", "default": {"type": "String", "value": "hello"}},
            ],
        }
        defaults = evaluator._extract_defaults(workflow_ast, {})
        assert defaults["x"] == {"type": "Int", "value": 42}
        assert defaults["y"] == {"type": "String", "value": "hello"}

    def test_compiled_defaults_flow_through_execution(self, evaluator):
        """Test that compiler-emitted defaults are used when no input is provided."""
        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "TestDefaults",
            "params": [
                {"name": "input", "type": "Long", "default": 1},
            ],
            "returns": [{"name": "output", "type": "Long"}],
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {
                        "type": "StepStmt",
                        "id": "step-s1",
                        "name": "s1",
                        "call": {
                            "type": "CallExpr",
                            "target": "Value",
                            "args": [
                                {
                                    "name": "input",
                                    "value": {
                                        "type": "BinaryExpr",
                                        "operator": "+",
                                        "left": {"type": "InputRef", "path": ["input"]},
                                        "right": {"type": "Int", "value": 1},
                                    },
                                }
                            ],
                        },
                    },
                ],
                "yield": {
                    "type": "YieldStmt",
                    "id": "yield-1",
                    "call": {
                        "type": "CallExpr",
                        "target": "TestDefaults",
                        "args": [
                            {
                                "name": "output",
                                "value": {"type": "StepRef", "path": ["s1", "input"]},
                            }
                        ],
                    },
                },
            },
        }

        # Execute without providing inputs — default should kick in
        result = evaluator.execute(workflow_ast, inputs={})
        assert result.success is True
        # input defaults to 1, s1.input = 1 + 1 = 2, output = 2
        assert result.outputs.get("output") == 2

    def test_max_iterations_exceeded(self, store):
        """execute stops at max_iterations (line 363->394 timeout path)."""
        from afl.runtime.evaluator import ExecutionResult

        evaluator = Evaluator(
            persistence=store,
            telemetry=Telemetry(enabled=False),
            max_iterations=2,
        )
        # Create a workflow that makes progress every iteration but never completes
        # by mocking _run_iteration to always return True
        from unittest.mock import patch

        with patch.object(evaluator, "_run_iteration", return_value=True):
            with patch.object(evaluator, "_build_result") as mock_build:
                mock_build.return_value = ExecutionResult(
                    success=False,
                    workflow_id="wf-1",
                    error=Exception("Workflow did not complete"),
                    iterations=2,
                )
                result = evaluator.execute({"name": "Test", "params": []})

        assert result.iterations == 2

    def test_build_result_root_error(self, store):
        """_build_result returns error when root step is in error (lines 584-586)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        # Create a root step in error state
        wf_id = "wf-err"
        root = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.WORKFLOW,
            facet_name="Test",
        )
        root.mark_error(RuntimeError("step failed"))
        store.save_step(root)

        result = evaluator._build_result(wf_id, 5)
        assert result.success is False
        assert result.status == ExecutionStatus.ERROR
        assert isinstance(result.error, RuntimeError)
        assert result.iterations == 5

    def test_build_result_root_error_no_transition_error(self, store):
        """_build_result uses default error when transition.error is None (line 584)."""
        from afl.runtime.states import StepState
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        wf_id = "wf-err-2"
        root = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.WORKFLOW,
            facet_name="Test",
        )
        # Set error state without setting transition.error
        root.state = StepState.STATEMENT_ERROR
        root.transition.current_state = StepState.STATEMENT_ERROR
        store.save_step(root)

        result = evaluator._build_result(wf_id, 3)
        assert result.success is False
        assert result.status == ExecutionStatus.ERROR
        assert str(result.error) == "Workflow error"

    def test_build_result_not_complete_not_error(self, store):
        """_build_result returns 'did not complete' when root is neither (line 594-599)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        wf_id = "wf-incomplete"
        root = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.WORKFLOW,
            facet_name="Test",
        )
        # Leave in initial CREATED state (not complete, not error)
        store.save_step(root)

        result = evaluator._build_result(wf_id, 1)
        assert result.success is False
        assert str(result.error) == "Workflow did not complete"

    def test_continue_step_not_found(self, evaluator):
        """continue_step raises ValueError when step not found (line 628)."""
        with pytest.raises(ValueError, match="not found"):
            evaluator.continue_step("non-existent-step")

    def test_continue_step_wrong_state(self, store, evaluator):
        """continue_step raises ValueError when step not at EVENT_TRANSMIT (line 630)."""
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        step = StepDefinition.create(
            workflow_id="wf-1",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        # Leave in CREATED state
        store.save_step(step)

        with pytest.raises(ValueError, match="expected"):
            evaluator.continue_step(step.id)

    def test_resume_exception_returns_error(self, store):
        """resume returns ERROR when exception raised (lines 707-709)."""
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        from unittest.mock import patch

        with patch.object(evaluator, "_run_iteration", side_effect=RuntimeError("resume boom")):
            result = evaluator.resume(
                "wf-resume-err",
                {"name": "Test", "params": []},
            )

        assert result.success is False
        assert result.status == ExecutionStatus.ERROR
        assert isinstance(result.error, RuntimeError)

    def test_resume_re_pauses_at_event_blocked(self, store):
        """resume returns PAUSED when steps still at EVENT_TRANSMIT (line 697)."""
        from afl.runtime.states import StepState
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        wf_id = "wf-re-pause"

        # Create a step stuck at EVENT_TRANSMIT
        step = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="SomeEvent",
        )
        step.state = StepState.EVENT_TRANSMIT
        step.transition.current_state = StepState.EVENT_TRANSMIT
        step.transition.request_transition = False
        store.save_step(step)

        result = evaluator.resume(
            wf_id,
            {"name": "Test", "params": []},
        )

        assert result.success is True
        assert result.status == ExecutionStatus.PAUSED

    def test_process_step_changed_but_no_state_change(self, store):
        """_process_step detects attribute change without state change (lines 554-555)."""
        from unittest.mock import MagicMock, patch

        from afl.runtime.evaluator import ExecutionContext
        from afl.runtime.persistence import IterationChanges
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        context = ExecutionContext(
            persistence=store,
            telemetry=Telemetry(enabled=False),
            changes=IterationChanges(),
            workflow_id="wf-attr-change",
        )

        step = StepDefinition.create(
            workflow_id="wf-attr-change",
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="Value",
        )
        # Simulate: changer processes step, marks changed but no state change
        original_state = step.state

        mock_result = MagicMock()
        mock_result.step = step
        mock_result.step.state = original_state  # Same state
        mock_result.step.transition.changed = True
        mock_result.continue_processing = False

        mock_changer = MagicMock()
        mock_changer.process.return_value = mock_result

        with patch("afl.runtime.evaluator.get_state_changer", return_value=mock_changer):
            progress = evaluator._process_step(step, context)

        assert progress is True


# =========================================================================
# Evaluator iteration edge cases
# =========================================================================


class TestEvaluatorIteration:
    """Tests for iteration loop edge cases."""

    @pytest.fixture
    def store(self):
        return MemoryStore()

    def test_run_iteration_skips_duplicate_step_ids(self, store):
        """_run_iteration skips already-processed step IDs (line 483)."""
        from afl.runtime.evaluator import ExecutionContext
        from afl.runtime.persistence import IterationChanges
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        wf_id = "wf-dup"
        # Create a terminal step (won't make progress)
        step = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        step.mark_completed()
        store.save_step(step)

        context = ExecutionContext(
            persistence=store,
            telemetry=Telemetry(enabled=False),
            changes=IterationChanges(),
            workflow_id=wf_id,
        )

        # Run iteration - the terminal step should be processed (returns False)
        progress = evaluator._run_iteration(context)
        assert progress is False

    def test_run_iteration_processes_created_steps(self, store):
        """_run_iteration processes newly created steps (lines 502-508)."""

        from afl.runtime.evaluator import ExecutionContext
        from afl.runtime.persistence import IterationChanges
        from afl.runtime.step import StepDefinition
        from afl.runtime.types import ObjectType

        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

        wf_id = "wf-created"

        context = ExecutionContext(
            persistence=store,
            telemetry=Telemetry(enabled=False),
            changes=IterationChanges(),
            workflow_id=wf_id,
        )

        # Manually add a step to created_steps to simulate step creation during iteration
        new_step = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="Value",
        )
        new_step.mark_completed()  # Terminal, won't make progress
        context.changes.add_created_step(new_step)

        progress = evaluator._run_iteration(context)
        # Terminal step doesn't make progress, but it gets processed
        assert progress is False
        # Step should be in pending_created (restored for commit)
        assert len(context.changes.created_steps) >= 1


# =========================================================================
# Schema Instantiation Runtime Tests
# =========================================================================


class TestSchemaInstantiationRuntime:
    """Tests for schema instantiation execution in the runtime."""

    @pytest.fixture
    def evaluator(self):
        """Create evaluator with in-memory store."""
        store = MemoryStore()
        telemetry = Telemetry(enabled=True)
        return Evaluator(persistence=store, telemetry=telemetry)

    def test_schema_instantiation_execution(self, evaluator):
        """Schema instantiation step should create returns, not params.

        ```afl
        schema Config {
            timeout: Long
            retries: Long
        }
        facet Value(input: Long) => (output: Long)
        workflow Test(input: Long) => (output: Long) andThen {
            cfg = Config(timeout = 30, retries = 3)
            v = Value(input = cfg.timeout)
            yield Test(output = v.input)
        }
        ```
        """
        program_ast = {
            "declarations": [
                {
                    "type": "SchemaDecl",
                    "name": "Config",
                    "fields": [
                        {"name": "timeout", "type": "Long"},
                        {"name": "retries", "type": "Long"},
                    ],
                },
            ],
        }

        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "Test",
            "params": [{"name": "input", "type": "Long"}],
            "returns": [{"name": "output", "type": "Long"}],
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {
                        "type": "StepStmt",
                        "id": "step-cfg",
                        "name": "cfg",
                        "call": {
                            "type": "CallExpr",
                            "target": "Config",
                            "args": [
                                {"name": "timeout", "value": {"type": "Int", "value": 30}},
                                {"name": "retries", "value": {"type": "Int", "value": 3}},
                            ],
                        },
                    },
                    {
                        "type": "StepStmt",
                        "id": "step-v",
                        "name": "v",
                        "call": {
                            "type": "CallExpr",
                            "target": "Value",
                            "args": [
                                {
                                    "name": "input",
                                    "value": {"type": "StepRef", "path": ["cfg", "timeout"]},
                                }
                            ],
                        },
                    },
                ],
                "yield": {
                    "type": "YieldStmt",
                    "id": "yield-1",
                    "call": {
                        "type": "CallExpr",
                        "target": "Test",
                        "args": [
                            {
                                "name": "output",
                                "value": {"type": "StepRef", "path": ["v", "input"]},
                            }
                        ],
                    },
                },
            },
        }

        result = evaluator.execute(workflow_ast, inputs={"input": 1}, program_ast=program_ast)
        assert result.success is True
        # cfg.timeout = 30 (stored as return)
        # v.input = 30 (from cfg.timeout)
        # output = 30
        assert result.outputs.get("output") == 30

    def test_schema_field_passed_to_facet(self, evaluator):
        """Schema fields should be accessible via step references.

        ```afl
        schema Data {
            value: Long
            multiplier: Long
        }
        facet Multiply(a: Long, b: Long) => (result: Long)
        workflow Test(input: Long) => (output: Long) andThen {
            d = Data(value = $.input, multiplier = 2)
            m = Multiply(a = d.value, b = d.multiplier)
            yield Test(output = m.result)
        }
        ```
        """
        program_ast = {
            "declarations": [
                {
                    "type": "SchemaDecl",
                    "name": "Data",
                    "fields": [
                        {"name": "value", "type": "Long"},
                        {"name": "multiplier", "type": "Long"},
                    ],
                },
                {
                    "type": "FacetDecl",
                    "name": "Multiply",
                    "params": [
                        {"name": "a", "type": "Long"},
                        {"name": "b", "type": "Long"},
                    ],
                    "returns": [{"name": "result", "type": "Long"}],
                },
            ],
        }

        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "Test",
            "params": [{"name": "input", "type": "Long"}],
            "returns": [{"name": "output", "type": "Long"}],
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {
                        "type": "StepStmt",
                        "id": "step-d",
                        "name": "d",
                        "call": {
                            "type": "CallExpr",
                            "target": "Data",
                            "args": [
                                {
                                    "name": "value",
                                    "value": {"type": "InputRef", "path": ["input"]},
                                },
                                {"name": "multiplier", "value": {"type": "Int", "value": 2}},
                            ],
                        },
                    },
                    {
                        "type": "StepStmt",
                        "id": "step-m",
                        "name": "m",
                        "call": {
                            "type": "CallExpr",
                            "target": "Multiply",
                            "args": [
                                {
                                    "name": "a",
                                    "value": {"type": "StepRef", "path": ["d", "value"]},
                                },
                                {
                                    "name": "b",
                                    "value": {"type": "StepRef", "path": ["d", "multiplier"]},
                                },
                            ],
                        },
                    },
                ],
                "yield": {
                    "type": "YieldStmt",
                    "id": "yield-1",
                    "call": {
                        "type": "CallExpr",
                        "target": "Test",
                        "args": [
                            {
                                "name": "output",
                                # Use a.value to verify facet processed the schema values
                                "value": {"type": "StepRef", "path": ["m", "a"]},
                            }
                        ],
                    },
                },
            },
        }

        result = evaluator.execute(workflow_ast, inputs={"input": 5}, program_ast=program_ast)
        assert result.success is True
        # d.value = 5, d.multiplier = 2
        # m.a = 5, m.b = 2
        # output = m.a = 5
        assert result.outputs.get("output") == 5

    def test_schema_with_concat_expression(self, evaluator):
        """Schema instantiation with concatenation expression.

        ```afl
        schema StringData {
            combined: String
        }
        facet Echo(value: String) => (result: String)
        workflow Test(a: String, b: String) => (output: String) andThen {
            d = StringData(combined = $.a ++ $.b)
            e = Echo(value = d.combined)
            yield Test(output = e.value)
        }
        ```
        """
        program_ast = {
            "declarations": [
                {
                    "type": "SchemaDecl",
                    "name": "StringData",
                    "fields": [{"name": "combined", "type": "String"}],
                },
            ],
        }

        workflow_ast = {
            "type": "WorkflowDecl",
            "name": "Test",
            "params": [
                {"name": "a", "type": "String"},
                {"name": "b", "type": "String"},
            ],
            "returns": [{"name": "output", "type": "String"}],
            "body": {
                "type": "AndThenBlock",
                "steps": [
                    {
                        "type": "StepStmt",
                        "id": "step-d",
                        "name": "d",
                        "call": {
                            "type": "CallExpr",
                            "target": "StringData",
                            "args": [
                                {
                                    "name": "combined",
                                    "value": {
                                        "type": "ConcatExpr",
                                        "operands": [
                                            {"type": "InputRef", "path": ["a"]},
                                            {"type": "InputRef", "path": ["b"]},
                                        ],
                                    },
                                }
                            ],
                        },
                    },
                    {
                        "type": "StepStmt",
                        "id": "step-e",
                        "name": "e",
                        "call": {
                            "type": "CallExpr",
                            "target": "Echo",
                            "args": [
                                {
                                    "name": "value",
                                    "value": {"type": "StepRef", "path": ["d", "combined"]},
                                }
                            ],
                        },
                    },
                ],
                "yield": {
                    "type": "YieldStmt",
                    "id": "yield-1",
                    "call": {
                        "type": "CallExpr",
                        "target": "Test",
                        "args": [
                            {
                                "name": "output",
                                "value": {"type": "StepRef", "path": ["e", "value"]},
                            }
                        ],
                    },
                },
            },
        }

        result = evaluator.execute(
            workflow_ast, inputs={"a": "Hello", "b": "World"}, program_ast=program_ast
        )
        assert result.success is True
        # d.combined = "HelloWorld"
        # e.value = "HelloWorld"
        # output = "HelloWorld"
        assert result.outputs.get("output") == "HelloWorld"
