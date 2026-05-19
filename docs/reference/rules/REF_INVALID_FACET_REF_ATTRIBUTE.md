# REF_INVALID_FACET_REF_ATTRIBUTE — `$.facetRef.<name>` must reference a param, return, or mixin alias on the referenced facet

When a parameter is typed as a facet (a FacetRef parameter), the
consumer can read attributes of the upstream step through
`$.facetRef.<name>` and one level of mixin alias as
`$.facetRef.<alias>.<field>`. Every `<name>` must resolve against the
namespace exposed by the referenced facet: its own params, its own
returns, and the aliases of any mixins declared with `as`.

## Wrong — unknown attribute on the referenced facet

```ffl
namespace x {
    facet Value(input: String) => (output: String)
    facet Consumer(ds: Value) => (out: String) andThen {
        yield Consumer(out = $.ds.bogus)        // ← `bogus` is not on Value
    }
}
```

→ `Invalid FacetRef attribute '$.ds.bogus': facet 'Value' has no param, return, or mixin alias named 'bogus'`

## Wrong — unknown attribute on a mixin alias

```ffl
namespace x {
    facet M1(in: String) => (out: String)
    facet F2(input: String) => (output: String) with M1() as m1
    facet Consumer(f2: F2) => (out: String) andThen {
        yield Consumer(out = $.f2.m1.bogus)     // ← `bogus` is not on M1
    }
}
```

→ `Invalid mixin attribute '$.f2.m1.bogus': mixin facet 'M1' has no param, return, or mixin alias named 'bogus'`

## Wrong — addressing a mixin that has no alias

```ffl
namespace x {
    facet M1(in: String) => (out: String)
    facet F1(input: String) => (output: String) with M1()        // ← no `as`
    facet Consumer(f1: F1) => (out: String) andThen {
        yield Consumer(out = $.f1.M1)            // ← M1 is unaddressable
    }
}
```

→ `Invalid FacetRef attribute '$.f1.M1': facet 'F1' has no param, return, or mixin alias named 'M1'`

A mixin without an `as` alias is unreachable through a FacetRef by
design — the consumer-side namespace would otherwise collide with
primary attributes (see
[MIXIN_ALIAS_NAME_CONFLICT](MIXIN_ALIAS_NAME_CONFLICT.md)). To expose a
mixin, give it an alias:

```ffl
facet F1(input: String) => (output: String) with M1() as m1
```

## Correct

```ffl
namespace x {
    facet M1(in: String) => (out: String)
    facet M2(in: String) => (out: String)
    facet F2(input: String) => (output: String) with M1() as m1 with M2() as m2
    facet Consumer(f2: F2) => (out: String) andThen {
        V1 = Value(input = $.f2.output)         // primary return
        V2 = Value(input = $.f2.input)          // primary param
        V3 = Value(input = $.f2.m1.out)         // via mixin alias
        V4 = Value(input = $.f2.m2.out)         // via mixin alias
        yield Consumer(out = V1.out)
    }
}
```

## Why

A FacetRef parameter routes attribute reads to the persisted upstream
step record. The set of legal `<name>` values is determined by what
*can* live on that record:

- The facet's **params** — bound input values, persisted on the step
  row.
- The facet's **returns** — computed output values, persisted on the
  step row at evaluation time.
- The facet's **mixin aliases** — each aliased mixin produces a
  sub-step row addressable by alias.

The validator checks the first one or two segments after the
FacetRef param against this union. Deeper paths (e.g.
`$.fref.alias.field.nested`) are validated at runtime by the
evaluator's path resolver.

## See also

- [STEP_REF_FACET_MISMATCH](STEP_REF_FACET_MISMATCH.md) — facet-name
  match on pass-by-step.
- [MIXIN_ALIAS_NAME_CONFLICT](MIXIN_ALIAS_NAME_CONFLICT.md) — aliases
  share namespace with primary attributes.
- [REF_INVALID_STEP_ATTRIBUTE](REF_INVALID_STEP_ATTRIBUTE.md) — sibling
  rule for `step.attr` (not `$.input.attr`).
