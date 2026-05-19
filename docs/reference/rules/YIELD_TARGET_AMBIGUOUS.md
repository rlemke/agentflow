# YIELD_TARGET_AMBIGUOUS — Bare mixin name can't pick one of N aliases

A `yield` uses a mixin facet's name as the target, but the containing
facet declares **two or more** mixins with that same target. The bare
name doesn't say which alias the yield belongs to, so the author must
use the alias name instead.

## Wrong

```ffl
namespace x {
    facet RetryPolicy(max: Int) => (out: String)
    facet F(input: String) => (output: String)
        with RetryPolicy() as primary
        with RetryPolicy() as fallback
        andThen {
            yield F(output = "ok")
            yield RetryPolicy(out = "retry-3")  // ← `primary` or `fallback`?
        }
}
```

→ `Ambiguous yield target 'RetryPolicy': the containing facet has 2 mixins with this target. Use one of the aliases instead: ['fallback', 'primary']`

## Correct

Address the alias you mean:

```ffl
namespace x {
    facet RetryPolicy(max: Int) => (out: String)
    facet F(input: String) => (output: String)
        with RetryPolicy() as primary
        with RetryPolicy() as fallback
        andThen {
            yield F(output = "ok")
            yield primary(out = "retry-3")     // populates $.f.primary.out
            yield fallback(out = "fallback-1") // populates $.f.fallback.out
        }
}
```

The bare-target form (`yield RetryPolicy(...)`) remains valid when only
one mixin targets that facet — the alias is unambiguous in that case.

## Why

Each aliased mixin is a separate sub-step that lives under the parent
in the dashboard tree and that FacetRef consumers reach as
`$.<fref>.<alias>.<field>`. The runtime routes yields to a specific
sub-step. With two aliases pointing at the same target, the bare facet
name doesn't identify a single sub-step — the author must name the
alias they intend.

This rule is paired with the routing implemented in
`facetwork/runtime/handlers/capture.py::StatementCaptureBeginHandler`,
which matches yields to destinations by alias first, then by unique
target-facet fallback.
