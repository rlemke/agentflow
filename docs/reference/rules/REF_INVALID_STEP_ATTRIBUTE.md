# REF_INVALID_STEP_ATTRIBUTE — Attribute is not a return field of that step's facet

A `step.attr` reference uses an attribute the step's facet does not return.

## Wrong

```ffl
namespace x {
    facet A() => (out: String)
    workflow W() => (r: String) andThen {
        a = A()
        yield W(r = a.result)      // ← A returns 'out', not 'result'
    }
}
```

→ `Invalid attribute 'result' for step 'a': valid attributes are ['out']`

## Correct

```ffl
namespace x {
    facet A() => (out: String)
    workflow W() => (r: String) andThen {
        a = A()
        yield W(r = a.out)
    }
}
```

## Why

Validation knows each facet's declared returns and rejects accesses to
fields that are not in that set. The error message lists the valid
attributes; pick from that list. If the facet really should expose a new
attribute, add it to the facet's `=> (...)` return clause.
