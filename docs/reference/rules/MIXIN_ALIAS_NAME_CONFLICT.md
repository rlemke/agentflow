# MIXIN_ALIAS_NAME_CONFLICT — Mixin alias must not collide with the primary facet's attributes or another mixin alias

A mixin in a facet signature may be given an alias with `as <name>`. The
alias becomes a consumer-side name on any FacetRef that points to this
facet's step: `$.fref.<alias>.<field>`. The alias therefore **shares a
namespace** with the facet's own parameters, return fields, and other
mixin aliases, and may not collide with any of them.

## Wrong — alias collides with a parameter

```ffl
namespace x {
    facet M1(input: String) => (output: String)
    facet F3(m1: String) => (out: String) with M1() as m1   // ← `m1` is also a param
}
```

→ `Mixin alias 'm1' on facet 'F3' conflicts with a parameter of the same name`

## Wrong — alias collides with a return field

```ffl
namespace x {
    facet M1(input: String) => (output: String)
    facet F4(input: String) => (m1: String) with M1() as m1   // ← `m1` is also a return
}
```

→ `Mixin alias 'm1' on facet 'F4' conflicts with a return field of the same name`

## Wrong — two mixins share an alias

```ffl
namespace x {
    facet M1(input: String) => (output: String)
    facet M2(input: String) => (output: String)
    facet F5(input: String) => (out: String) with M1() as m with M2() as m
                                                                       // ↑ duplicate
}
```

→ `Duplicate mixin alias 'm' on facet 'F5' (also used by 'with M1')`

## Correct

```ffl
namespace x {
    facet M1(input: String) => (output: String)
    facet M2(input: String) => (output: String)
    facet F2(input: String) => (output: String) with M1() as m1 with M2() as m2
}
```

A consumer that takes `F2` by reference may then read either mixin's
attributes through the alias:

```ffl
facet S2(f2: F2) => (output: String) andThen {
    V1 = Value(input = $.f2.output)
    V2 = Value(input = $.f2.m1.output)
    V3 = Value(input = $.f2.m2.output)
}
```

## Why

A FacetRef parameter's consumer can read attributes of the referenced
step through `$.<param>.<name>.<field>`. The `<name>` slot is resolved
against the referenced facet's namespace of accessible attributes, which
spans **(a)** its own param names, **(b)** its own return-field names,
and **(c)** the aliases of any mixins on its signature. Allowing a
collision in this namespace would make the reference ambiguous — the
resolver could not tell whether `$.f.m1` refers to a primary attribute
`m1` or to the aliased mixin step.

If a mixin in a signature has **no** alias, it is unreachable through a
FacetRef — by design, since giving the consumer a way to address it by
the mixin facet's name would conflict with the rule that aliases share
the same namespace as primary attributes. To expose a mixin to a
consumer, give it an `as` alias.

## See also

- [STEP_REF_FACET_MISMATCH](STEP_REF_FACET_MISMATCH.md) — facet-name match
  on pass-by-step.
- [REF_INVALID_STEP_ATTRIBUTE](REF_INVALID_STEP_ATTRIBUTE.md) — base
  field-access validation on `step.field` references.
