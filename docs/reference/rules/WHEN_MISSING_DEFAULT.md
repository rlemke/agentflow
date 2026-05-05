# WHEN_MISSING_DEFAULT — `when` block has no default case

Every `when` block must include a default case (`case _ =>`) so the
runtime always has a path to take.

## Wrong

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case $.score > 50 => { yield W(label = "high") }
    }
}
```

→ `When block must have a default case (case _ =>)`

## Correct

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case $.score > 50 => { yield W(label = "high") }
        case _ =>            { yield W(label = "low") }
    }
}
```

## Why

Without a default, an unmatched input has no path through the workflow —
the runtime would have to error or hang. Forcing an explicit default
makes that decision visible at write-time. Pair this rule with
`WHEN_DEFAULT_NOT_LAST` (which requires the default to be the final case)
and `WHEN_NO_CASES`.
