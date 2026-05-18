# REF_INVALID_STEP_FORMAT — Step reference must name a step (and optionally an attribute)

A step reference must start with a step name. The reference may be **bare**
(just the step name, when passing a whole step as a parameter) or **dotted**
(`step.attribute` for field access).

## Wrong

An empty step reference is the only shape rejected by this rule:

```text
y = B(in = .)                     // ← empty step reference (no step named)
```

→ `Empty step reference`

## Correct — field access

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

## Correct — bare step reference (pass-by-step)

When a parameter is typed as a facet, you can pass the whole step:

```ffl
namespace x {
    facet A() => (out: String)
    facet B(src: A) => (r: String) andThen {
        yield B(r = $.src.out)
    }
    workflow W() => (r: String) andThen {
        a = A()
        b = B(src = a)            // ← bare step name; B receives the whole step
        yield W(r = b.r)
    }
}
```

## Why

Two reference shapes are accepted:

1. **`step.attribute`** — read a single output value from a completed step.
2. **`step`** (bare) — pass a `StepReference` into a parameter typed as a
   facet. The consumer reads multiple fields from the upstream step via
   `$.param.field` in `andThen` bodies, or via `ctx.fetch_step(ref)` in
   handler bodies.

The grammar accepts `step_ref: IDENT ("." IDENT)*` — the attribute portion
is optional. The validator only flags an empty reference. Existence of the
named step is still checked — see
[REF_UNDEFINED_STEP](REF_UNDEFINED_STEP.md).
