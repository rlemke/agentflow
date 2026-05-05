# USE_UNKNOWN_NAMESPACE — `use` references a namespace that doesn't exist

A `use foo` statement names a namespace that isn't declared in any of
the files being compiled together.

## Wrong

```ffl
namespace x {
    use osm.utilities       // ← no such namespace
    workflow W() => (r: String) andThen {
        yield W(r = "hi")
    }
}
```

→ `Invalid use statement: namespace 'osm.utilities' does not exist`

## Correct

Either declare the namespace in another compiled source, or remove the
unused `use`:

```ffl
namespace osm.utilities {
    facet Helper() => (out: String)
}
namespace x {
    use osm.utilities
    workflow W() => (r: String) andThen {
        h = Helper()
        yield W(r = h.out)
    }
}
```

## Why

Imports must resolve so reference resolution can use them.
A `use` for a missing namespace would silently change which short names
are reachable; making it an error keeps the namespace graph honest.
