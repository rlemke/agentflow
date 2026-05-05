# WHEN_DEFAULT_NOT_LAST — Default case must be the last case

The default case (`case _ =>`) appears before another case. Defaults
must always come last.

## Wrong

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case _ =>            { yield W(label = "fallback") }
        case $.score > 50 => { yield W(label = "high") }    // ← unreachable
    }
}
```

→ `Default case must be the last case in a when block`

## Correct

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case $.score > 50 => { yield W(label = "high") }
        case _ =>            { yield W(label = "fallback") }
    }
}
```

## Why

`when` cases are tried in order, so anything after the default is
unreachable. Rather than warn about dead branches, the language requires
the default to come last.
