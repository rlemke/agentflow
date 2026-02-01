## Semantic Validation (12_validation.md)

The AFL compiler performs semantic validation after parsing to ensure program correctness.

---

## Validation Rules

### 1. Name Uniqueness

#### Within Top-Level Scope
All facet, event facet, and workflow names must be unique:
```afl
facet User(name: String)
facet User(email: String)  // ERROR: Duplicate facet name 'User'
```

#### Within a Namespace
Names must be unique within each namespace:
```afl
namespace team.data {
    facet User(name: String)
    facet User(email: String)  // ERROR: Duplicate facet name 'User'
}
```

Same names in different namespaces are allowed:
```afl
namespace team.a {
    facet User(name: String)  // OK
}
namespace team.b {
    facet User(name: String)  // OK - different namespace
}
```

#### Within a Block
Step names must be unique within each `andThen` block:
```afl
workflow Test(input: String) andThen {
    step1 = Process(value = $.input)
    step1 = Process(value = $.input)  // ERROR: Duplicate step name 'step1'
}
```

---

### 2. Step References

#### Input References (`$.attr`)
Must reference a valid parameter of the containing facet/workflow:
```afl
workflow Test(input: String) andThen {
    step1 = Process(value = $.input)      // OK
    step2 = Process(value = $.nonexistent) // ERROR: no parameter named 'nonexistent'
}
```

#### Step References (`step.attr`)
Must reference:
1. A step defined **before** the current step
2. A valid return attribute of that step's facet

```afl
facet Data(value: String) => (result: String)

workflow Test(input: String) andThen {
    step1 = Data(value = $.input)
    step2 = Data(value = step1.result)     // OK
    step3 = Data(value = step1.nonexistent) // ERROR: invalid attribute
    step4 = Data(value = step5.result)     // ERROR: undefined step
    step5 = Data(value = $.input)
}
```

#### Foreach Variables
The foreach iteration variable can be referenced within the block:
```afl
workflow Process(items: Json) andThen foreach item in $.items {
    step1 = Handle(data = item.value)  // OK - 'item' is the foreach variable
}
```

---

### 3. Yield Validation

#### Valid Targets
A yield must target either:
- The containing facet/workflow, OR
- One of its mixins

```afl
workflow Test(input: String) => (output: String) andThen {
    step1 = Process(value = $.input)
    yield Test(output = step1.result)      // OK
    yield WrongFacet(output = step1.result) // ERROR: invalid yield target
}
```

#### Multiple Yields
Multiple yields are allowed, each targeting a different facet/mixin:
```afl
workflow Test(input: String) => (output: String) with Extra(data = "x") andThen {
    step1 = Process(value = $.input)
    yield Test(output = step1.result)   // OK
    yield Extra(data = step1.result)    // OK - targets mixin
}
```

#### No Duplicate Targets
Each yield must reference a different target:
```afl
workflow Test(input: String) => (output: String) andThen {
    step1 = Process(value = $.input)
    yield Test(output = step1.result)
    yield Test(output = step1.result)  // ERROR: duplicate yield target 'Test'
}
```

---

### 4. Use Statement Validation

The `use` statement must reference an existing namespace:
```afl
namespace lib.utils {
    facet Helper(value: String)
}

namespace app {
    use lib.utils           // OK - namespace exists
    use nonexistent.module  // ERROR: namespace does not exist
}
```

---

### 5. Facet Name Resolution

#### Ambiguity Detection
When a facet name exists in multiple imported namespaces, it must be qualified:
```afl
namespace a.b {
    facet SomeFacet(input: String) => (result: String)
}
namespace c.d {
    facet SomeFacet(input: String) => (result: String)
}
namespace app {
    use a.b
    use c.d
    facet App(input: String) => (output: String) andThen {
        s = SomeFacet(input = $.input)      // ERROR: ambiguous reference
        s = a.b.SomeFacet(input = $.input)  // OK: fully qualified
        yield App(output = s.result)
    }
}
```

#### Local Precedence
Facets in the current namespace take precedence over imports:
```afl
namespace lib {
    facet Helper(value: String) => (result: String)
}
namespace app {
    use lib
    facet Helper(value: String) => (result: String)  // Local definition
    facet App(input: String) => (output: String) andThen {
        h = Helper(value = $.input)  // OK: uses local Helper, no ambiguity
        yield App(output = h.result)
    }
}
```

#### Resolution Order
1. Fully qualified name (exact match)
2. Current namespace (takes precedence)
3. Imported namespaces (ambiguity check)
4. Top-level declarations

---

## Implementation

### File: `afl/validator.py`

```python
from afl import parse, validate

ast = parse(source)
result = validate(ast)

if result.is_valid:
    print("Valid!")
else:
    for error in result.errors:
        print(f"Line {error.line}: {error.message}")
```

### Classes
| Class | Purpose |
|-------|---------|
| `AFLValidator` | Main validator class |
| `ValidationResult` | Contains list of errors, `is_valid` property |
| `ValidationError` | Error with message, line, column |

### CLI Integration
Validation runs by default during CLI compilation:
```bash
# Validation enabled (default)
afl input.afl

# Skip validation
afl input.afl --no-validate
```

---

## Error Messages

| Error | Example |
|-------|---------|
| Duplicate name | `Duplicate facet name 'User' (previously defined at line 1)` |
| Duplicate step | `Duplicate step name 'step1' (previously defined at line 3)` |
| Invalid input ref | `Invalid input reference '$.foo': no parameter named 'foo'` |
| Undefined step | `Reference to undefined step 'step2'` |
| Invalid attribute | `Invalid attribute 'foo' for step 'step1': valid attributes are ['result']` |
| Invalid yield | `Invalid yield target 'Wrong': must be the containing facet or one of its mixins. Valid targets are: ['Test']` |
| Duplicate yield | `Duplicate yield target 'Test': each yield must reference a different facet or mixin` |
| Invalid use | `Invalid use statement: namespace 'nonexistent' does not exist` |
| Ambiguous facet | `Ambiguous facet reference 'Facet': could be a.b.Facet, c.d.Facet. Use fully qualified name to disambiguate.` |
| Unknown facet | `Unknown facet 'nonexistent.Facet'` |
