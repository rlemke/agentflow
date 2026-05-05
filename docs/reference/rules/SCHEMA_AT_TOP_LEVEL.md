# SCHEMA_AT_TOP_LEVEL — Schemas must be defined inside a namespace

A `schema` declaration appears at the top level. All schemas must live
inside a namespace.

## Wrong

```ffl
schema Order {
    sku: String,
    qty: Long
}
```

→ `Schema 'Order' must be defined inside a namespace. Top-level schemas are not allowed.`

## Correct

```ffl
namespace shop {
    schema Order {
        sku: String,
        qty: Long
    }
}
```

## Why

Schema names are resolved through the namespace import graph (`use`).
Top-level schemas would have no namespace, breaking the resolution model
and creating a single global flat name space. The same constraint applies
to facets and workflows (`WORKFLOW_AT_TOP_LEVEL`).
