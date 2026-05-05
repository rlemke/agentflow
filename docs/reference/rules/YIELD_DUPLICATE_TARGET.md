# YIELD_DUPLICATE_TARGET — Two yields target the same facet

Two `yield` statements in the same block reference the same target.

## Wrong

```ffl
namespace x {
    workflow W() => (r: String) andThen {
        yield W(r = "first")
        yield W(r = "second")     // ← W already yielded above
    }
}
```

→ `Duplicate yield target 'W': each yield must reference a different facet or mixin`

## Correct

Combine into a single `yield`, or — if you need two return slots —
declare a mixin and yield to it separately:

```ffl
namespace x {
    workflow W() => (r: String) andThen {
        yield W(r = "first")
    }
}
```

## Why

A yield writes to the caller's return slot for that target. Two yields
to the same target would silently race or overwrite, so the language
forbids it.
