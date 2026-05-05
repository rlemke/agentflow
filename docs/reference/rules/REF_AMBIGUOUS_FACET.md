# REF_AMBIGUOUS_FACET — Unqualified facet name matches more than one declaration

An unqualified facet name (e.g. `Process`) appears in multiple visible
namespaces and the validator can't pick one.

## Wrong

```ffl
namespace a { facet Process() => (out: String) }
namespace b { facet Process() => (out: String) }
namespace caller {
    use a
    use b
    workflow W() => (r: String) andThen {
        p = Process()                 // ← which one?
        yield W(r = p.out)
    }
}
```

→ `Ambiguous facet reference 'Process': could be a.Process, b.Process. Use fully qualified name to disambiguate.`

## Correct

```ffl
namespace caller {
    use a
    use b
    workflow W() => (r: String) andThen {
        p = a.Process()
        yield W(r = p.out)
    }
}
```

## Why

Resolution order is: current namespace → imported namespaces → top-level.
Local declarations always win over imports, and a single import wins over
none — but two imports with the same short name are ambiguous on purpose,
to prevent silent dependency on import order. Using the fully qualified
name is always safe.
