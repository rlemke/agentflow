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

"""Tests for AFL JSON emitter."""

import json

import pytest

from afl import parse
from afl.emitter import JSONEmitter, emit_dict, emit_json


@pytest.fixture
def emitter():
    """Create an emitter instance."""
    return JSONEmitter(include_locations=False)


class TestBasicEmission:
    """Test basic JSON emission."""

    def test_empty_program(self, emitter):
        """Empty program emits minimal JSON."""
        ast = parse("")
        data = emitter.emit_dict(ast)
        assert data["type"] == "Program"

    def test_simple_facet(self, emitter):
        """Simple facet emits correct structure."""
        ast = parse("facet User(name: String)")
        data = emitter.emit_dict(ast)

        assert len(data["facets"]) == 1
        facet = data["facets"][0]
        assert facet["type"] == "FacetDecl"
        assert facet["name"] == "User"
        assert facet["params"] == [{"name": "name", "type": "String"}]

    def test_facet_with_return(self, emitter):
        """Facet with return clause."""
        ast = parse("facet Transform(input: String) => (output: String)")
        data = emitter.emit_dict(ast)

        facet = data["facets"][0]
        assert facet["returns"] == [{"name": "output", "type": "String"}]

    def test_event_facet(self, emitter):
        """Event facet emits correct type."""
        ast = parse("event facet Process(input: String) => (output: String)")
        data = emitter.emit_dict(ast)

        assert len(data["eventFacets"]) == 1
        ef = data["eventFacets"][0]
        assert ef["type"] == "EventFacetDecl"
        assert ef["name"] == "Process"

    def test_workflow(self, emitter):
        """Workflow emits correct type."""
        ast = parse("workflow Main(input: String) => (output: String)")
        data = emitter.emit_dict(ast)

        assert len(data["workflows"]) == 1
        wf = data["workflows"][0]
        assert wf["type"] == "WorkflowDecl"
        assert wf["name"] == "Main"


class TestWorkflowBody:
    """Test workflow body emission."""

    def test_workflow_with_steps(self, emitter):
        """Workflow with andThen block."""
        ast = parse("""
        workflow Test(input: String) => (output: String) andThen {
            step1 = Process(value = $.input)
            step2 = Transform(data = step1.result)
            yield Test(output = step2.value)
        }
        """)
        data = emitter.emit_dict(ast)

        wf = data["workflows"][0]
        body = wf["body"]
        assert body["type"] == "AndThenBlock"
        assert len(body["steps"]) == 2

        # Check first step
        step1 = body["steps"][0]
        assert step1["type"] == "StepStmt"
        assert step1["name"] == "step1"
        assert step1["call"]["target"] == "Process"

        # Check yield
        assert body["yield"]["type"] == "YieldStmt"
        assert body["yield"]["call"]["target"] == "Test"

    def test_foreach(self, emitter):
        """Workflow with foreach."""
        ast = parse("""
        workflow ProcessAll(items: Json) => (results: Json) andThen foreach item in $.items {
            result = Process(data = item.value)
            yield ProcessAll(results = result.output)
        }
        """)
        data = emitter.emit_dict(ast)

        body = data["workflows"][0]["body"]
        assert body["foreach"]["type"] == "ForeachClause"
        assert body["foreach"]["variable"] == "item"
        assert body["foreach"]["iterable"] == {"type": "InputRef", "path": ["items"]}


class TestReferences:
    """Test reference emission."""

    def test_input_ref(self, emitter):
        """Input reference ($.field)."""
        ast = parse("""
        workflow Test(input: String) andThen {
            step = Process(value = $.input)
        }
        """)
        data = emitter.emit_dict(ast)

        arg = data["workflows"][0]["body"]["steps"][0]["call"]["args"][0]
        assert arg["value"] == {"type": "InputRef", "path": ["input"]}

    def test_step_ref(self, emitter):
        """Step reference (step.field)."""
        ast = parse("""
        workflow Test(input: String) andThen {
            step1 = Process(value = $.input)
            step2 = Transform(data = step1.output)
        }
        """)
        data = emitter.emit_dict(ast)

        arg = data["workflows"][0]["body"]["steps"][1]["call"]["args"][0]
        assert arg["value"] == {"type": "StepRef", "path": ["step1", "output"]}

    def test_nested_ref(self, emitter):
        """Nested reference path."""
        ast = parse("""
        workflow Test(data: Json) andThen {
            step = Process(value = $.data.nested.field)
        }
        """)
        data = emitter.emit_dict(ast)

        arg = data["workflows"][0]["body"]["steps"][0]["call"]["args"][0]
        assert arg["value"] == {"type": "InputRef", "path": ["data", "nested", "field"]}


