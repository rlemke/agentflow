## Implementation Constraints (Mandatory)

### Terminology

- **AgentFlow**: The platform for distributed workflow execution (compiler + runtime + agents)
- **AFL**: Agent Flow Language — the DSL for defining workflows (`.afl` files)
- **AFL Agent**: A standalone service that polls the task queue for event facet tasks, performs the required action (API call, data processing, etc.), writes the result back to the step, and signals the workflow to continue. Agents are built using the `AgentPoller` library and register callbacks for qualified event facet names (e.g. `osm.geo.Geocode`). Multiple agents can run concurrently, each handling different event facet types.

### Language Requirements

The AFL v1 reference implementation SHALL be written in **Python 3.11+**.

The language parser SHALL be implemented using **Lark**:
- Lark grammar format (.lark)
- LALR parser mode
- Explicit lexer rules
- Line and column error reporting

ANTLR, PLY, Parsimonious, regex-based parsers, or handwritten parsers SHALL NOT be used.

### Implementation Status (v0.5.1)

All specified runtime features are implemented:

| Feature | Spec Reference | Implementation |
|---------|---------------|----------------|
| EventTransmit blocking for event facets | `30_runtime.md` §8.1, `50_event_system.md` §6 | `EventTransmitHandler` blocks for `EventFacetDecl`, passes through for regular facets |
| StepContinue event handling | `30_runtime.md` §12.1, `50_event_system.md` §7 | `Evaluator.continue_step()` resumes event-blocked steps with result data |
| Facet definition resolution | `30_runtime.md` §11.1 | `get_facet_definition()` performs qualified and short-name lookups across the Program AST |
| Statement-level block creation | `30_runtime.md` §8.2, `51_state_system.md` | `StatementBlocksBeginHandler` creates blocks from workflow root, inline statement, or facet-level bodies |
| Nested block AST resolution | `30_runtime.md` §8.3, `51_state_system.md` | `get_block_ast()` resolves workflow root, statement-level, and facet-level block ASTs |
| Multi-run execution model | `30_runtime.md` §10.2, `50_event_system.md` §8 | Evaluator returns `PAUSED` at fixed point with event-blocked steps; `resume()` re-enters the iteration loop |

See `spec/70_examples.md` Examples 2–4 for detailed execution traces demonstrating these features.
