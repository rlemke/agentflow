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
