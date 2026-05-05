# REF_AMBIGUOUS_SCHEMA — Unqualified schema name matches more than one declaration

An unqualified schema name (e.g. `Order`) is declared in multiple
visible namespaces, so the validator can't pick one.

## Wrong

```ffl
namespace shop_a { schema Order { id: String } }
namespace shop_b { schema Order { id: String } }
namespace caller {
    use shop_a
    use shop_b
    facet Process(o: Order) => (out: String)   // ← which Order?
}
```

→ `Ambiguous schema reference 'Order': could be shop_a.Order, shop_b.Order. Use fully qualified name to disambiguate.`

## Correct

```ffl
namespace caller {
    use shop_a
    use shop_b
    facet Process(o: shop_a.Order) => (out: String)
}
```

## Why

Resolution rules for schemas mirror those for facets: current namespace
wins, then a single import wins, but two imports with the same short
name are ambiguous on purpose — to prevent silent dependence on import
order. Always disambiguate with a fully qualified name.
