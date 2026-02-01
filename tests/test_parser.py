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

"""Tests for AFL parser."""

import pytest

from afl import (
    AFLParser,
    ArrayType,
    Literal,
    ParseError,
    Program,
    Reference,
    SchemaDecl,
    TypeRef,
    parse,
)


@pytest.fixture
def parser():
    """Create a parser instance."""
    return AFLParser()


class TestBasicParsing:
    """Test basic parsing functionality."""

    def test_empty_program(self, parser):
        """Empty input should produce empty program."""
        ast = parser.parse("")
        assert isinstance(ast, Program)
        assert ast.namespaces == []
        assert ast.facets == []
        assert ast.workflows == []

    def test_simple_facet(self, parser):
        """Parse a simple facet declaration."""
        ast = parser.parse("facet SomeData(num: Long)")
        assert len(ast.facets) == 1
        facet = ast.facets[0]
        assert facet.sig.name == "SomeData"
        assert len(facet.sig.params) == 1
        assert facet.sig.params[0].name == "num"
        assert facet.sig.params[0].type.name == "Long"

    def test_facet_multiple_params(self, parser):
        """Parse facet with multiple parameters."""
        ast = parser.parse("facet User(name: String, email: String, age: Int)")
        facet = ast.facets[0]
        assert len(facet.sig.params) == 3
        assert facet.sig.params[0].name == "name"
        assert facet.sig.params[1].name == "email"
        assert facet.sig.params[2].name == "age"

    def test_facet_no_params(self, parser):
        """Parse facet with no parameters."""
        ast = parser.parse("facet Empty()")
        facet = ast.facets[0]
        assert facet.sig.name == "Empty"
        assert facet.sig.params == []

    def test_facet_with_return(self, parser):
        """Parse facet with return clause."""
        ast = parser.parse("facet Transform(input: String) => (output: String)")
        facet = ast.facets[0]
        assert facet.sig.returns is not None
        assert len(facet.sig.returns.params) == 1
        assert facet.sig.returns.params[0].name == "output"


class TestEventFacets:
    """Test event facet parsing."""

    def test_event_facet(self, parser):
        """Parse event facet declaration."""
        ast = parser.parse("event facet Sub(input1: Long, input2: Long) => (output: Long)")
        assert len(ast.event_facets) == 1
        ef = ast.event_facets[0]
        assert ef.sig.name == "Sub"
        assert len(ef.sig.params) == 2
        assert ef.sig.returns is not None


class TestWorkflows:
    """Test workflow parsing."""

    def test_simple_workflow(self, parser):
        """Parse workflow declaration."""
        ast = parser.parse("workflow MyFlow(input: String) => (output: String)")
        assert len(ast.workflows) == 1
        wf = ast.workflows[0]
        assert wf.sig.name == "MyFlow"

    def test_workflow_with_body(self, parser):
        """Parse workflow with andThen block."""
        source = """
        workflow GetStreets(input: String) => (output: String) andThen {
            step = ConvertToGeoJson(input = $.input)
            yield GetStreets(output = step.output)
        }
        """
        ast = parser.parse(source)
        wf = ast.workflows[0]
        assert wf.body is not None
        assert wf.body.block is not None
        assert len(wf.body.block.steps) == 1
        assert wf.body.block.yield_stmt is not None


class TestNamespaces:
    """Test namespace parsing."""

    def test_simple_namespace(self, parser):
        """Parse namespace block."""
        source = """
        namespace team.a.osm {
            facet Data(value: String)
        }
        """
        ast = parser.parse(source)
        assert len(ast.namespaces) == 1
        ns = ast.namespaces[0]
        assert ns.name == "team.a.osm"
        assert len(ns.facets) == 1

    def test_namespace_with_uses(self, parser):
        """Parse namespace with uses declarations."""
        source = """
        namespace team.a.osm.conversions {
            uses team.b.osm.streets
            uses team.c.utils
            facet ConvertToGeoJson(input: String) => (output: String)
        }
        """
        ast = parser.parse(source)
        ns = ast.namespaces[0]
        assert len(ns.uses) == 2
        assert ns.uses[0].name == "team.b.osm.streets"
        assert ns.uses[1].name == "team.c.utils"

    def test_namespace_with_workflow(self, parser):
        """Parse namespace containing workflow."""
        source = """
        namespace team.a.osm.conversions {
            uses team.b.osm.streets

            facet ConvertToGeoJson(input: String) => (output: String)

            workflow GetStreets(input: String) => (output: String) andThen {
                step = ConvertToGeoJson(input = $.input)
                streets = FilterStreets(input = step.output)
                yield GetStreets(output = streets.output)
            }
        }
        """
        ast = parser.parse(source)
        ns = ast.namespaces[0]
        assert len(ns.workflows) == 1
        assert len(ns.facets) == 1


