## Acceptance Tests (80_acceptance_tests.md)

The implementation includes pytest tests that verify parser and emitter correctness.

---

## Test Summary

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_parser.py` | 50 | Parser functionality |
| `tests/test_emitter.py` | 34 | JSON emission |
| `tests/test_validator.py` | 40 | Semantic validation |
| **Total** | **124** | **~82%** |

---

## Parser Tests (`test_parser.py`)

### Basic Parsing
- `test_empty_program` - Empty input produces empty program
- `test_simple_facet` - Parse basic facet declaration
- `test_facet_multiple_params` - Multiple parameter parsing
- `test_facet_no_params` - Empty parameter list
- `test_facet_with_return` - Return clause parsing

### Event Facets
- `test_event_facet` - Parse `event facet` declarations

### Workflows
- `test_simple_workflow` - Basic workflow declaration
- `test_workflow_with_body` - AndThen block with steps and yield

### Namespaces
- `test_simple_namespace` - Namespace with contents
- `test_namespace_with_uses` - Uses declarations
- `test_namespace_with_workflow` - Full namespace example

### Mixins
- `test_mixin_in_signature` - Mixin in facet signature
- `test_mixin_call_with_alias` - Mixin call with `as` alias

### Implicits
- `test_implicit_decl` - Implicit declarations

### References
- `test_input_reference` - `$.field` references
- `test_step_reference` - `step.field` references
- `test_nested_reference` - Nested path references

### Literals
- `test_string_literal` - String parsing
- `test_integer_literal` - Integer parsing
- `test_boolean_literal` - Boolean parsing (true/false)
- `test_null_literal` - Null parsing

### Foreach
- `test_foreach_in_workflow` - Foreach iteration

### Comments
- `test_line_comment` - `//` comments ignored
- `test_block_comment` - `/* */` comments ignored

### Types
- `test_builtin_types` - All builtin types (String, Long, Int, Boolean, Json)
- `test_qualified_type` - Qualified type names

### Error Reporting
- `test_unexpected_token` - Error includes line/column
- `test_missing_parenthesis` - Missing token errors
- `test_invalid_return_clause` - Invalid syntax errors

### Other
- `test_parse_function` - Convenience function
- `test_facet_has_location` - Source location tracking
- `test_multiple_facets` - Multiple declarations
- `test_mixed_declarations` - Mixed declaration types
- `test_semicolon_separator` - Semicolon separators
- `test_mixed_separators` - Mixed newlines and semicolons

### Concat Expression
- `test_simple_concat` - Parse `++` operator
- `test_multi_concat` - Multiple concat operands
- `test_concat_with_newlines` - Newlines after `++`

### Use Declaration
- `test_use_singular` - Parse `use` (singular form)
- `test_multiple_use_declarations` - Multiple `use` statements

### Default Parameter Values
- `test_string_default` - Parse string default value
- `test_integer_default` - Parse integer default value
- `test_boolean_default` - Parse boolean default value
- `test_null_default` - Parse null default value
- `test_no_default` - Parameters without defaults have default=None
- `test_mixed_defaults` - Mix of params with and without defaults
- `test_workflow_with_defaults` - Workflow params and return defaults
- `test_event_facet_with_defaults` - Event facet with defaults
- `test_multiple_defaults` - Multiple parameters with defaults
- `test_reference_default` - Parameter with literal default in workflow context

---

## Emitter Tests (`test_emitter.py`)

### Basic Emission
- `test_empty_program` - Empty program JSON
- `test_simple_facet` - Facet to JSON
- `test_facet_with_return` - Return clause emission
- `test_event_facet` - Event facet type
- `test_workflow` - Workflow emission

### Workflow Body
- `test_workflow_with_steps` - Steps and yield emission
- `test_foreach` - Foreach clause emission

### References
- `test_input_ref` - InputRef JSON format
- `test_step_ref` - StepRef JSON format
- `test_nested_ref` - Nested path emission

### Literals
- `test_string_literal` - String JSON format
- `test_integer_literal` - Int JSON format
- `test_boolean_literal` - Boolean JSON format
- `test_null_literal` - Null JSON format

### Mixins
- `test_mixin_in_signature` - MixinSig emission
- `test_mixin_call_with_alias` - MixinCall with alias

### Namespaces
- `test_namespace` - Full namespace emission

### Implicits
- `test_implicit` - Implicit declaration emission

### Locations
- `test_locations_included` - Location fields present
- `test_locations_excluded` - Location fields absent

### Convenience Functions
- `test_emit_json` - `emit_json()` function
- `test_emit_dict` - `emit_dict()` function
- `test_compact_json` - Compact output mode

### Complex Examples
- `test_full_workflow` - Real-world workflow example

### Default Parameter Values
- `test_string_default` - String default value emitted correctly
- `test_integer_default` - Integer default value emitted correctly
- `test_boolean_default` - Boolean default value emitted correctly
- `test_null_default` - Null default value emitted correctly
- `test_no_default_omits_key` - No default key when absent
- `test_mixed_defaults` - Mix of params with and without defaults
- `test_workflow_defaults_roundtrip` - Workflow params and returns with defaults
- `test_default_in_json_output` - Default survives JSON serialization

### JSON Validity
- `test_valid_json_output` - Output is valid JSON
- `test_roundtrip_consistency` - Consistent output

---

## Validator Tests (`test_validator.py`)

### Name Uniqueness
- `test_duplicate_facet_names` - Duplicate facets error
- `test_duplicate_workflow_names` - Duplicate workflows error
- `test_duplicate_event_facet_names` - Duplicate event facets error
- `test_facet_workflow_same_name` - Mixed type duplicates error
- `test_unique_names_valid` - Unique names pass
- `test_duplicate_names_in_namespace` - Namespace duplicate error
- `test_same_name_different_namespaces` - Cross-namespace OK
- `test_duplicate_step_names` - Duplicate steps error
- `test_unique_step_names_valid` - Unique steps pass

