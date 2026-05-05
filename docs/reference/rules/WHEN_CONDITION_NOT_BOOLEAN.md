# WHEN_CONDITION_NOT_BOOLEAN — `when` case condition is not a Boolean expression

A non-default `when` case has a condition whose inferred type is not
`Boolean`.

## Wrong

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case $.score => { yield W(label = "any") }   // ← Long, not Boolean
        case _ =>      { yield W(label = "fallback") }
    }
}
```

→ `When case condition must be Boolean, got Long`

## Correct

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case $.score > 0 => { yield W(label = "positive") }
        case _ =>           { yield W(label = "non-positive") }
    }
}
```

## Why

FFL has no implicit truthy/falsy coercion. Comparison and boolean
operators (`>`, `==`, `&&`, `||`, `!`) produce `Boolean`; bare numbers
or strings do not. This rule catches the common mistake of forgetting
the comparison.
