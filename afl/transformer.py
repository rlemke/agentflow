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

"""Lark Transformer to convert parse tree to AFL AST."""

from lark import Token, Transformer, v_args

from .ast import (
    AndThenBlock,
    ArrayType,
    Block,
    CallExpr,
    ConcatExpr,
    EventFacetDecl,
    FacetDecl,
    FacetSig,
    ForeachClause,
    ImplicitDecl,
    Literal,
    MixinCall,
    MixinSig,
    NamedArg,
    Namespace,
    Parameter,
    Program,
    Reference,
    ReturnClause,
    SchemaDecl,
    SchemaField,
    SourceLocation,
    StepStmt,
    TypeRef,
    UsesDecl,
    WorkflowDecl,
    YieldStmt,
)


def _get_location(meta, source_id: str | None = None) -> SourceLocation | None:
    """Extract source location from Lark meta."""
    if meta and hasattr(meta, "line"):
        return SourceLocation(
            line=meta.line,
            column=meta.column,
            end_line=getattr(meta, "end_line", None),
            end_column=getattr(meta, "end_column", None),
            source_id=source_id,
        )
    return None


class AFLTransformer(Transformer):
    """Transform Lark parse tree to AFL AST."""

    def __init__(self, source_id: str | None = None):
        super().__init__()
        self._source_id = source_id

    def _loc(self, meta) -> SourceLocation | None:
        """Helper to get location with source_id."""
        return _get_location(meta, self._source_id)

    # Terminals
    def IDENT(self, token: Token) -> str:
        return str(token)

    def QNAME(self, token: Token) -> str:
        return str(token)

    def TYPE_BUILTIN(self, token: Token) -> str:
        return str(token)

    def STRING(self, token: Token) -> str:
        # Remove quotes and process escapes
        s = str(token)[1:-1]
        return s.encode().decode("unicode_escape")

    def INTEGER(self, token: Token) -> int:
        return int(token)

    def BOOLEAN(self, token: Token) -> bool:
        return str(token) == "true"

    def NULL(self, token: Token) -> None:
        return None

    def INPUT_REF(self, token: Token) -> list[str]:
        # $.field.subfield -> ["field", "subfield"]
        return str(token)[2:].split(".")

    # Types
    @v_args(inline=True)
    def type(self, value) -> "TypeRef | ArrayType":
        if isinstance(value, ArrayType):
            return value
        return TypeRef(name=value)

    @v_args(meta=True)
    def array_type(self, meta, items: list) -> ArrayType:
        return ArrayType(element_type=items[0], location=self._loc(meta))

    # Parameters
    def param(self, items: list) -> Parameter:
        name = items[0]
        type_ref = items[1]
        default = items[2] if len(items) > 2 else None
        return Parameter(name=str(name), type=type_ref, default=default)

    def params(self, items: list) -> list[Parameter]:
        return list(items)

    # Literals
    @v_args(meta=True)
    def literal(self, meta, items: list) -> Literal:
        value = items[0]
        if isinstance(value, str):
            kind = "string"
        elif isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, int):
            kind = "integer"
        elif value is None:
            kind = "null"
        else:
            kind = "unknown"
        return Literal(value=value, kind=kind, location=self._loc(meta))

    # References
    @v_args(meta=True)
    def reference(self, meta, items: list) -> Reference:
        item = items[0]
        if isinstance(item, list):
            # INPUT_REF already parsed to list
            return Reference(path=item, is_input=True, location=self._loc(meta))
        else:
            # step_ref
            return item

    @v_args(meta=True)
    def step_ref(self, meta, items: list) -> Reference:
        path = [str(item) for item in items]
        return Reference(path=path, is_input=False, location=self._loc(meta))

    # Expressions
    def expr(self, items: list):
        return items[0]

    @v_args(meta=True)
    def concat_expr(self, meta, items: list):
        # If there's only one operand, return it directly
        if len(items) == 1:
            return items[0]
        # Otherwise create a ConcatExpr with all operands
        return ConcatExpr(operands=list(items), location=self._loc(meta))

    def atom_expr(self, items: list):
        return items[0]

    # Named arguments
    @v_args(meta=True, inline=True)
    def named_arg(self, meta, name: str, value) -> NamedArg:
        return NamedArg(name=name, value=value, location=self._loc(meta))

    def named_args(self, items: list) -> list[NamedArg]:
        return list(items)

    # Mixins
    @v_args(meta=True)
    def mixin_sig(self, meta, items: list) -> MixinSig:
        name = items[0]
        args = items[1] if len(items) > 1 else []
        return MixinSig(name=name, args=args, location=self._loc(meta))

    @v_args(meta=True)
    def mixin_call(self, meta, items: list) -> MixinCall:
        name = items[0]
        args = []
        alias = None
        for item in items[1:]:
            if isinstance(item, list):
                args = item
            elif isinstance(item, str):
                alias = item
        return MixinCall(name=name, args=args, alias=alias, location=self._loc(meta))

    # Call expressions
    @v_args(meta=True)
    def call_expr(self, meta, items: list) -> CallExpr:
        name = items[0]
        args = []
        mixins = []
        for item in items[1:]:
            if isinstance(item, list):
                args = item
            elif isinstance(item, MixinCall):
                mixins.append(item)
        return CallExpr(name=name, args=args, mixins=mixins, location=self._loc(meta))

    # Statements
    @v_args(meta=True, inline=True)
    def step_stmt(self, meta, name: str, call: CallExpr) -> StepStmt:
        return StepStmt(name=name, call=call, location=self._loc(meta))

    @v_args(meta=True, inline=True)
    def yield_stmt(self, meta, call: CallExpr) -> YieldStmt:
        return YieldStmt(call=call, location=self._loc(meta))

    # Blocks
    @v_args(meta=True)
    def block_body(self, meta, items: list) -> tuple[list[StepStmt], list[YieldStmt]]:
        steps = []
        yield_stmts = []
        for item in items:
            if isinstance(item, StepStmt):
                steps.append(item)
            elif isinstance(item, YieldStmt):
                yield_stmts.append(item)
        return (steps, yield_stmts)

    @v_args(meta=True)
    def block(self, meta, items: list) -> Block:
        if items and isinstance(items[0], tuple):
            steps, yield_stmts = items[0]
        else:
            # Flatten items
            steps = []
            yield_stmts = []
            for item in items:
                if isinstance(item, StepStmt):
                    steps.append(item)
                elif isinstance(item, YieldStmt):
                    yield_stmts.append(item)
                elif isinstance(item, tuple):
                    steps.extend(item[0])
                    yield_stmts.extend(item[1])
        return Block(steps=steps, yield_stmts=yield_stmts, location=self._loc(meta))

    @v_args(meta=True)
    def foreach_clause(self, meta, items: list) -> ForeachClause:
        var = items[0]
        ref = items[1]
        return ForeachClause(variable=var, iterable=ref, location=self._loc(meta))

    @v_args(meta=True)
    def facet_def_tail(self, meta, items: list) -> AndThenBlock:
        foreach = None
        block = None
        for item in items:
            if isinstance(item, ForeachClause):
                foreach = item
            elif isinstance(item, Block):
                block = item
        return AndThenBlock(block=block, foreach=foreach, location=self._loc(meta))

    # Return clause
    @v_args(meta=True)
    def return_clause(self, meta, items: list) -> ReturnClause:
        params = items[0] if items else []
        return ReturnClause(params=params, location=self._loc(meta))

    # Facet signature
    @v_args(meta=True)
    def facet_sig(self, meta, items: list) -> FacetSig:
        name = items[0]
        params = []
        returns = None
        mixins = []
        for item in items[1:]:
            if isinstance(item, list) and item and isinstance(item[0], Parameter):
                params = item
            elif isinstance(item, ReturnClause):
                returns = item
            elif isinstance(item, MixinSig):
                mixins.append(item)
        return FacetSig(
            name=name, params=params, returns=returns, mixins=mixins, location=self._loc(meta)
        )

    # Declarations
    @v_args(meta=True)
    def facet_decl(self, meta, items: list) -> FacetDecl:
        sig = items[0]
        body = items[1] if len(items) > 1 else None
        return FacetDecl(sig=sig, body=body, location=self._loc(meta))

    @v_args(meta=True)
    def event_facet_decl(self, meta, items: list) -> EventFacetDecl:
        sig = items[0]
        body = items[1] if len(items) > 1 else None
        return EventFacetDecl(sig=sig, body=body, location=self._loc(meta))

    @v_args(meta=True)
    def workflow_decl(self, meta, items: list) -> WorkflowDecl:
        sig = items[0]
        body = items[1] if len(items) > 1 else None
        return WorkflowDecl(sig=sig, body=body, location=self._loc(meta))

    @v_args(meta=True, inline=True)
    def implicit_decl(self, meta, name: str, call: CallExpr) -> ImplicitDecl:
        return ImplicitDecl(name=name, call=call, location=self._loc(meta))

    @v_args(meta=True, inline=True)
    def uses_decl(self, meta, name: str) -> UsesDecl:
        return UsesDecl(name=name, location=self._loc(meta))

    # Schema declarations
    @v_args(meta=True, inline=True)
    def schema_field(self, meta, name: str, type_node) -> SchemaField:
        return SchemaField(name=name, type=type_node, location=self._loc(meta))

    def schema_fields(self, items: list) -> list[SchemaField]:
        return list(items)

    @v_args(meta=True)
    def schema_decl(self, meta, items: list) -> SchemaDecl:
        name = items[0]
        fields = items[1] if len(items) > 1 else []
        return SchemaDecl(name=name, fields=fields, location=self._loc(meta))

    # Namespace
    @v_args(meta=True)
    def namespace_body(self, meta, items: list) -> dict:
        result = {
            "uses": [],
            "facets": [],
            "event_facets": [],
            "workflows": [],
            "implicits": [],
            "schemas": [],
        }
        for item in items:
            if isinstance(item, UsesDecl):
                result["uses"].append(item)
            elif isinstance(item, FacetDecl):
                result["facets"].append(item)
            elif isinstance(item, EventFacetDecl):
                result["event_facets"].append(item)
            elif isinstance(item, WorkflowDecl):
                result["workflows"].append(item)
            elif isinstance(item, ImplicitDecl):
                result["implicits"].append(item)
            elif isinstance(item, SchemaDecl):
                result["schemas"].append(item)
        return result

    @v_args(meta=True)
    def namespace_block(self, meta, items: list) -> Namespace:
        name = items[0]
        body = items[1] if len(items) > 1 else {}
        return Namespace(
            name=name,
            uses=body.get("uses", []),
            facets=body.get("facets", []),
            event_facets=body.get("event_facets", []),
            workflows=body.get("workflows", []),
            implicits=body.get("implicits", []),
            schemas=body.get("schemas", []),
            location=self._loc(meta),
        )

    # Top-level
    def top_level_decl(self, items: list):
        return items[0]

    # Program (start)
    @v_args(meta=True)
    def start(self, meta, items: list) -> Program:
        namespaces = []
        facets = []
        event_facets = []
        workflows = []
        implicits = []
        schemas = []
        for item in items:
            if isinstance(item, Namespace):
                namespaces.append(item)
            elif isinstance(item, FacetDecl):
                facets.append(item)
            elif isinstance(item, EventFacetDecl):
                event_facets.append(item)
            elif isinstance(item, WorkflowDecl):
                workflows.append(item)
            elif isinstance(item, ImplicitDecl):
                implicits.append(item)
            elif isinstance(item, SchemaDecl):
                schemas.append(item)
        return Program(
            namespaces=namespaces,
            facets=facets,
            event_facets=event_facets,
            workflows=workflows,
            implicits=implicits,
            schemas=schemas,
            location=self._loc(meta),
        )
