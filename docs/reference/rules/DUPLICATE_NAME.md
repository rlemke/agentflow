# DUPLICATE_NAME — Two declarations share the same name in the same scope

A facet, event facet, workflow, or schema name is declared twice in the
same namespace (or both at top level).

## Wrong

```ffl
namespace x {
    facet Process(in: String) => (out: String)
    facet Process(value: Long) => (out: Long)   // ← same short name
}
```

→ `Duplicate facet name 'Process' (previously defined at line 2)`

## Correct

Rename one of them:

```ffl
namespace x {
    facet ProcessText(in: String) => (out: String)
    facet ProcessNumber(value: Long) => (out: Long)
}
```

## Why

FFL has no overloading. Names within a scope must be unique across all
kinds (you cannot, for example, have a facet and a schema with the same
short name in the same namespace). The error message includes the line
number of the first declaration so you can decide which to rename.
