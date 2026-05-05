# PROMPT_MISSING_TEMPLATE — Prompt block is missing the `template` directive

A `prompt` block was declared but no `template "..."` directive was
provided. The template is the user-message content for the LLM and is
required.

## Wrong

```ffl
namespace x {
    event facet Summarize(text: String) => (summary: String) prompt {
        system "You are a helpful summarizer."
        model "claude-sonnet-4-6"
    }
}
```

→ `Prompt block must have a 'template' directive`

## Correct

```ffl
namespace x {
    event facet Summarize(text: String) => (summary: String) prompt {
        system "You are a helpful summarizer."
        template "Summarize this in two sentences:\n{text}"
        model "claude-sonnet-4-6"
    }
}
```

## Why

Without a `template`, the prompt block has no user message to send. The
runtime treats prompt blocks as the unit of work for LLM-driven event
facets, so a missing template is a hard error rather than a warning.
