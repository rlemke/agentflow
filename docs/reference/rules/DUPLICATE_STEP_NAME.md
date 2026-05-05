# DUPLICATE_STEP_NAME — Two steps in the same block share a name

Step names within a single `andThen` block (and across nested step
bodies) must be unique.

## Wrong

```ffl
namespace x {
    facet A(n: Long) => (out: Long)
    workflow W() => (r: Long) andThen {
        a = A(n = 1)
        a = A(n = 2)              // ← same name
        yield W(r = a.out)
    }
}
```

→ `Duplicate step name 'a' (previously defined at line 4)`

## Correct

```ffl
namespace x {
    facet A(n: Long) => (out: Long)
    workflow W() => (r: Long) andThen {
        a1 = A(n = 1)
        a2 = A(n = 2)
        yield W(r = a2.out)
    }
}
```

## Why

Step names are how downstream code references step results, so they have
to resolve unambiguously. The error includes the line of the first
declaration so you can pick which to rename.
