# TYPE_ARITHMETIC_BOOLEAN — Arithmetic operators cannot take Boolean operands

`+` `-` `*` `/` `%` were applied to a Boolean value.

## Wrong

```ffl
yield W(count = $.flag + 1)
```

→ `Type error: cannot use arithmetic operator '+' with Boolean operand`

## Correct

Convert via a `when` block (or fix the type):

```ffl
} andThen when {
    case $.flag => { yield W(count = 1) }
    case _      => { yield W(count = 0) }
}
```

## Why

FFL has no implicit Boolean-to-Int coercion. If you need 1/0 from a
Boolean, branch on it explicitly with `when`.