class TestMixins:
    """Test mixin parsing."""

    def test_mixin_in_signature(self, parser):
        """Parse facet with mixin in signature."""
        source = "facet Job(input: String) with Retry(maxAttempts = 3)"
        ast = parser.parse(source)
        facet = ast.facets[0]
        assert len(facet.sig.mixins) == 1
        assert facet.sig.mixins[0].name == "Retry"

    def test_mixin_call_with_alias(self, parser):
        """Parse mixin call with alias."""
        source = """
        workflow Test(input: String) andThen {
            job = RunASparkJob(input = $.input) with User(name = "test") as user
        }
        """
        ast = parser.parse(source)
        wf = ast.workflows[0]
        step = wf.body.block.steps[0]
        assert len(step.call.mixins) == 1
        assert step.call.mixins[0].alias == "user"


class TestImplicits:
    """Test implicit declaration parsing."""

    def test_implicit_decl(self, parser):
        """Parse implicit declaration."""
        source = 'implicit user = User(name = "John", email = "john@example.com")'
        ast = parser.parse(source)
        assert len(ast.implicits) == 1
        impl = ast.implicits[0]
        assert impl.name == "user"
        assert impl.call.name == "User"


class TestReferences:
    """Test reference parsing."""

    def test_input_reference(self, parser):
        """Parse input reference ($.field)."""
        source = """
        workflow Test(input: String) andThen {
            step = Process(value = $.input)
        }
        """
        ast = parser.parse(source)
        step = ast.workflows[0].body.block.steps[0]
        arg = step.call.args[0]
        assert isinstance(arg.value, Reference)
        assert arg.value.is_input is True
        assert arg.value.path == ["input"]

    def test_step_reference(self, parser):
        """Parse step reference (step.field)."""
        source = """
        workflow Test(input: String) andThen {
            step1 = Process(value = $.input)
            step2 = Transform(value = step1.output)
        }
        """
        ast = parser.parse(source)
        step2 = ast.workflows[0].body.block.steps[1]
        arg = step2.call.args[0]
        assert isinstance(arg.value, Reference)
        assert arg.value.is_input is False
        assert arg.value.path == ["step1", "output"]

    def test_nested_reference(self, parser):
        """Parse nested reference (step.field.subfield)."""
        source = """
        workflow Test(data: Json) andThen {
            step = Process(value = $.data.nested.field)
        }
        """
        ast = parser.parse(source)
        step = ast.workflows[0].body.block.steps[0]
        arg = step.call.args[0]
        assert arg.value.path == ["data", "nested", "field"]


class TestLiterals:
    """Test literal parsing."""

    def test_string_literal(self, parser):
        """Parse string literal."""
        source = 'implicit msg = Message(text = "hello world")'
        ast = parser.parse(source)
        arg = ast.implicits[0].call.args[0]
        assert isinstance(arg.value, Literal)
        assert arg.value.kind == "string"
        assert arg.value.value == "hello world"

    def test_integer_literal(self, parser):
        """Parse integer literal."""
        source = "implicit count = Counter(value = 42)"
        ast = parser.parse(source)
        arg = ast.implicits[0].call.args[0]
        assert isinstance(arg.value, Literal)
        assert arg.value.kind == "integer"
        assert arg.value.value == 42

    def test_boolean_literal(self, parser):
        """Parse boolean literals."""
        source = "implicit flag = Config(enabled = true, disabled = false)"
        ast = parser.parse(source)
        args = ast.implicits[0].call.args
        assert args[0].value.value is True
        assert args[1].value.value is False

    def test_null_literal(self, parser):
        """Parse null literal."""
        source = "implicit opt = Optional(value = null)"
        ast = parser.parse(source)
        arg = ast.implicits[0].call.args[0]
        assert arg.value.kind == "null"
        assert arg.value.value is None


class TestForeach:
    """Test foreach parsing."""

    def test_foreach_in_workflow(self, parser):
        """Parse workflow with foreach."""
        source = """
        workflow ProcessAllRegions(regions: Json) => (results: Json) andThen foreach r in $.regions {
            processed = ProcessRegion(region = r.name)
            yield ProcessAllRegions(results = processed.result)
        }
        """
        ast = parser.parse(source)
        wf = ast.workflows[0]
        assert wf.body.foreach is not None
        assert wf.body.foreach.variable == "r"
        assert wf.body.foreach.iterable.path == ["regions"]


