# YIELD_INVALID_TARGET — Yield names something other than the containing facet or its mixins

A `yield X(...)` statement must target the containing facet/workflow OR
one of its declared mixins. It cannot target arbitrary other facets.

## Wrong

```ffl
namespace x {
    facet OtherThing() => (val: String)
    workflow W() => (r: String) andThen {
        yield OtherThing(val = "hi")    // ← W is the containing workflow
    }
}
```

→ `Invalid yield target 'OtherThing': must be the containing facet or one of its mixins. Valid targets are: ['W']`

## Correct

```ffl
namespace x {
    workflow W() => (r: String) andThen {
        yield W(r = "hi")
    }
}
```

If you want to yield to multiple targets, declare them as mixins on the
workflow signature:

```ffl
namespace x {
    facet Audit() => (at: String)
    workflow W(at: String) => (r: String, at: String) with Audit() andThen {
        yield W(r = "hi")
        yield Audit(at = $.at)
    }
}
```

## Why

`yield` reports a result back to the *caller* of the containing
facet/workflow, not arbitrary other code. Mixins are explicitly part of
the caller's contract, which is why they're allowed as targets. To
combine results from sibling steps, use step references in the yield
arguments rather than additional yields.
