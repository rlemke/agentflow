# REF_UNDEFINED_STEP — Reference to a step name that wasn't defined

A `step.attr` expression names a step that doesn't exist in the current scope.

## Wrong

```ffl
namespace x {
    facet A() => (out: String)
    workflow W() => (r: String) andThen {
        a = A()
        yield W(r = b.out)
    }
}
```

→ `Reference to undefined step 'b'`

## Correct

```ffl
namespace x {
    facet A() => (out: String)
    workflow W() => (r: String) andThen {
        a = A()
        yield W(r = a.out)
    }
}
```

## Why

Steps are visible to later code in the same `andThen` block (and to nested
step bodies). A typo in the step name is the most common cause; cross-block
references are reported separately as `REF_CROSS_BLOCK_STEP`.
