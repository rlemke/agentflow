# TYPE_NOT_OPERAND_REQUIRED — `!` requires a Boolean operand

The unary not operator was applied to a non-Boolean value.

## Wrong

```ffl
case !$.score => { ... }   // ← $.score is Long
```

→ `Type error: operator '!' requires Boolean operand, got Long`

## Correct

```ffl
case !($.score > 0) => { ... }
// or:
case $.score == 0 => { ... }
```

## Why

`!` flips a Boolean. With no truthy/falsy coercion in FFL, applying it
to anything else has no defined meaning. Wrap a comparison or use the
opposite operator.