class TestComments:
    """Test comment handling."""

    def test_line_comment(self, parser):
        """Line comments should be ignored."""
        source = """
        // This is a comment
        facet Data(value: String)  // inline comment
        """
        ast = parser.parse(source)
        assert len(ast.facets) == 1

    def test_block_comment(self, parser):
        """Block comments should be ignored."""
        source = """
        /* Multi-line
           comment */
        facet Data(value: String)
        """
        ast = parser.parse(source)
        assert len(ast.facets) == 1


class TestTypes:
    """Test type parsing."""

    def test_builtin_types(self, parser):
        """Parse all builtin types."""
        source = """
        facet AllTypes(
            s: String,
            l: Long,
            i: Int,
            b: Boolean,
            j: Json
        )
        """
        ast = parser.parse(source)
        params = ast.facets[0].sig.params
        assert params[0].type.name == "String"
        assert params[1].type.name == "Long"
        assert params[2].type.name == "Int"
        assert params[3].type.name == "Boolean"
        assert params[4].type.name == "Json"

    def test_qualified_type(self, parser):
        """Parse qualified type name."""
        source = "facet UseCustom(data: team.types.CustomData)"
        ast = parser.parse(source)
        param = ast.facets[0].sig.params[0]
        assert param.type.name == "team.types.CustomData"


