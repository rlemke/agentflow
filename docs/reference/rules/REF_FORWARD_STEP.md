# REF_FORWARD_STEP — Step references a sibling that hasn't been defined yet

A step's call arguments reference another step that comes later in the
same block. Step ordering inside an `andThen` block is significant.

## Wrong

```ffl
namespace x {
    facet A(in: String) => (out: String)
    facet B() => (val: String)
    workflow W() => (r: String) andThen {
        a = A(in = b.val)         // ← 'b' is defined below
        b = B()
        yield W(r = a.out)
    }
}
```

→ `Step 'a' cannot reference step 'b' which is not defined before it`

## Correct

```ffl
namespace x {
    facet A(in: String) => (out: String)
    facet B() => (val: String)
    workflow W() => (r: String) andThen {
        b = B()
        a = A(in = b.val)
        yield W(r = a.out)
    }
}
```

## Why

Within a single `andThen` block, steps are ordered top-to-bottom and a
step can only reference steps that precede it. This makes data flow
explicit and matches how the runtime schedules dependencies. (To express
parallelism between independent steps, put them in sibling `andThen`
blocks instead.)