### Step References
- `test_valid_input_reference` - `$.param` OK
- `test_invalid_input_reference` - `$.unknown` error
- `test_valid_step_reference` - `step.attr` OK
- `test_invalid_step_attribute` - Unknown attribute error
- `test_reference_undefined_step` - Unknown step error
- `test_reference_step_defined_after` - Forward reference error
- `test_foreach_variable_valid` - Foreach var OK

### Yield Validation
- `test_valid_yield_containing_facet` - Yield to self OK
- `test_invalid_yield_target` - Wrong target error
- `test_yield_to_mixin_valid` - Yield to mixin OK
- `test_yield_references_validated` - Yield refs checked
- `test_duplicate_yield_targets` - Duplicate yields error

### Other
- `test_validate_function` - Convenience function
- `test_validate_with_errors` - Returns errors
- `test_empty_result_is_valid` - Empty = valid
- `test_result_with_errors_invalid` - Errors = invalid
- `test_error_string_format` - Error formatting
- `test_error_string_no_location` - Error without location
- `test_nested_block_references` - Complex references
- `test_multiple_errors_reported` - All errors reported
- `test_full_namespace_example` - Real-world example

### Use Statement Validation
- `test_valid_use_statement` - Use existing namespace OK
- `test_invalid_use_statement` - Use nonexistent namespace error
- `test_multiple_valid_use_statements` - Multiple valid uses OK
- `test_mixed_valid_invalid_use_statements` - Mixed valid/invalid errors

### Facet Name Resolution
- `test_unambiguous_facet_reference` - Unambiguous reference OK
- `test_ambiguous_facet_reference` - Ambiguous reference error
- `test_qualified_name_resolves_ambiguity` - Qualified name OK
- `test_local_facet_takes_precedence` - Local facet wins
- `test_mixin_with_qualified_name` - Qualified mixin OK
- `test_unknown_qualified_facet` - Unknown qualified error

---

## Running Tests

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install lark pytest pytest-cov

# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run with coverage
PYTHONPATH=. pytest tests/ --cov=afl --cov-report=term-missing

# Run specific test file
PYTHONPATH=. pytest tests/test_parser.py -v

# Run specific test class
PYTHONPATH=. pytest tests/test_parser.py::TestWorkflows -v

# Run specific test
PYTHONPATH=. pytest tests/test_parser.py::TestBasicParsing::test_simple_facet -v

# Run tests matching pattern
PYTHONPATH=. pytest tests/ -k "namespace" -v
```

---

---

## Runtime Tests

The runtime implementation includes pytest tests that verify evaluator, state machine, and execution correctness.

### Runtime Test Summary

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/runtime/test_types.py` | — | Type system (StepId, BlockId, ObjectType, FacetAttributes) |
| `tests/runtime/test_states.py` | — | State constants and transitions |
| `tests/runtime/test_step.py` | — | StepDefinition and StepTransition |
| `tests/runtime/test_persistence.py` | — | PersistenceAPI and IterationChanges |
| `tests/runtime/test_dependency.py` | — | DependencyGraph from AST |
| `tests/runtime/test_expression.py` | — | Expression evaluation (InputRef, StepRef, BinaryExpr, ConcatExpr) |
| `tests/runtime/test_evaluator.py` | — | Integration tests for spec examples 21.1 and 21.2 |

### Required Runtime Tests (Partial Coverage)

The following tests are required to verify behavior described in `spec/70_examples.md` Examples 2–4. The underlying features are implemented and covered by end-to-end tests in `test_evaluator.py`, but dedicated **iteration-level trace** tests have not yet been written:

| Test Name | Validates | Spec Reference |
|-----------|-----------|----------------|
| `test_event_facet_blocks_at_transmit` | subStep1 calling event facet blocks at `EventTransmit` with `request_state_change(False)` | Example 4, §8.1 |
| `test_step_continue_resumes_step` | `StepContinue` event unblocks step from `EventTransmit` | Example 4, §12.1 |
| `test_nested_statement_block` | s1 with statement-level `andThen` creates `block_s1` | Examples 3–4, §8.2 |
| `test_facet_definition_lookup` | `EventTransmitHandler` detects `EventFacetDecl` via `get_facet_definition()` | Example 4, §11.1 |
| `test_multi_run_execution` | Evaluator pauses at fixed point, resumes after external event processing | Example 4, §10.2 |
| `test_facet_level_block_creation` | Step calling facet with `andThen` body creates block from facet definition | Examples 2–4, §8.2 |
| `test_block_ast_resolution_nested` | `BlockExecutionBegin` resolves correct AST for nested statement-level blocks | Examples 3–4, §8.3 |
| `test_example_2_full_trace` | Full iteration-by-iteration trace for Example 2 (8 steps, 8 iterations) | Example 2 |
| `test_example_3_full_trace` | Full iteration-by-iteration trace for Example 3 (11 steps, 11 iterations) | Example 3 |
| `test_example_4_full_trace` | Full iteration-by-iteration trace for Example 4 (11 steps, 2 evaluator runs) | Example 4 |

---

## Coverage Report

```
Name                      Stmts   Miss  Cover
---------------------------------------------
afl/__init__.py               5      0   100%
afl/ast.py                   78      0   100%
afl/cli.py                   47     47     0%
afl/emitter.py              223     32    81%
afl/grammar/__init__.py       0      0   100%
afl/parser.py                40      6    82%
afl/transformer.py          219     12    90%
---------------------------------------------
TOTAL                       612     97    81%
```

Note: CLI coverage is 0% because it's tested manually, not via pytest.
