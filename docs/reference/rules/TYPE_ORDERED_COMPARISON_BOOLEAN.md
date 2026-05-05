# TYPE_ORDERED_COMPARISON_BOOLEAN — `>` `<` `>=` `<=` cannot take Boolean operands

Ordered comparison was applied to a Boolean value. Use `==` / `!=` for
Booleans instead.

## Wrong

```ffl
case $.flag > true => { ... }
```

→ `Type error: cannot use ordered comparison '>' with Boolean operand`

## Correct

```ffl
case $.flag == true => { ... }
// or simply:
case $.flag => { ... }   // when $.flag is already Boolean
```

## Why

Booleans don't have a meaningful ordering. `==` and `!=` are defined on
all types; `<` `>` `<=` `>=` are restricted to numerics and strings to
prevent meaningless comparisons.
