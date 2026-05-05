# WHEN_MULTIPLE_DEFAULTS — `when` block has more than one default case

Only one default case (`case _ =>`) is allowed per `when` block.

## Wrong

```ffl
namespace x {
    workflow W(score: Long) => (label: String) andThen when {
        case $.score > 50 => { yield W(label = "high") }
        case _ =>            { yield W(label = "first default") }
        case _ =>            { yield W(label = "second default") }
    }
}
```

→ `When block can have at most one default case`

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

Two defaults make execution order significant in a way that's easy to
get wrong. Collapse the duplicates into one default — or, if the two
default branches really do different work, gate them with explicit
conditions.
