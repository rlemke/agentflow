# IMPLICIT_UNKNOWN_PARAM — Implicit passes an unknown parameter to its target facet

An `implicit name = Call(...)` declaration passes a named argument that
the target facet doesn't accept.

## Wrong

```ffl
namespace x {
    facet Process(in: String) => (out: String)
    implicit p = Process(input = "hi")    // ← Process has 'in', not 'input'
}
```

→ `Implicit 'p' passes unknown parameter 'input' to facet 'Process'`

## Correct

```ffl
namespace x {
    facet Process(in: String) => (out: String)
    implicit p = Process(in = "hi")
}
```

## Why

Implicits are pre-bound facet calls. Their arguments are checked against
the target's declared parameters at compile time, the same way step
calls are.
