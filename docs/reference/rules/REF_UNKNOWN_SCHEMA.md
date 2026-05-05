# REF_UNKNOWN_SCHEMA — Qualified schema name doesn't resolve

A fully-qualified schema reference (e.g. `shop.Order`) doesn't match any
declared schema.

## Wrong

```ffl
namespace x {
    facet Process(o: shop.Order) => (out: String)   // ← no schema 'shop.Order'
}
```

→ `Unknown schema 'shop.Order': no schema found with this qualified name.`

## Correct

Either declare the schema in that namespace, or fix the reference:

```ffl
namespace shop {
    schema Order { sku: String, qty: Long }
}
namespace x {
    use shop
    facet Process(o: shop.Order) => (out: String)
}
```

## Why

Qualified names look up directly into the schema table. If the lookup
fails, it's not a typo the resolver can recover from — the namespace
must declare the schema. This is the schema counterpart of
`REF_UNKNOWN_FACET`.