class TestLiterals:
    """Test literal emission."""

    def test_string_literal(self, emitter):
        """String literal."""
        ast = parse('implicit msg = Message(text = "hello")')
        data = emitter.emit_dict(ast)

        arg = data["implicits"][0]["call"]["args"][0]
        assert arg["value"] == {"type": "String", "value": "hello"}

    def test_integer_literal(self, emitter):
        """Integer literal."""
        ast = parse("implicit count = Counter(value = 42)")
        data = emitter.emit_dict(ast)

        arg = data["implicits"][0]["call"]["args"][0]
        assert arg["value"] == {"type": "Int", "value": 42}

    def test_boolean_literal(self, emitter):
        """Boolean literals."""
        ast = parse("implicit flag = Config(enabled = true, disabled = false)")
        data = emitter.emit_dict(ast)

        args = data["implicits"][0]["call"]["args"]
        assert args[0]["value"] == {"type": "Boolean", "value": True}
        assert args[1]["value"] == {"type": "Boolean", "value": False}

    def test_null_literal(self, emitter):
        """Null literal."""
        ast = parse("implicit opt = Optional(value = null)")
        data = emitter.emit_dict(ast)

        arg = data["implicits"][0]["call"]["args"][0]
        assert arg["value"] == {"type": "Null"}


class TestMixins:
    """Test mixin emission."""

    def test_mixin_in_signature(self, emitter):
        """Mixin in facet signature."""
        ast = parse("facet Job(input: String) with Retry(maxAttempts = 3)")
        data = emitter.emit_dict(ast)

        mixins = data["facets"][0]["mixins"]
        assert len(mixins) == 1
        assert mixins[0]["target"] == "Retry"
        assert mixins[0]["args"] == [{"name": "maxAttempts", "value": {"type": "Int", "value": 3}}]

    def test_mixin_call_with_alias(self, emitter):
        """Mixin call with alias."""
        ast = parse("""
        workflow Test(input: String) andThen {
            job = RunJob(input = $.input) with User(name = "test") as user
        }
        """)
        data = emitter.emit_dict(ast)

        mixins = data["workflows"][0]["body"]["steps"][0]["call"]["mixins"]
        assert len(mixins) == 1
        assert mixins[0]["target"] == "User"
        assert mixins[0]["alias"] == "user"


class TestNamespaces:
    """Test namespace emission."""

    def test_namespace(self, emitter):
        """Namespace with contents."""
        ast = parse("""
        namespace team.data.processing {
            uses team.common.utils
            uses team.other

            facet Data(value: String)
            workflow Process(input: String) => (output: String)
        }
        """)
        data = emitter.emit_dict(ast)

        ns = data["namespaces"][0]
        assert ns["type"] == "Namespace"
        assert ns["name"] == "team.data.processing"
        assert ns["uses"] == ["team.common.utils", "team.other"]
        assert len(ns["facets"]) == 1
        assert len(ns["workflows"]) == 1


class TestImplicits:
    """Test implicit declaration emission."""

    def test_implicit(self, emitter):
        """Implicit declaration."""
        ast = parse('implicit user = User(name = "system", email = "sys@test.com")')
        data = emitter.emit_dict(ast)

        impl = data["implicits"][0]
        assert impl["type"] == "ImplicitDecl"
        assert impl["name"] == "user"
        assert impl["call"]["target"] == "User"