class TestErrorReporting:
    """Test error reporting with line/column numbers."""

    def test_unexpected_token(self, parser):
        """Parse error should include line and column."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("facet ()")
        assert exc_info.value.line is not None
        assert exc_info.value.column is not None

    def test_missing_parenthesis(self, parser):
        """Missing parenthesis should report error location."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("facet Test(name: String")
        assert exc_info.value.line is not None

    def test_invalid_return_clause(self, parser):
        """Invalid return clause syntax."""
        with pytest.raises(ParseError):
            # Return clause must be => ( ... ), not => ...
            parser.parse("event facet Sub(input: Long) => output: Long")


class TestConvenienceFunction:
    """Test the parse() convenience function."""

    def test_parse_function(self):
        """Test module-level parse function."""
        ast = parse("facet Simple()")
        assert isinstance(ast, Program)
        assert len(ast.facets) == 1


class TestSourceLocations:
    """Test source location tracking."""

    def test_facet_has_location(self, parser):
        """Parsed nodes should have source locations."""
        ast = parser.parse("facet Test(value: String)")
        facet = ast.facets[0]
        assert facet.location is not None
        assert facet.location.line == 1


class TestMultipleDeclarations:
    """Test parsing multiple declarations."""

    def test_multiple_facets(self, parser):
        """Parse multiple facet declarations."""
        source = """
        facet A(x: Int)
        facet B(y: String)
        facet C(z: Boolean)
        """
        ast = parser.parse(source)
        assert len(ast.facets) == 3

    def test_mixed_declarations(self, parser):
        """Parse mixed declaration types."""
        source = """
        facet Data(value: String)
        event facet Process(input: String) => (output: String)
        workflow Main(start: String) => (end: String)
        implicit config = Config(debug = true)
        """
        ast = parser.parse(source)
        assert len(ast.facets) == 1
        assert len(ast.event_facets) == 1
        assert len(ast.workflows) == 1
        assert len(ast.implicits) == 1


class TestSemicolonSeparators:
    """Test semicolon as statement separator."""

    def test_semicolon_separator(self, parser):
        """Semicolons can separate statements."""
        source = "facet A(); facet B(); facet C()"
        ast = parser.parse(source)
        assert len(ast.facets) == 3

    def test_mixed_separators(self, parser):
        """Mix of newlines and semicolons."""
        source = """facet A(); facet B()
        facet C()"""
        ast = parser.parse(source)
        assert len(ast.facets) == 3


class TestConcatExpression:
    """Test concatenation expression (++) parsing."""

    def test_simple_concat(self, parser):
        """Parse simple concat expression."""
        source = """
        facet Data() => (value: Json)
        workflow Test() => (result: Json) andThen {
            a = Data()
            b = Data()
            yield Test(result = a.value ++ b.value)
        }
        """
        ast = parser.parse(source)
        yield_stmt = ast.workflows[0].body.block.yield_stmts[0]
        arg = yield_stmt.call.args[0]
        from afl.ast import ConcatExpr

        assert isinstance(arg.value, ConcatExpr)
        assert len(arg.value.operands) == 2

    def test_multi_concat(self, parser):
        """Parse multiple concat operands."""
        source = """
        facet Data() => (value: Json)
        workflow Test() => (result: Json) andThen {
            a = Data()
            b = Data()
            c = Data()
            yield Test(result = a.value ++ b.value ++ c.value)
        }
        """
        ast = parser.parse(source)
        yield_stmt = ast.workflows[0].body.block.yield_stmts[0]
        arg = yield_stmt.call.args[0]
        from afl.ast import ConcatExpr

        assert isinstance(arg.value, ConcatExpr)
        assert len(arg.value.operands) == 3

    def test_concat_with_newlines(self, parser):
        """Parse concat expression with newlines after ++."""
        source = """
        facet Data() => (value: Json)
        workflow Test() => (result: Json) andThen {
            a = Data()
            b = Data()
            c = Data()
            yield Test(result =
                a.value ++
                b.value ++
                c.value)
        }
        """
        ast = parser.parse(source)
        yield_stmt = ast.workflows[0].body.block.yield_stmts[0]
        arg = yield_stmt.call.args[0]
        from afl.ast import ConcatExpr

        assert isinstance(arg.value, ConcatExpr)
        assert len(arg.value.operands) == 3


class TestUseDeclaration:
    """Test 'use' as alternative to 'uses'."""

    def test_use_singular(self, parser):
        """Parse 'use' declaration (singular form)."""
        source = """
        namespace test {
            use other.module
            facet Test()
        }
        """
        ast = parser.parse(source)
        ns = ast.namespaces[0]
        assert len(ns.uses) == 1
        assert ns.uses[0].name == "other.module"

    def test_multiple_use_declarations(self, parser):
        """Parse multiple 'use' declarations."""
        source = """
        namespace test {
            use module.a
            use module.b
            uses module.c
            facet Test()
        }
        """
        ast = parser.parse(source)
        ns = ast.namespaces[0]
        assert len(ns.uses) == 3


class TestDefaultParameterValues:
    """Test parsing default parameter values."""

    def test_string_default(self, parser):
        """Parse parameter with string default."""
        ast = parser.parse('facet Greeting(message: String = "hello")')
        param = ast.facets[0].sig.params[0]
        assert param.name == "message"
        assert param.type.name == "String"
        assert isinstance(param.default, Literal)
        assert param.default.kind == "string"
        assert param.default.value == "hello"

    def test_integer_default(self, parser):
        """Parse parameter with integer default."""
        ast = parser.parse("facet Config(retries: Int = 3)")
        param = ast.facets[0].sig.params[0]
        assert isinstance(param.default, Literal)
        assert param.default.kind == "integer"
        assert param.default.value == 3

    def test_boolean_default(self, parser):
        """Parse parameter with boolean default."""
        ast = parser.parse("facet Config(verbose: Boolean = true)")
        param = ast.facets[0].sig.params[0]
        assert isinstance(param.default, Literal)
        assert param.default.value is True

    def test_null_default(self, parser):
        """Parse parameter with null default."""
        ast = parser.parse("facet Config(extra: Json = null)")
        param = ast.facets[0].sig.params[0]
        assert isinstance(param.default, Literal)
        assert param.default.kind == "null"
        assert param.default.value is None

    def test_no_default(self, parser):
        """Parameters without defaults have default=None."""
        ast = parser.parse("facet Data(value: String)")
        param = ast.facets[0].sig.params[0]
        assert param.default is None

    def test_mixed_defaults(self, parser):
        """Parse params where some have defaults and some don't."""
        ast = parser.parse("facet Mixed(required: String, optional: Int = 42)")
        params = ast.facets[0].sig.params
        assert params[0].default is None
        assert params[1].default is not None
        assert params[1].default.value == 42

    def test_workflow_with_defaults(self, parser):
        """Parse workflow with default parameter values."""
        ast = parser.parse('workflow MyFlow(input: String = "hello") => (output: String = "world")')
        wf = ast.workflows[0]
        assert wf.sig.params[0].default.value == "hello"
        assert wf.sig.returns.params[0].default.value == "world"

    def test_event_facet_with_defaults(self, parser):
        """Parse event facet with default parameter values."""
        ast = parser.parse("event facet Process(count: Long = 10) => (result: Long)")
        ef = ast.event_facets[0]
        assert ef.sig.params[0].default.value == 10

    def test_multiple_defaults(self, parser):
        """Parse multiple parameters with defaults."""
        ast = parser.parse(
            'facet Config(host: String = "localhost", port: Int = 8080, debug: Boolean = false)'
        )
        params = ast.facets[0].sig.params
        assert params[0].default.value == "localhost"
        assert params[1].default.value == 8080
        assert params[2].default.value is False

    def test_reference_default(self, parser):
        """Parse parameter with reference default."""
        ast = parser.parse(
            "workflow Test(x: Long = 1) => (output: Long) andThen {\n"
            "    step = Process(value = $.x)\n"
            "}"
        )
        param = ast.workflows[0].sig.params[0]
        assert isinstance(param.default, Literal)
        assert param.default.value == 1


class TestSchemaDeclarations:
    """Test schema declaration parsing."""

    def test_basic_schema(self, parser):
        """Parse a basic schema with scalar fields."""
        ast = parser.parse("""
        schema UserRequest {
            name: String
            age: Int
        }
        """)
        assert len(ast.schemas) == 1
        schema = ast.schemas[0]
        assert isinstance(schema, SchemaDecl)
        assert schema.name == "UserRequest"
        assert len(schema.fields) == 2
        assert schema.fields[0].name == "name"
        assert isinstance(schema.fields[0].type, TypeRef)
        assert schema.fields[0].type.name == "String"
        assert schema.fields[1].name == "age"
        assert schema.fields[1].type.name == "Int"

    def test_schema_with_array_type(self, parser):
        """Parse a schema with array type fields."""
        ast = parser.parse("""
        schema TaggedItem {
            tags: [String]
            ids: [Long]
        }
        """)
        schema = ast.schemas[0]
        assert len(schema.fields) == 2
        tags_field = schema.fields[0]
        assert tags_field.name == "tags"
        assert isinstance(tags_field.type, ArrayType)
        assert isinstance(tags_field.type.element_type, TypeRef)
        assert tags_field.type.element_type.name == "String"

    def test_schema_referencing_schema(self, parser):
        """Parse a schema that references another schema as a field type."""
        ast = parser.parse("""
        schema Address {
            street: String
            city: String
        }
        schema Person {
            name: String
            home: Address
        }
        """)
        assert len(ast.schemas) == 2
        person = ast.schemas[1]
        assert person.fields[1].name == "home"
        assert isinstance(person.fields[1].type, TypeRef)
        assert person.fields[1].type.name == "Address"

    def test_schema_in_namespace(self, parser):
        """Parse a schema inside a namespace."""
        ast = parser.parse("""
        namespace app {
            schema Config {
                key: String
                value: String
            }
        }
        """)
        assert len(ast.namespaces) == 1
        ns = ast.namespaces[0]
        assert len(ns.schemas) == 1
        assert ns.schemas[0].name == "Config"
        assert len(ns.schemas[0].fields) == 2

    def test_schema_as_parameter_type(self, parser):
        """Schema name used as a parameter type in facet signature."""
        ast = parser.parse("""
        schema UserRequest {
            name: String
        }
        event facet CreateUser(request: UserRequest) => (id: String)
        """)
        assert len(ast.schemas) == 1
        assert len(ast.event_facets) == 1
        param = ast.event_facets[0].sig.params[0]
        assert param.name == "request"
        assert isinstance(param.type, TypeRef)
        assert param.type.name == "UserRequest"

    def test_array_type_in_parameter(self, parser):
        """Array type used in regular facet parameter."""
        ast = parser.parse("facet Process(items: [String])")
        param = ast.facets[0].sig.params[0]
        assert param.name == "items"
        assert isinstance(param.type, ArrayType)
        assert isinstance(param.type.element_type, TypeRef)
        assert param.type.element_type.name == "String"

    def test_nested_array_type(self, parser):
        """Nested array type [[String]]."""
        ast = parser.parse("""
        schema Matrix {
            rows: [[Int]]
        }
        """)
        field = ast.schemas[0].fields[0]
        assert isinstance(field.type, ArrayType)
        assert isinstance(field.type.element_type, ArrayType)
        assert isinstance(field.type.element_type.element_type, TypeRef)
        assert field.type.element_type.element_type.name == "Int"

    def test_empty_schema(self, parser):
        """Parse an empty schema."""
        ast = parser.parse("schema Empty {}")
        assert len(ast.schemas) == 1
        assert ast.schemas[0].name == "Empty"
        assert ast.schemas[0].fields == []

    def test_schema_with_qualified_type(self, parser):
        """Schema field with qualified type name."""
        ast = parser.parse("""
        schema Response {
            data: app.DataModel
        }
        """)
        field = ast.schemas[0].fields[0]
        assert isinstance(field.type, TypeRef)
        assert field.type.name == "app.DataModel"
