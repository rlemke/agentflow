# SCHEMA_INSTANTIATION_NO_MIXINS — Schema calls cannot have mixins

A schema instantiation uses `with X()` — but schemas are pure data and
do not support mixin composition.

## Wrong

```ffl
namespace x {
    schema Order { sku: String, qty: Long }
    facet Audit() => (at: String)
    workflow W() => (r: String) andThen {
        o = Order(sku = "A", qty = 1) with Audit()   // ← schemas can't mix in
        yield W(r = o.sku)
    }
}
```

→ `Schema instantiation 'Order' cannot have mixins. Schemas are simple data structures without mixin support.`

## Correct

Drop the mixin from the schema instantiation. If you want both a schema
result and an audit timestamp, instantiate them separately:

```ffl
namespace x {
    schema Order { sku: String, qty: Long }
    facet Audit() => (at: String)
    workflow W(at: String) => (r: String, at: String) with Audit() andThen {
        o = Order(sku = "A", qty = 1)
        yield W(r = o.sku)
        yield Audit(at = $.at)
    }
}
```

## Why

Mixins extend a *facet's* contract with extra return slots; they have no
meaning for a schema, which is just a typed record. The grammar permits
the syntax, but the validator rejects it to keep the data/behaviour split
clear.
