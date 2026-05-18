# STEP_REF_FACET_MISMATCH — Step reference facet does not match the parameter's declared facet type

When a parameter is typed as a facet (a step-reference parameter), the step
passed to it must be a call to **that exact facet**. Passing a step that calls
a different facet is flagged statically.

## Wrong

```ffl
namespace refs {
    facet DoSomething(input: String) => (output: String) andThen {
        yield DoSomething(output = $.input ++ "!")
    }
    facet OtherFacet(value: String) => (output: String) andThen {
        yield OtherFacet(output = $.value)
    }
    facet AnotherThing(ds: DoSomething) => (output: String) andThen {
        yield AnotherThing(output = $.ds.output)
    }
    workflow Demo(input: String) => (output: String) andThen {
        bad = OtherFacet(value = $.input)
        s2  = AnotherThing(ds = bad)        // ← OtherFacet step into DoSomething slot
        yield Demo(output = s2.output)
    }
}
```

→ `Step 'bad' is a 'OtherFacet', but parameter 'ds' expects a step of facet 'DoSomething'`

## Correct

```ffl
namespace refs {
    facet DoSomething(input: String) => (output: String) andThen {
        yield DoSomething(output = $.input ++ "!")
    }
    facet AnotherThing(ds: DoSomething) => (output: String) andThen {
        yield AnotherThing(output = $.ds.output)
    }
    workflow Demo(input: String) => (output: String) andThen {
        s1 = DoSomething(input = $.input)
        s2 = AnotherThing(ds = s1)         // ← DoSomething into DoSomething slot
        yield Demo(output = s2.output)
    }
}
```

## Why

A step-reference parameter (`ds: DoSomething`) tells the runtime two things:

1. **In `andThen` bodies**, `$.ds.<field>` is resolved lazily against the
   referenced step. The fields available depend on `DoSomething`'s declared
   returns — passing a different facet would let `$.ds.<field>` reach for
   fields that may not exist.
2. **In handler bodies**, the parameter arrives as a tagged JSON ref and the
   handler calls `ctx.fetch_step(ref)` to materialize it. The handler is
   written against `DoSomething`'s shape; a step of another facet would
   silently mismatch.

Mixin compatibility is **not** considered: the check is exact facet-name
equality. This is intentional for the first cut and may be relaxed later.

If you genuinely need to pass an unrelated step, project the fields you want
into a schema-typed parameter instead, or read individual fields via
`step.field` references.

## See also

- [REF_INVALID_STEP_FORMAT](REF_INVALID_STEP_FORMAT.md) — the bare-vs-dotted
  reference grammar.
- [REF_INVALID_STEP_ATTRIBUTE](REF_INVALID_STEP_ATTRIBUTE.md) — field-access
  validation on dotted references.
- [REF_UNDEFINED_STEP](REF_UNDEFINED_STEP.md) — referenced step must exist.
