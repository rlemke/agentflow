# TYPE_ARITHMETIC_STRING — Use `++` for string concatenation, not `+`

`+` `-` `*` `/` `%` are numeric only. To concatenate strings use `++`.

## Wrong

```ffl
yield W(greeting = "hello " + $.name)
```

→ `Type error: cannot use arithmetic operator '+' with String operand (use '++' for concatenation)`

## Correct

```ffl
yield W(greeting = "hello " ++ $.name)
```

## Why

Keeping `+` numeric-only avoids the JavaScript-style ambiguity where
`"5" + 3` becomes `"53"`. The dedicated `++` operator makes string
concatenation explicit.
