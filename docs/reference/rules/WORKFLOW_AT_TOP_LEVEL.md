# WORKFLOW_AT_TOP_LEVEL — Workflows must be declared inside a namespace

A `workflow` declaration appears at the top level.

## Wrong

```ffl
workflow SayHello(name: String) => (greeting: String) andThen {
    yield SayHello(greeting = "hello")
}
```

→ `Workflow 'SayHello' must be declared inside a namespace`

## Correct

```ffl
namespace hello {
    workflow SayHello(name: String) => (greeting: String) andThen {
        yield SayHello(greeting = "hello")
    }
}
```

## Why

Workflows are entry points the dashboard and runner address by qualified
name. A top-level workflow has no namespace, which breaks the addressing
scheme and conflicts with same-named workflows in different files. Even
single-file demos should put the workflow in a namespace — usually a
short one matching the file's purpose.
