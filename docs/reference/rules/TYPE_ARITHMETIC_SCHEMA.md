# TYPE_ARITHMETIC_SCHEMA — Arithmetic operators cannot take a schema operand

`+` `-` `*` `/` `%` were applied to a schema-typed value. Use a specific
numeric field instead.

## Wrong

```ffl
yield W(total = order + 1)              // ← order is a schema instance
```

→ `Type error: cannot use arithmetic operator '+' with schema type 'Order'`

## Correct

```ffl
yield W(total = order.qty + 1)
```

## Why

Schemas have no defined arithmetic — what would `Order + 1` mean? The
language forces you to pick the numeric field you actually want to
operate on. The same rule fires on string concatenation (`++`) against
schemas.
