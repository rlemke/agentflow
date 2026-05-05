# TYPE_NEGATE_BOOLEAN — Cannot negate a Boolean — use `!` instead

Unary minus (`-`) was applied to a Boolean. To flip a Boolean, use `!`.

## Wrong

```ffl
case -$.flag => { ... }
```

→ `Type error: cannot negate Boolean operand`

## Correct

```ffl
case !$.flag => { ... }
```

## Why

`-` is arithmetic; `!` is logical negation. Keeping them separate
prevents the C-style ambiguity where both happen to work on a 1/0
representation. FFL has no truthy/falsy coercion, so each operator is
restricted to its real domain.
