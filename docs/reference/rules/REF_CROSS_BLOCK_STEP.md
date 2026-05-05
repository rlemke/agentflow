# REF_CROSS_BLOCK_STEP — Reference to a step in a sibling `andThen` block

Sibling `andThen` blocks run concurrently and cannot see each other's
steps. The named step does exist — but in a different block.

## Wrong

```ffl
namespace x {
    facet A() => (out: String)
    facet B(in: String) => (r: String)
    workflow W() => (r: String) andThen {
        a = A()
    } andThen {
        b = B(in = a.out)         // ← 'a' is in the sibling block
        yield W(r = b.r)
    }
}
```

→ `Cross-block step reference: 'a' is defined in a sibling andThen block ...`

## Correct

Use a step body — `andThen` attached to a step expression — to compose
steps that depend on each other. Step bodies see the parent step's
context.

```ffl
namespace x {
    facet A() => (out: String)
    facet B(in: String) => (r: String)
    workflow W() => (r: String) andThen {
        a = A() andThen {
            b = B(in = a.out)
            yield W(r = b.r)
        }
    }
}
```

## Why

The runtime executes top-level `andThen` siblings in parallel. Allowing
cross-block references would force serialisation and make the parallelism
silent — instead the language requires you to be explicit about
ordering with a step body or `andThen when`.
