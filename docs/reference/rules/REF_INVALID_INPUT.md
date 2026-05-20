# REF_INVALID_INPUT — `$.foo` references a parameter that doesn't exist

An input reference (`$.<name>`) names a parameter that is not declared on
the containing facet/workflow.

## Wrong

```ffl
namespace x {
    workflow W(name: String) => (greeting: String) andThen {
        yield W(greeting = $.user)   // ← W has 'name', not 'user'
    }
}
```

→ `Invalid input reference '$.user': no parameter named 'user'`

## Correct

```ffl
namespace x {
    workflow W(name: String) => (greeting: String) andThen {
        yield W(greeting = $.name)
    }
}
```

## Why

`$.x` resolves against the containing signature's parameter list (and,
inside an `andThen foreach`, the loop variable). The fix is either to
correct the name or to add the parameter to the signature. Note that
parameter visibility does not extend to step-call parameters — those are
named arguments matched against the called facet's parameters, a separate
namespace.

### Mixin body scope isolation

This rule is also the compile-time check for the **mixin body scope
isolation** runtime contract: when a facet is used as an aliased mixin
(`with M(x = $.input) as m` on a parent facet sig), the mixin's body
runs with `$.` bound only to the mixin sub-step's own attributes — no
workflow root inheritance, no parent reach-out. The runtime enforces
this in `facetwork/runtime/handlers/initialization.py::_resolve_inputs`;
the validator enforces it via `REF_INVALID_INPUT` because the mixin
facet's body can only legally reference names in its own params.

A `$.outside_scope` reference inside a facet body is rejected here
regardless of whether the facet is ever used as a mixin — so any code
that validates clean is also safe under mixin execution. The runtime
catches the corresponding violation as `ReferenceError`, but the
compile-time path is preferred.
