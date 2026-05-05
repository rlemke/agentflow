# TYPE_NEGATE_SCHEMA — Cannot negate a schema-typed value

Unary minus (`-`) was applied to a schema instance. Negate a specific
numeric field instead.

## Wrong

```ffl
yield W(total = -order)             // ← order is a schema instance
```

→ `Type error: cannot negate schema type 'Order'`

## Correct

```ffl
yield W(total = -order.qty)
```

## Why

Negation of a record has no defined meaning. The validator forces you
to pick the numeric field you really want to negate, the same way
arithmetic and ordered-comparison rules do.