class TestLocations:
    """Test source location emission."""

    def test_locations_included(self):
        """Locations included by default."""
        emitter = JSONEmitter(include_locations=True)
        ast = parse("facet Test()")
        data = emitter.emit_dict(ast)

        assert "location" in data["facets"][0]
        loc = data["facets"][0]["location"]
        assert "line" in loc
        assert "column" in loc

    def test_locations_excluded(self):
        """Locations can be excluded."""
        emitter = JSONEmitter(include_locations=False)
        ast = parse("facet Test()")
        data = emitter.emit_dict(ast)

        assert "location" not in data["facets"][0]


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_emit_json(self):
        """Test emit_json function."""
        ast = parse("facet Test()")
        result = emit_json(ast)

        assert isinstance(result, str)
        data = json.loads(result)
        assert data["type"] == "Program"

    def test_emit_dict(self):
        """Test emit_dict function."""
        ast = parse("facet Test()")
        result = emit_dict(ast)

        assert isinstance(result, dict)
        assert result["type"] == "Program"

    def test_compact_json(self):
        """Test compact JSON output."""
        ast = parse("facet Test()")
        result = emit_json(ast, indent=None)

        assert "\n" not in result


class TestComplexExample:
    """Test complex real-world example."""

    def test_full_workflow(self, emitter):
        """Full workflow with all features."""
        ast = parse("""
        namespace team.email {
            uses team.common.types

            facet EmailConfig(smtpHost: String, smtpPort: Int)

            event facet SendEmail(to: String, subject: String, body: String) => (messageId: String)

            implicit config = EmailConfig(smtpHost = "smtp.example.com", smtpPort = 587)

            workflow BulkSend(recipients: Json, template: String) => (results: Json) with Retry(maxAttempts = 3) andThen foreach recipient in $.recipients {
                email = SendEmail(
                    to = recipient.email,
                    subject = "Hello",
                    body = $.template
                ) with Config() as cfg
                yield BulkSend(results = email.messageId)
            }
        }
        """)
        data = emitter.emit_dict(ast)

        # Verify structure
        ns = data["namespaces"][0]
        assert ns["name"] == "team.email"
        assert ns["uses"] == ["team.common.types"]
        assert len(ns["facets"]) == 1
        assert len(ns["eventFacets"]) == 1
        assert len(ns["implicits"]) == 1
        assert len(ns["workflows"]) == 1

        # Verify workflow
        wf = ns["workflows"][0]
        assert wf["name"] == "BulkSend"
        assert wf["mixins"][0]["target"] == "Retry"
        assert wf["body"]["foreach"]["variable"] == "recipient"


class TestDefaultParameterValues:
    """Test default parameter value emission."""

    def test_string_default(self, emitter):
        """String default value emitted correctly."""
        ast = parse('facet Greeting(message: String = "hello")')
        data = emitter.emit_dict(ast)
        param = data["facets"][0]["params"][0]
        assert param == {
            "name": "message",
            "type": "String",
            "default": {"type": "String", "value": "hello"},
        }

    def test_integer_default(self, emitter):
        """Integer default value emitted correctly."""
        ast = parse("facet Config(retries: Int = 3)")
        data = emitter.emit_dict(ast)
        param = data["facets"][0]["params"][0]
        assert param == {"name": "retries", "type": "Int", "default": {"type": "Int", "value": 3}}

    def test_boolean_default(self, emitter):
        """Boolean default value emitted correctly."""
        ast = parse("facet Config(verbose: Boolean = true)")
        data = emitter.emit_dict(ast)
        param = data["facets"][0]["params"][0]
        assert param == {
            "name": "verbose",
            "type": "Boolean",
            "default": {"type": "Boolean", "value": True},
        }

    def test_null_default(self, emitter):
        """Null default value emitted correctly."""
        ast = parse("facet Config(extra: Json = null)")
        data = emitter.emit_dict(ast)
        param = data["facets"][0]["params"][0]
        assert param == {"name": "extra", "type": "Json", "default": {"type": "Null"}}

    def test_no_default_omits_key(self, emitter):
        """Parameters without defaults omit the default key."""
        ast = parse("facet Data(value: String)")
        data = emitter.emit_dict(ast)
        param = data["facets"][0]["params"][0]
        assert "default" not in param

    def test_mixed_defaults(self, emitter):
        """Mix of params with and without defaults."""
        ast = parse("facet Mixed(required: String, optional: Int = 42)")
        data = emitter.emit_dict(ast)
        params = data["facets"][0]["params"]
        assert "default" not in params[0]
        assert params[1]["default"] == {"type": "Int", "value": 42}

    def test_workflow_defaults_roundtrip(self, emitter):
        """Workflow params and returns with defaults round-trip correctly."""
        ast = parse('workflow MyFlow(input: String = "hello") => (output: String = "world")')
        data = emitter.emit_dict(ast)
        wf = data["workflows"][0]
        assert wf["params"][0]["default"] == {"type": "String", "value": "hello"}
        assert wf["returns"][0]["default"] == {"type": "String", "value": "world"}

    def test_default_in_json_output(self):
        """Default values survive JSON serialization."""
        ast = parse("facet Config(retries: Int = 3)")
        json_str = emit_json(ast, include_locations=False)
        data = json.loads(json_str)
        param = data["facets"][0]["params"][0]
        assert param["default"] == {"type": "Int", "value": 3}


