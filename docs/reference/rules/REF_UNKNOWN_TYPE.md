# REF_UNKNOWN_TYPE — Type name is neither a builtin nor a known schema

A type reference (in a parameter or return clause) names something that
isn't a builtin and doesn't resolve to a declared schema.

Builtin types: `String`, `Long`, `Int`, `Double`, `Boolean`, `Json`.

## Wrong

```ffl
namespace x {
    facet Process(in: Buffer) => (out: String)   // ← Buffer is unknown
}
```

→ `Unknown type 'Buffer': not a builtin type or known schema. Schema types must be defined in a namespace and either imported via 'use' or referenced with a fully qualified name.`

## Correct

Either use a builtin (typically `String` or `Json` for opaque blobs) or
declare and import the schema:

```ffl
namespace x {
    schema Buffer { bytes: String, len: Long }
    facet Process(in: Buffer) => (out: String)
}
```

## Why

The validator needs to know each parameter's type to type-check
expressions and step references. Unknown types would silently degrade
type-checking everywhere they flow. Use `Json` if you genuinely have an
opaque payload — that's the explicit "I'm not type-checking this" type.
