# TYPE_NEGATE_STRING — Cannot negate a String

Unary minus (`-`) was applied to a String value.

## Wrong

```ffl
yield W(label = -$.name)
```

→ `Type error: cannot negate String operand`

## Correct

If you meant to negate a numeric value, fix the type. If you wanted to
clear or invert a string in some other sense, that's not what `-` does
in FFL — there is no string-negation operator.

```ffl
yield W(label = $.name)
```

## Why

`-` is arithmetic-only. Strings have no negation; the validator catches
the mismatch rather than letting it surface as a runtime error.
