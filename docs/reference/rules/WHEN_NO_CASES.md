# WHEN_NO_CASES — `when` block must have at least one case

A `when` block was opened without any cases.

## Wrong

```ffl
namespace x {
    workflow W() => (r: String) andThen when {
    }
}
```

→ `When block must have at least one case`

## Correct

```ffl
namespace x {
    workflow W() => (r: String) andThen when {
        case _ => { yield W(r = "default") }
    }
}
```

## Why

An empty `when` block has no execution path. If you only need an
unconditional branch, drop the `when` and use a plain `andThen` block
instead.
