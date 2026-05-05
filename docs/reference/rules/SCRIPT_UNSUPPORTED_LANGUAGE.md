# SCRIPT_UNSUPPORTED_LANGUAGE — Script language is not supported

A `script` block specifies a language other than `python`. Only Python is
currently supported.

## Wrong

```ffl
namespace x {
    facet Process(in: String) => (out: String) script javascript "
        return { out: input.in.toUpperCase() }
    "
}
```

→ `Unsupported script language 'javascript'. Currently only 'python' is supported.`

## Correct

```ffl
namespace x {
    facet Process(in: String) => (out: String) script python "
        result['out'] = inputs['in'].upper()
    "
}
```

## Why

The runtime ships a single embedded interpreter for script blocks
(Python). Other languages would need their own sandboxed runtime, which
is out of scope. For non-Python logic, register an external handler and
use an `event facet` instead.