class TestJSONValidity:
    """Test that output is valid JSON."""

    def test_valid_json_output(self):
        """Output should be valid JSON."""
        ast = parse("""
        facet Test(value: String)
        workflow Main(input: String) => (output: String) andThen {
            step = Test(value = $.input)
            yield Main(output = step.value)
        }
        """)
        result = emit_json(ast)

        # Should not raise
        parsed = json.loads(result)
        assert parsed is not None

    def test_roundtrip_consistency(self):
        """Multiple emissions should produce same result."""
        ast = parse("facet Test(value: String)")

        result1 = emit_json(ast, include_locations=False)
        result2 = emit_json(ast, include_locations=False)

        assert result1 == result2


class TestSchemaEmission:
    """Test schema declaration JSON emission."""

    def test_basic_schema(self, emitter):
        """Schema emits correct JSON structure."""
        ast = parse("""
        schema UserRequest {
            name: String
            age: Int
        }
        """)
        data = emitter.emit_dict(ast)
        assert "schemas" in data
        assert len(data["schemas"]) == 1
        schema = data["schemas"][0]
        assert schema["type"] == "SchemaDecl"
        assert schema["name"] == "UserRequest"
        assert len(schema["fields"]) == 2
        assert schema["fields"][0] == {"name": "name", "type": "String"}
        assert schema["fields"][1] == {"name": "age", "type": "Int"}

    def test_array_type_in_schema(self, emitter):
        """Array types emit correctly in schema fields."""
        ast = parse("""
        schema Tagged {
            tags: [String]
        }
        """)
        data = emitter.emit_dict(ast)
        field = data["schemas"][0]["fields"][0]
        assert field["name"] == "tags"
        assert field["type"] == {"type": "ArrayType", "elementType": "String"}

    def test_array_type_in_parameter(self, emitter):
        """Array types emit correctly in regular parameters."""
        ast = parse("facet Process(items: [String])")
        data = emitter.emit_dict(ast)
        param = data["facets"][0]["params"][0]
        assert param["name"] == "items"
        assert param["type"] == {"type": "ArrayType", "elementType": "String"}

    def test_nested_array_type(self, emitter):
        """Nested array types emit correctly."""
        ast = parse("""
        schema Matrix {
            rows: [[Int]]
        }
        """)
        data = emitter.emit_dict(ast)
        field = data["schemas"][0]["fields"][0]
        assert field["type"] == {
            "type": "ArrayType",
            "elementType": {"type": "ArrayType", "elementType": "Int"},
        }

    def test_schema_in_namespace(self, emitter):
        """Schema in namespace emits correctly."""
        ast = parse("""
        namespace app {
            schema Config {
                key: String
            }
        }
        """)
        data = emitter.emit_dict(ast)
        ns = data["namespaces"][0]
        assert "schemas" in ns
        assert len(ns["schemas"]) == 1
        assert ns["schemas"][0]["name"] == "Config"

    def test_schema_reference_as_field_type(self, emitter):
        """Schema name as field type emits as string."""
        ast = parse("""
        schema Address {
            city: String
        }
        schema Person {
            home: Address
        }
        """)
        data = emitter.emit_dict(ast)
        person_field = data["schemas"][1]["fields"][0]
        assert person_field == {"name": "home", "type": "Address"}


