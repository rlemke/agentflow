# TYPE_CONTAINMENT_OPERAND — `in` / `not in` / `contains` collection operand isn't a collection or String

The collection-side operand of `in`, `not in`, or `contains` must be a
collection (array, set) or a String (substring search). Other types —
particularly Boolean — have no meaningful membership relation.

For `a in B` and `a not in B`, the collection side is `B` (right).
For `A contains b`, the collection side is `A` (left).

## Wrong

```ffl
namespace x {
    facet F(items: [String], flag: Boolean) => (out: Boolean) andThen {
        sys.assert("x" in $.flag)         // ← right side is Boolean
        sys.assert($.flag contains "y")   // ← left side is Boolean
        yield F(out = true)
    }
}
```

→ `Type error: operator 'in' requires a collection or String operand, got Boolean`

## Correct

```ffl
namespace x {
    facet F(items: [String], name: String) => (out: Boolean) andThen {
        sys.assert("x" in $.items)        // collection on right
        sys.assert($.name contains "@")   // String on left (substring)
        sys.assert("foo" not in $.items)
        yield F(out = true)
    }
}
```

## Why

`in` / `not in` / `contains` need a container to ask membership of.
Booleans and numbers aren't containers, so the operation has no
defined result — the validator catches that early instead of letting
a misleading runtime error surface later.
