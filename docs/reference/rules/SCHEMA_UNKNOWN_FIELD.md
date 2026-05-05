# SCHEMA_UNKNOWN_FIELD — Schema instantiation passes a field the schema doesn't declare

A schema call uses a named argument whose name doesn't match any field
on the target schema. (As a warning, the same rule fires when accessing
`step.field` on a schema-typed value where the field doesn't exist.)

## Wrong

```ffl
namespace x {
    schema Order { sku: String, qty: Long }
    workflow W() => (r: String) andThen {
        o = Order(sku = "A", quantity = 1)   // ← field is 'qty', not 'quantity'
        yield W(r = o.sku)
    }
}
```

→ `Unknown field 'quantity' for schema 'Order'. Valid fields are: ['qty', 'sku']`

## Correct

```ffl
namespace x {
    schema Order { sku: String, qty: Long }
    workflow W() => (r: String) andThen {
        o = Order(sku = "A", qty = 1)
        yield W(r = o.sku)
    }
}
```

## Why

Schema instantiation is checked against the schema's declared fields.
The error lists the valid field names — pick from that list, or extend
the schema if the new field is genuinely needed.
