# SCRIPT_EMPTY — Script block has no code

A `script` block was declared with no body (or only whitespace).

## Wrong

```ffl
namespace x {
    facet Process(in: String) => (out: String) script python ""
}
```

→ `Script block must contain code`

## Correct

```ffl
namespace x {
    facet Process(in: String) => (out: String) script python "
        result['out'] = inputs['in'].upper()
    "
}
```

## Why

An empty script block has no behavior. If you really want a no-op, omit
the script block entirely and let the runtime use the default handler
or pass-through behavior.
