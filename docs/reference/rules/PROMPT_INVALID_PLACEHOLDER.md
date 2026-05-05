# PROMPT_INVALID_PLACEHOLDER — `{name}` in template/system doesn't match a parameter

A prompt template references `{some_name}` but no parameter with that
name is declared on the facet signature.

## Wrong

```ffl
namespace x {
    event facet Summarize(text: String) => (summary: String) prompt {
        template "Summarize: {document}"   // ← param is 'text', not 'document'
    }
}
```

→ `Invalid placeholder '{document}' in template: no parameter named 'document'. Valid parameters are: ['text']`

## Correct

```ffl
namespace x {
    event facet Summarize(text: String) => (summary: String) prompt {
        template "Summarize: {text}"
    }
}
```

## Why

Placeholders are filled at runtime from the call's parameter values. A
placeholder that does not match a declared parameter would interpolate
empty (or worse, behave inconsistently between runtimes), so the
validator catches it at compile time. The check applies to both
`template` and `system` directives.
