# REF_INVALID_STEP_FORMAT — Step reference must include an attribute

A bare step name was used where a `step.attr` reference was expected.

## Wrong

```ffl
namespace x {
    facet A() => (out: String)
    facet B(in: String) => (r: String)
    workflow W() => (r: String) andThen {
        a = A()
        b = B(in = a)              // ← bare 'a' is not a valid expression
        yield W(r = b.r)
    }
}
```

→ `Invalid step reference: must be 'step.attribute'`

## Correct

```ffl
namespace x {
    facet A() => (out: String)
    facet B(in: String) => (r: String)
    workflow W() => (r: String) andThen {
        a = A()
        b = B(in = a.out)
        yield W(r = b.r)
    }
}
```

## Why

The grammar rule is `step_ref: IDENT ("." IDENT)+` — at least one `.field`
segment is required. Even when a step's return is a single-field schema,
you must access it via `step.field`. There is no way to pass a whole step
result as one opaque value.
