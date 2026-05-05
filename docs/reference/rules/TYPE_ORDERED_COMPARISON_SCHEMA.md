# TYPE_ORDERED_COMPARISON_SCHEMA — `>` `<` `>=` `<=` cannot take a schema operand

Ordered comparison was applied to a schema-typed value. Compare a
specific field instead.

## Wrong

```ffl
case order > other_order => { ... }   // ← order is a schema instance
```

→ `Type error: cannot use ordered comparison '>' with schema type 'Order'`

## Correct

```ffl
case order.qty > other_order.qty => { ... }
```

## Why

Schemas are records, not numbers. Comparison between two records has no
canonical meaning, so the language requires you to pick the field that
defines the ordering. `==` and `!=` are also not defined on schemas —
compare specific fields.
