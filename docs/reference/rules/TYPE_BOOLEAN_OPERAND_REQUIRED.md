# TYPE_BOOLEAN_OPERAND_REQUIRED — `&&` / `||` need Boolean operands

A logical operator was applied to a non-Boolean value.

## Wrong

```ffl
case $.score && $.flag => { ... }   // ← if $.score is Long, this errors
```

→ `Type error: operator '&&' requires Boolean operands, got Long`

## Correct

```ffl
case $.score > 0 && $.flag => { ... }
```

## Why

FFL has no truthy/falsy coercion. Always combine with explicit
comparisons (`> 0`, `== "yes"`, `!= null`).