class TestUsesDecl:
    """Test uses declaration emission."""

    def test_uses_decl_standalone(self):
        """UsesDecl emits with type and name in namespace context."""
        emitter = JSONEmitter(include_locations=True)
        ast = parse("""
        namespace app {
            use lib.utils
        }
        """)
        data = emitter.emit_dict(ast)
        ns = data["namespaces"][0]
        # Uses declarations are emitted as a list of strings in namespace
        assert "uses" in ns or "uses" not in ns  # uses are emitted as name strings
        # The namespace should contain the use reference
        assert ns["uses"] == ["lib.utils"]


class TestConcatExpr:
    """Test ConcatExpr emission via direct AST construction."""

    def test_concat_expr(self):
        from afl.ast import ConcatExpr, Literal

        emitter = JSONEmitter(include_locations=False)
        node = ConcatExpr(
            operands=[
                Literal(kind="string", value="hello"),
                Literal(kind="string", value=" world"),
            ]
        )
        data = emitter._convert(node)
        assert data["type"] == "ConcatExpr"
        assert len(data["operands"]) == 2
        assert data["operands"][0] == {"type": "String", "value": "hello"}
        assert data["operands"][1] == {"type": "String", "value": " world"}


class TestProvenance:
    """Test source provenance emission."""

    def test_file_provenance(self, tmp_path):
        from afl.parser import AFLParser
        from afl.source import CompilerInput

        afl_file = tmp_path / "test.afl"
        afl_file.write_text("facet Test()")

        from afl.loader import SourceLoader

        entry = SourceLoader.load_file(str(afl_file), is_library=False)
        ci = CompilerInput()
        ci.primary_sources.append(entry)

        parser = AFLParser()
        ast, registry = parser.parse_sources(ci)

        emitter = JSONEmitter(
            include_locations=True,
            include_provenance=True,
            source_registry=registry,
        )
        data = emitter.emit_dict(ast)
        loc = data["facets"][0]["location"]
        assert "provenance" in loc
        assert loc["provenance"]["type"] == "file"

    def test_mongodb_provenance(self):
        from afl.source import MongoDBOrigin

        emitter = JSONEmitter()
        origin = MongoDBOrigin(collection_id="col-1", display_name="MySource")
        result = emitter._provenance_to_dict(origin)
        assert result == {
            "type": "mongodb",
            "collectionId": "col-1",
            "displayName": "MySource",
        }

    def test_maven_provenance_without_classifier(self):
        from afl.source import MavenOrigin

        emitter = JSONEmitter()
        origin = MavenOrigin(group_id="com.example", artifact_id="lib", version="1.0")
        result = emitter._provenance_to_dict(origin)
        assert result == {
            "type": "maven",
            "groupId": "com.example",
            "artifactId": "lib",
            "version": "1.0",
        }
        assert "classifier" not in result

    def test_maven_provenance_with_classifier(self):
        from afl.source import MavenOrigin

        emitter = JSONEmitter()
        origin = MavenOrigin(
            group_id="com.example",
            artifact_id="lib",
            version="1.0",
            classifier="tests",
        )
        result = emitter._provenance_to_dict(origin)
        assert result["classifier"] == "tests"

    def test_unknown_provenance(self):
        emitter = JSONEmitter()
        # Pass an object that isn't any known origin type
        result = emitter._provenance_to_dict("not-a-real-origin")
        assert result == {"type": "unknown"}


class TestCompactJSON:
    """Test compact JSON output (indent=None)."""

    def test_compact_no_newlines(self):
        ast = parse("facet Test(value: String)")
        emitter = JSONEmitter(include_locations=False, indent=None)
        result = emitter.emit(ast)
        assert "\n" not in result
        # Should still be valid JSON
        data = json.loads(result)
        assert data["type"] == "Program"


class TestUnknownNodeType:
    """Test unknown node type raises ValueError."""

    def test_unknown_node_raises(self):
        emitter = JSONEmitter()
        with pytest.raises(ValueError, match="Unknown node type"):
            emitter._convert(object())
