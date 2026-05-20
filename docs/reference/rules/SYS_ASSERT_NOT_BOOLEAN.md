# SYS_ASSERT_NOT_BOOLEAN — `sys.assert(...)` condition isn't Boolean

The argument to `sys.assert(...)` must be a Boolean-typed expression.
The assertion fires when the expression evaluates to `false`; that
contract is only meaningful for Boolean values.

## Wrong

```ffl
namespace x {
    facet F(input: String) => (output: String) andThen {
        s1 = Identity(value = $.input)
        sys.assert(s1.value)            // ← String, not Boolean
        sys.assert(42)                  // ← Int, not Boolean
        yield F(output = s1.value)
    }
}
```

→ `sys.assert condition must be Boolean, got String`

## Correct

Compare the value to something, or use one of the boolean
operators (`==`, `!=`, `in`, `not in`, `contains`, `startsWith`,
`endsWith`, `&&`, `||`, `!`):

```ffl
namespace x {
    facet F(input: String) => (output: String) andThen {
        s1 = Identity(value = $.input)
        sys.assert(s1.value != "")
        sys.assert(s1.value in ["a", "b", "c"])
        sys.assert(s1.value startsWith "http")
        yield F(output = s1.value)
    }
}
```

## Why

`sys.assert` is a runtime invariant check: when the condition is
`false`, the containing step is marked errored and the
ancestor-error-propagation kicks in (catch handlers still apply).
Any other type would have undefined semantics — should
`sys.assert("non-empty string")` pass because the string is
truthy, or always fail because it isn't Boolean? The language
takes the strict position and rejects the construct at compile
time.
