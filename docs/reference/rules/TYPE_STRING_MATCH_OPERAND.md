# TYPE_STRING_MATCH_OPERAND — `startsWith` / `endsWith` operands aren't both String

The `startsWith` and `endsWith` operators require both operands to be
String. They test substring matches and have no defined meaning for
other types.

## Wrong

```ffl
namespace x {
    facet F(value: Int, prefix: String) => (out: Boolean) andThen {
        sys.assert($.value startsWith $.prefix)  // ← Int startsWith String
        yield F(out = true)
    }
}
```

→ `Type error: operator 'startsWith' requires String operands, got Int`

## Correct

```ffl
namespace x {
    facet F(url: String) => (out: Boolean) andThen {
        sys.assert($.url startsWith "https://")
        sys.assert($.url endsWith ".com")
        yield F(out = true)
    }
}
```

## Why

The operators are defined on strings. Coercing non-strings (e.g.
implicit `str(...)`) would mask author errors — usually the wrong
operand was passed. Strict typing keeps the language honest about
what the operator means.
