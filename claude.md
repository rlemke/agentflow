# CLAUDE.md — AgentFlow Repo Guide
Repo root: /Users/ralph_lemke/agentflow

## Purpose of this repository
This repository contains the **AgentFlow** platform:
- **AFL compiler** that parses AFL source using Lark (LALR) and emits JSON workflow definitions
- **AFL runtime** that executes compiled workflows with iterative evaluation and dependency-driven step creation
- AST representation using Python dataclasses
- Command-line interface for compilation

## Terminology
- **AgentFlow**: The platform for distributed workflow execution (compiler + runtime + agents)
- **AFL**: Agent Flow Language — the DSL for defining workflows (`.afl` files)

AFL is designed as a programming-language-style workflow DSL: workflows are authored in `.afl` files, compiled to JSON, and executed by AgentFlow agents.

---

## Conceptual model (use these terms consistently)

### Core constructs
- **Facet**: a typed attribute structure with parameters and optional return clause.
- **Event Facet**: a facet prefixed with `event` that triggers agent execution.
- **Workflow**: a facet designated as an entry point for execution.
- **Step**: an assignment of a call expression within an `andThen` block.
- **Schema**: a named typed structure (`schema Name { field: Type }`) used as a type in parameter signatures.

### Composition features
- **Mixins**: `with FacetA() with FacetB()` composes normalized facets.
- **Implicit facets**: `implicit name = Call()` declares default values.
- **andThen / yield blocks**: compose multi-step internal logic.
- **andThen foreach**: iterate over collections with parallel execution.

---

## Repository map

```
agentflow/
├── afl/                        # AFL compiler package
│   ├── __init__.py             # Package exports
│   ├── ast.py                  # AST node dataclasses (27 node types)
│   ├── parser.py               # Lark parser wrapper with error handling
│   ├── transformer.py          # Parse tree → AST transformer
│   ├── emitter.py              # AST → JSON emitter
│   ├── validator.py            # Semantic validator
│   ├── source.py               # Source input and provenance tracking
│   ├── loader.py               # Source loaders (file, MongoDB, Maven)
│   ├── config.py               # Configuration (MongoDB, etc.)
│   ├── cli.py                  # Command-line interface
│   ├── grammar/
│   │   └── afl.lark            # Lark LALR grammar
│   ├── runtime/                # AFL runtime engine
│   │   ├── __init__.py         # Package exports
│   │   ├── types.py            # StepId, BlockId, ObjectType, FacetAttributes
│   │   ├── states.py           # StepState constants and transitions
│   │   ├── step.py             # StepDefinition and StepTransition
│   │   ├── block.py            # StepAnalysis for block tracking
│   │   ├── persistence.py      # PersistenceAPI Protocol
│   │   ├── memory_store.py     # In-memory implementation for testing
│   │   ├── mongo_store.py      # MongoDB persistence implementation
│   │   ├── evaluator.py        # Main iteration loop
│   │   ├── expression.py       # Expression evaluation (refs, arithmetic)
│   │   ├── dependency.py       # DependencyGraph from AST
│   │   ├── events.py           # Event lifecycle
│   │   ├── telemetry.py        # Structured logging
│   │   ├── errors.py           # Runtime error types
│   │   ├── agent_poller.py     # AgentPoller library for standalone agents
│   │   ├── changers/           # State changers
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Abstract StateChanger
│   │   │   ├── step_changer.py # Full state machine
│   │   │   ├── block_changer.py# Block state machine
│   │   │   └── yield_changer.py# Yield state machine
│   │   ├── handlers/           # State handlers
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # StateHandler base class
│   │   │   ├── initialization.py
│   │   │   ├── scripts.py
│   │   │   ├── blocks.py
│   │   │   ├── capture.py
│   │   │   ├── completion.py
│   │   │   └── block_execution.py
│   │   └── runner/             # Distributed runner service
│   │       ├── __init__.py     # Exports: RunnerService, RunnerConfig
│   │       ├── service.py      # RunnerService class + RunnerConfig dataclass
│   │       └── __main__.py     # CLI: python -m afl.runtime.runner
│   ├── mcp/                    # MCP server for LLM agents
│   │   ├── __init__.py         # Exports: create_server
│   │   ├── server.py           # MCP Server with tools + resources
│   │   ├── store.py            # MongoStore singleton factory
│   │   ├── serializers.py      # Entity → dict converters
│   │   └── __main__.py         # CLI: python -m afl.mcp
│   └── dashboard/              # Web monitoring dashboard
│       ├── __init__.py         # create_app() export
│       ├── app.py              # FastAPI app factory, Jinja2 setup
│       ├── __main__.py         # python -m afl.dashboard entry point
│       ├── dependencies.py     # MongoStore dependency injection
│       ├── filters.py          # Jinja2 filters (timestamps, state colors, etc.)
│       ├── routes/
│       │   ├── __init__.py     # Register all routers
│       │   ├── home.py         # GET / — summary dashboard
│       │   ├── runners.py      # Runner list, detail, cancel/pause/resume
│       │   ├── steps.py        # Step detail, retry action
│       │   ├── flows.py        # Flow list, detail, AFL source, JSON view
│       │   ├── servers.py      # Server status
│       │   ├── logs.py         # Log viewer per runner
│       │   ├── tasks.py        # Task queue viewer
│       │   └── api.py          # JSON API endpoints (htmx partials + programmatic)
│       ├── templates/          # Jinja2 templates (base, pages, partials)
│       └── static/
│           └── style.css       # State badge colors, layout tweaks
├── tests/
│   ├── test_parser.py          # Parser tests
│   ├── test_emitter.py         # Emitter tests
│   ├── test_validator.py       # Validator tests
│   ├── test_source.py          # Source input tests
│   ├── test_config.py          # Configuration tests
│   ├── test_cli.py             # CLI argument parsing and error handling tests
│   ├── test_runner_main.py     # Runner service CLI entry point tests
│   ├── runtime/                # Runtime tests
│   │   ├── test_types.py
│   │   ├── test_states.py
│   │   ├── test_step.py
│   │   ├── test_persistence.py
│   │   ├── test_dependency.py
│   │   ├── test_expression.py
│   │   ├── test_events.py      # Event lifecycle tests
│   │   ├── test_mongo_store.py # MongoDB persistence tests
│   │   ├── test_evaluator.py   # Integration tests for spec examples
│   │   ├── test_runner_service.py # Distributed runner service tests
│   │   ├── test_agent_poller.py # AgentPoller library tests
│   │   ├── test_agent_poller_async.py # Async handler tests
│   │   ├── test_agent_poller_extended.py # AgentPoller edge case tests
│   │   ├── test_script_executor.py # Sandboxed script execution tests
│   │   └── test_addone_agent.py # AddOne agent integration test
│   ├── test_loader.py          # MongoDB and Maven source loader tests
│   ├── mcp/                    # MCP server tests
│   │   ├── test_server.py      # Tool + resource integration tests
│   │   ├── test_server_extended.py # Continue/resume/resource edge cases
│   │   ├── test_serializers.py # Serializer unit tests
│   │   └── test_store.py       # MongoStore singleton factory tests
│   └── dashboard/              # Dashboard tests
│       ├── test_app.py         # App creation and route registration
│       ├── test_filters.py     # Jinja2 filter unit tests
│       ├── test_routes.py      # Route integration tests (TestClient + mongomock)
│       ├── test_step_routes.py # Step detail and name resolution tests
│       └── test_dependencies.py # Dependency injection tests
├── agents/                     # Multi-language agent integration libraries
│   ├── protocol/               # Cross-language protocol constants
│   │   ├── constants.json      # Collection names, states, document schemas, MongoDB ops
│   │   └── README.md           # External agent workflow documentation
│   ├── templates/              # Standalone files for new agent repos
│   │   ├── CLAUDE.md           # Drop-in CLAUDE.md with full protocol reference
│   │   └── README.md           # Instructions for using the templates
│   ├── scala/
│   │   └── afl-agent/          # Scala agent library (sbt project)
│   │       ├── build.sbt       # Scala 3.3.x, mongo-scala-driver, scalatest
│   │       ├── project/
│   │       │   └── build.properties
│   │       ├── src/main/scala/afl/agent/
│   │       │   ├── Protocol.scala          # Constants matching constants.json
│   │       │   ├── AgentPollerConfig.scala  # Config case class with JSON/env loading
│   │       │   ├── AgentPoller.scala        # Poll loop, handler registration, lifecycle
│   │       │   ├── MongoOps.scala           # MongoDB operations (claim, read, write, resume)
│   │       │   ├── ServerRegistration.scala # Server register/deregister/heartbeat
│   │       │   └── model/
│   │       │       ├── TaskDocument.scala       # Task BSON codec
│   │       │       ├── StepAttributes.scala     # Step params/returns extraction
│   │       │       └── ServerDocument.scala      # Server BSON codec
│   │       └── src/test/scala/afl/agent/
│   │           ├── ProtocolSpec.scala       # Constants verified against constants.json
│   │           ├── MongoOpsSpec.scala        # TaskDocument serialization tests
│   │           └── AgentPollerSpec.scala     # Poller + config + attributes tests
│   ├── go/
│   │   └── afl-agent/          # Go agent library
│   │       ├── go.mod          # Module definition
│   │       ├── protocol.go     # Constants matching constants.json
│   │       ├── config.go       # Config struct with JSON/env loading
│   │       ├── models.go       # TaskDocument, StepDocument, ServerDocument
│   │       ├── mongo_ops.go    # MongoDB operations
│   │       ├── server_registration.go # Server lifecycle
│   │       ├── poller.go       # AgentPoller with goroutine pool
│   │       └── poller_test.go  # Unit tests
│   ├── typescript/
│   │   └── afl-agent/          # TypeScript/Node.js agent library
│   │       ├── package.json    # npm package definition
│   │       ├── tsconfig.json   # TypeScript configuration
│   │       └── src/
│   │           ├── index.ts    # Package exports
│   │           ├── protocol.ts # Constants
│   │           ├── config.ts   # AgentPollerConfig
│   │           ├── models.ts   # Document types
│   │           ├── mongo-ops.ts # MongoDB operations
│   │           ├── server-registration.ts # Server lifecycle
│   │           ├── poller.ts   # AgentPoller with async/await
│   │           └── poller.test.ts # Jest tests
│   └── java/
│       └── afl-agent/          # Java agent library
│           ├── pom.xml         # Maven configuration
│           └── src/
│               ├── main/java/afl/agent/
│               │   ├── Protocol.java       # Static constants
│               │   ├── AgentPollerConfig.java # Config record
│               │   ├── AgentPoller.java    # Poller with ExecutorService
│               │   ├── Handler.java        # Functional interface
│               │   ├── MongoOps.java       # MongoDB operations
│               │   ├── ServerRegistration.java # Server lifecycle
│               │   └── model/
│               │       ├── TaskDocument.java
│               │       ├── StepAttribute.java
│               │       └── ServerDocument.java
│               └── test/java/afl/agent/
│                   └── AgentPollerTest.java # JUnit 5 tests
├── examples/                   # Example agents and workflows
│   └── osm-geocoder/           # OSM geocoding and data processing agent
│       ├── afl/                # AFL source files (20 files)
│       │   ├── geocoder.afl    # Schema, event facet, geocoding workflows
│       │   ├── osmtypes.afl    # OSMCache, GraphHopperCache schemas
│       │   ├── osmcache.afl    # ~250 cache event facets (11 namespaces)
│       │   ├── osmoperations.afl # Download, Tile, RoutingGraph operations
│       │   ├── osmpoi.afl      # POI extraction facets
│       │   ├── osmgraphhopper.afl # GraphHopper routing graph operations
│       │   ├── osmgraphhoppercache.afl # ~200 GraphHopper cache facets
│       │   ├── osmgraphhopper_workflows.afl # Regional routing graph workflows
│       │   ├── osmafrica.afl   # Africa workflow (cache + download steps)
│       │   ├── osmasia.afl     # Asia workflow
│       │   ├── osmaustralia.afl # Australia/Oceania workflow
│       │   ├── osmcanada.afl   # Canada provinces workflow
│       │   ├── osmcentralamerica.afl # Central America workflow
│       │   ├── osmeurope.afl   # Europe workflow
│       │   ├── osmnorthamerica.afl # North America workflow
│       │   ├── osmsouthamerica.afl # South America workflow
│       │   ├── osmunitedstates.afl # US states workflow
│       │   ├── osmcontinents.afl # Continents workflow
│       │   ├── osmworld.afl    # World workflow (composes all regions)
│       │   └── osmshapefiles.afl # Europe shapefile download workflow
│       ├── handlers/           # Python event handlers (~480 facets)
│       │   ├── __init__.py     # register_all_handlers(poller)
│       │   ├── cache_handlers.py # ~250 region cache handlers (Geofabrik)
│       │   ├── operations_handlers.py # 13 data processing handlers
│       │   ├── poi_handlers.py # 8 POI extraction handlers
│       │   └── graphhopper_handlers.py # ~200 GraphHopper routing handlers
│       ├── agent.py            # Live agent (AgentPoller + Nominatim API)
│       ├── test_geocoder.py    # Offline end-to-end test
│       ├── requirements.txt    # Python dependencies (requests)
│       └── README.md           # Example documentation
├── scripts/                    # Executable convenience scripts
│   ├── compile                 # Compile AFL source to JSON
│   ├── server                  # Run a workflow from MongoDB
│   ├── runner                  # Start the distributed runner service
│   ├── dashboard               # Start the web dashboard
│   ├── mcp-server              # Start the MCP server
│   └── db-stats                # Show database collection statistics
├── spec/                       # Language specifications
│   ├── 00_overview.md          # Implementation constraints
│   ├── 10_language.md          # AFL syntax (EBNF grammar)
│   ├── 11_semantics.md         # AST requirements
│   ├── 12_validation.md        # Semantic validation rules
│   ├── 20_compiler.md          # Compiler architecture
│   ├── 30_runtime.md           # Runtime specification
│   ├── 80_acceptance_tests.md  # Test requirements
│   └── 90_nonfunctional.md     # Dependencies
├── pyproject.toml              # Project configuration
└── README.md                   # User documentation
```

---

## Build / test / run
From repo root:

### Setup virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate

# Install for development (includes pytest, ruff, mypy, pre-commit)
pip install -e ".[dev]"

# For full stack development
pip install -e ".[dev,test,dashboard,mcp,mongodb]"
```

### Run unit tests
```bash
pytest tests/ -v
```

### Run MongoDB tests against a real server
```bash
pytest tests/runtime/test_mongo_store.py --mongodb -v
```

This connects to the MongoDB server from the AFL config (see Configuration below).
Without `--mongodb`, tests use mongomock (no real server needed).

### Run with coverage
```bash
pytest tests/ --cov=afl --cov-report=term-missing
```

### Use the CLI
```bash
# Parse file to JSON
afl input.afl -o output.json

# Parse from stdin
echo 'facet Test()' | afl

# Syntax check only
afl input.afl --check

# Use a custom config file
afl input.afl --config /path/to/afl.config.json
```

### Run the dashboard
```bash
# Start the dashboard (default port 8080)
python -m afl.dashboard

# Custom port and config
python -m afl.dashboard --port 9000 --config /path/to/afl.config.json

# Development mode with auto-reload
python -m afl.dashboard --reload
```

### Run dashboard tests
```bash
pytest tests/dashboard/ -v
```

### Run the distributed runner service
```bash
# Start the runner (connects to MongoDB)
python -m afl.runtime.runner

# Custom configuration
python -m afl.runtime.runner --config /path/to/afl.config.json

# Handle specific event topics only
python -m afl.runtime.runner --topics TopicA TopicB

# Increase concurrency
python -m afl.runtime.runner --max-concurrent 10 --poll-interval 500

# Custom HTTP status port (auto-increments if in use)
python -m afl.runtime.runner --port 9090
```

### Run runner service tests
```bash
pytest tests/runtime/test_runner_service.py -v
```

### Run agent poller tests
```bash
pytest tests/runtime/test_agent_poller.py -v
```

### Run the MCP server
```bash
# Start the MCP server (stdio transport)
python -m afl.mcp

# Custom config
python -m afl.mcp --config /path/to/afl.config.json
```

### Run MCP server tests
```bash
pytest tests/mcp/ -v
```

### Build and test the Scala agent library
```bash
# Compile
cd agents/scala/afl-agent && sbt compile

# Run tests (42 tests)
cd agents/scala/afl-agent && sbt test

# Package as JAR
cd agents/scala/afl-agent && sbt package
```

### Convenience scripts
All scripts are in `scripts/` and are self-contained (no need to set `PYTHONPATH`):
```bash
scripts/compile input.afl -o output.json      # compile AFL to JSON
scripts/compile input.afl --check              # syntax check only
scripts/server --workflow MyWorkflow           # execute a workflow from MongoDB
scripts/server --flow-id ID --input '{"x":1}' # execute with inputs
scripts/runner                                 # start distributed runner
scripts/runner --topics TopicA --max-concurrent 10
scripts/runner --port 9090                     # custom HTTP status port
scripts/dashboard                              # start web UI on port 8080
scripts/dashboard --port 9000 --reload         # dev mode on custom port
scripts/mcp-server                             # start MCP server (stdio)
scripts/mcp-server --config /path/to/config.json
scripts/db-stats                               # show database statistics
scripts/db-stats --json                        # output stats as JSON
```

### Configuration

AFL uses a JSON config file (`afl.config.json`) for service connections. The config is resolved in this order:

1. Explicit `--config FILE` CLI argument
2. `AFL_CONFIG` environment variable
3. `afl.config.json` in the current directory, `~/.afl/`, or `/etc/afl/`
4. Environment variables (`AFL_MONGODB_*`)
5. Built-in defaults

**Example configuration:**
```json
{
  "mongodb": {
    "url": "mongodb://localhost:27017",
    "username": "",
    "password": "",
    "authSource": "admin",
    "database": "afl"
  }
}
```

Each developer can use their own database name to avoid conflicts:
```json
{
  "mongodb": {
    "database": "afl_dev_alice"
  }
}
```

**Environment variables (recommended for credentials):**
| Variable | Default |
|----------|---------|
| `AFL_MONGODB_URL` | `mongodb://localhost:27017` |
| `AFL_MONGODB_USERNAME` | (empty) |
| `AFL_MONGODB_PASSWORD` | (empty) |
| `AFL_MONGODB_AUTH_SOURCE` | `admin` |
| `AFL_MONGODB_DATABASE` | `afl` |

---

## Implementation status

### Completed (v0.1.0) - Compiler
- ✅ Lark LALR grammar for AFL syntax
- ✅ AST dataclasses for all language constructs
- ✅ Parser with line/column error reporting
- ✅ JSON emitter with optional source locations
- ✅ Semantic validator (name uniqueness, references, yields)
- ✅ CLI for file and stdin parsing with validation

### Completed (v0.2.0) - Runtime
- ✅ State machine with 20+ states for step execution
- ✅ Three state changers (Step, Block, Yield) with transition tables
- ✅ Iterative evaluator with atomic commits at iteration boundaries
- ✅ Dependency-driven step creation from AST
- ✅ Expression evaluation (InputRef, StepRef, BinaryExpr, ConcatExpr)
- ✅ In-memory persistence for testing
- ✅ MongoDB persistence with auto-created collections and indexes
- ✅ Configurable database name for developer/test isolation
- ✅ Event lifecycle management
- ✅ Structured telemetry logging
- ✅ Spec examples 21.1 and 21.2 passing

### Completed (v0.3.0) - Dashboard
- ✅ FastAPI + Jinja2 + htmx web dashboard for monitoring workflows
- ✅ Summary home page with runner/server/task counts
- ✅ Runner list (filterable by state), detail with steps/logs/params
- ✅ Step detail with attributes (params/returns), retry action
- ✅ Flow list, detail, AFL source view with syntax highlighting, compiled JSON view
- ✅ Server status, log viewer, task queue pages
- ✅ Action endpoints: cancel/pause/resume runners, retry failed steps
- ✅ JSON API endpoints for programmatic access
- ✅ htmx auto-refresh (5s polling) for live step/runner state updates
- ✅ 361 tests passing

### Completed (v0.4.0) - Distributed Runner Service
- ✅ RunnerService: long-lived process polling for blocked steps and pending tasks
- ✅ Distributed locking via MongoDB for coordinated multi-instance execution
- ✅ ToolRegistry dispatch with continue_step and workflow resume
- ✅ Server registration with heartbeat and handled-count stats
- ✅ ThreadPoolExecutor for concurrent work item processing
- ✅ Per-work-item lock extension threads
- ✅ Graceful shutdown with SIGTERM/SIGINT signal handling
- ✅ RunnerConfig dataclass for all tunable parameters
- ✅ CLI entry point (python -m afl.runtime.runner) with argparse
- ✅ get_steps_by_state() persistence API extension
- ✅ Embedded HTTP status server (`/health`, `/status`) with auto-port probing

### Completed (v0.4.1) - Event Task-Queue Architecture
- ✅ Qualified facet names: steps store `"namespace.FacetName"` for namespaced facets
- ✅ `resolve_qualified_name()` on `ExecutionContext` and `DependencyGraph`
- ✅ `get_facet_definition()` supports both qualified (`ns.Facet`) and short (`Facet`) lookups
- ✅ Task creation at EVENT_TRANSMIT: `EventTransmitHandler` creates `TaskDefinition` in task queue
- ✅ Tasks committed atomically alongside steps and events via `IterationChanges.created_tasks`
- ✅ `claim_task()` on `PersistenceAPI`: atomic PENDING → RUNNING transition
- ✅ MemoryStore `claim_task()` with `threading.Lock` for atomicity
- ✅ MongoStore `claim_task()` via `find_one_and_update()` with compound index
- ✅ Partial unique index `(step_id, state=running)` ensures one agent per event step
- ✅ RunnerService claims event tasks from task queue instead of polling step state
- ✅ `_process_event_task()`: dispatch → continue_step → resume → mark completed/failed
- ✅ `runner_id` propagated from RunnerService through Evaluator to task creation
- ✅ `--topics` accepts qualified facet names (e.g. `ns.CountDocuments`)
- ✅ 618 tests passing

### Completed (v0.5.0) - MCP Server
- ✅ MCP server exposing AFL compiler and runtime to LLM agents
- ✅ 6 tools: compile, validate, execute_workflow, continue_step, resume_workflow, manage_runner
- ✅ 10 resources: runners, steps, flows, servers, tasks (with sub-resources)
- ✅ stdio transport (standard for local MCP servers)
- ✅ Reusable serializers module for entity-to-dict conversion
- ✅ CLI entry point (python -m afl.mcp) with argparse
- ✅ 599 tests passing

### Completed (v0.5.1) - Agent Poller Library
- ✅ `Evaluator.fail_step(step_id, error_message)`: marks event-blocked step as STATEMENT_ERROR
- ✅ `AgentPollerConfig` dataclass: service_name, server_group, task_list, poll_interval_ms, max_concurrent, heartbeat_interval_ms
- ✅ `AgentPoller` class: standalone event polling library for building AFL Agent services
- ✅ `register(facet_name, callback)`: register callbacks for qualified event facet names
- ✅ `start()` / `stop()`: blocking poll loop with server registration and heartbeat
- ✅ `poll_once()`: synchronous single cycle for testing (no thread pool)
- ✅ Short name fallback: qualified task name `ns.Facet` matches handler registered as `Facet`
- ✅ AST caching: `cache_workflow_ast()` / `_load_workflow_ast()` for workflow resume
- ✅ Error handling: callback exceptions → `fail_step()` + task FAILED
- ✅ RunnerService updated to call `fail_step()` on event task failure
- ✅ AddOne agent integration test: end-to-end event facet handling with `handlers.AddOne`
- ✅ 639 tests passing

### Completed (v0.5.2) - Schema Declarations
- ✅ `schema` declarations at top level and inside namespaces
- ✅ `SchemaDecl`, `SchemaField`, `ArrayType` AST nodes
- ✅ Array types `[Type]` supported in schema fields and parameter signatures
- ✅ Schema names usable as types in facet/workflow parameters
- ✅ Schema name uniqueness validation (same pool as facets/workflows)
- ✅ Schema field name uniqueness validation
- ✅ JSON emitter support for schemas and array types
- ✅ 660 tests passing

### Completed (v0.6.0) - Scala Agent Library
- ✅ sbt project under `agents/scala/afl-agent/` with Scala 3.3.x
- ✅ `Protocol` object: constants matching `agents/protocol/constants.json`
- ✅ `AgentPollerConfig` case class with `fromConfig`/`resolve`/`fromEnvironment`
- ✅ `AgentPoller` class: poll loop, handler registration, lifecycle (mirrors Python AgentPoller)
- ✅ `MongoOps` class: claimTask, readStepParams, writeStepReturns, markTaskCompleted/Failed, insertResumeTask
- ✅ `ServerRegistration` class: register/deregister/heartbeat via MongoDB
- ✅ BSON model codecs: `TaskDocument`, `StepAttributes`, `ServerDocument` with fromBson/toBson
- ✅ Short name fallback: qualified task name `ns.Facet` matches handler registered as `Facet`
- ✅ `afl:resume` protocol task insertion for Python RunnerService workflow resumption
- ✅ 42 tests passing (protocol constants verification, serialization round-trips, poller unit tests)

### Completed (v0.5.3) - OSM Geocoder Example
- ✅ 20 AFL source files defining geographic data processing workflows
- ✅ `OSMCache` and `GraphHopperCache` schema declarations (`osmtypes.afl`)
- ✅ ~250 cache event facets across 11 geographic namespaces (`osmcache.afl`)
- ✅ 13 operations event facets: Download, Tile, RoutingGraph, Status, PostGisImport, DownloadShapefile (plus *All variants) (`osmoperations.afl`)
- ✅ 8 POI event facets: POI, Cities, Towns, Suburbs, Villages, Hamlets, Countries (`osmpoi.afl`)
- ✅ **GraphHopper routing graph integration**:
  - 6 operation facets: BuildGraph, BuildMultiProfile, BuildGraphAll, ImportGraph, ValidateGraph, CleanGraph (`osmgraphhopper.afl`)
  - ~200 per-region cache facets across 9 namespaces (`osmgraphhoppercache.afl`)
  - Regional workflow compositions: BuildMajorEuropeGraphs, BuildNorthAmericaGraphs, BuildWestCoastGraphs, BuildEastCoastGraphs (`osmgraphhopper_workflows.afl`)
  - `recreate` flag parameter to control graph rebuilding (default: use cached graph if exists)
  - Supports routing profiles: car, bike, foot, motorcycle, truck, hike, mtb, racingbike
- ✅ Regional workflows composing cache lookups with download operations (Africa, Asia, Australia, Canada, Central America, Europe, North America, South America, United States, Continents)
- ✅ Shapefile download workflow for Europe (`osmshapefiles.afl`) — reuses cache facets, routes through `DownloadShapefile`
- ✅ World workflow orchestrating all regional workflows (`osmworld.afl`)
- ✅ Python handler modules with Geofabrik URL registry and factory-pattern handler generation
- ✅ Multi-format downloader: `download(region, fmt="pbf"|"shp")` supports PBF (default) and Geofabrik free shapefiles
- ✅ `register_all_handlers(poller)` for batch registration of ~480 event facet handlers
- ✅ Agent updated to handle geocoding + all OSM data events + GraphHopper routing
- ✅ 879 tests passing

### Completed (v0.7.0) - LLM Integration & Multi-Language Agents
- ✅ **Async AgentPoller**: `register_async()` for async/await handlers (LLM integration)
- ✅ **Partial results**: `update_step()` for streaming handler output
- ✅ **Prompt templates**: `prompt {}` block syntax for LLM-based event facets
  - `system`, `template`, `model` directives
  - Placeholder validation (`{param_name}` must match facet parameters)
- ✅ **Script blocks**: `script {}` block syntax for inline Python execution
  - Sandboxed execution with restricted built-ins
  - `params` dict for input, `result` dict for output
- ✅ **Source loaders**: MongoDB and Maven source loading implemented
  - `SourceLoader.load_mongodb(collection_id, display_name)` for flows collection
  - `SourceLoader.load_maven(group_id, artifact_id, version, classifier)` for Maven Central
  - CLI: `--mongo UUID:Name` and `--maven group:artifact:version[:classifier]`
- ✅ **Go agent library** (`agents/go/afl-agent/`):
  - `AgentPoller` with goroutine pool for concurrency
  - `MongoOps`, `ServerRegistration`, `Config` modules
  - Short name fallback for handler lookup
  - 6 tests passing
- ✅ **TypeScript agent library** (`agents/typescript/afl-agent/`):
  - `AgentPoller` with async/await and `setInterval` polling
  - Full npm package with Jest tests
  - `resolveConfig()` for standard config resolution
- ✅ **Java agent library** (`agents/java/afl-agent/`):
  - `AgentPoller` with `ExecutorService` for concurrency
  - Maven project with JUnit 5 tests
  - `Handler` functional interface for lambda registration
- ✅ 879 tests passing

### MCP Protocol Messages

The MCP server uses JSON-RPC 2.0 over stdio. The following protocol messages are relevant:

| Message | Direction | AFL Handler |
|---------|-----------|-------------|
| `initialize` | Client → Server | SDK auto-handles; advertises `tools` + `resources` capabilities |
| `notifications/initialized` | Client → Server | SDK auto-handles |
| `ping` | Bidirectional | SDK auto-handles |
| `tools/list` | Client → Server | `list_tools()` → returns 6 Tool definitions with JSON Schema |
| `tools/call` | Client → Server | `call_tool(name, arguments)` → dispatches to `_tool_*` functions |
| `resources/list` | Client → Server | `list_resources()` → returns 10 Resource definitions with `afl://` URIs |
| `resources/read` | Client → Server | `read_resource(uri)` → routes to `_handle_resource()` |

Messages **not implemented**: `prompts/*`, `completion`, `resources/subscribe`, `sampling/createMessage`, `logging/setLevel`.

### MCP Tools — Parameters and Returns

| Tool | Parameters | Returns |
|------|-----------|---------|
| `afl_compile` | `source: str` | `{ success, json?, errors? }` |
| `afl_validate` | `source: str` | `{ valid, errors: [{ message, line?, column? }] }` |
| `afl_execute_workflow` | `source: str`, `workflow_name: str`, `inputs?: dict` | `{ success, workflow_id, status, iterations, outputs, error? }` |
| `afl_continue_step` | `step_id: str`, `result?: dict` | `{ success, error? }` |
| `afl_resume_workflow` | `workflow_id: str`, `source: str`, `workflow_name: str`, `inputs?: dict` | `{ success, workflow_id, status, iterations, outputs, error? }` |
| `afl_manage_runner` | `runner_id: str`, `action: str` (cancel/pause/resume) | `{ success, error? }` |

### MCP Resources — URI Patterns and Response Schemas

| URI Pattern | Response Shape |
|-------------|---------------|
| `afl://runners` | `[{ uuid, workflow_id, workflow_name, state, start_time, end_time, duration, parameters }]` |
| `afl://runners/{id}` | `{ uuid, workflow_id, workflow_name, state, start_time, end_time, duration, parameters }` |
| `afl://runners/{id}/steps` | `[{ id, workflow_id, object_type, state, statement_id, container_id, block_id, facet_name?, params?, returns? }]` |
| `afl://runners/{id}/logs` | `[{ uuid, order, runner_id, step_id, note_type, note_originator, note_importance, message, state, time }]` |
| `afl://steps/{id}` | `{ id, workflow_id, object_type, state, statement_id, container_id, block_id, facet_name?, params?, returns? }` |
| `afl://flows` | `[{ uuid, name, path, workflows: [{ uuid, name, version }], sources, facets }]` |
| `afl://flows/{id}` | `{ uuid, name, path, workflows, sources, facets }` |
| `afl://flows/{id}/source` | `{ uuid, name, sources: [{ name, content, language }] }` |
| `afl://servers` | `[{ uuid, server_group, service_name, server_name, state, start_time, ping_time, topics, handlers, handled }]` |
| `afl://tasks` | `[{ uuid, name, runner_id, workflow_id, flow_id, step_id, state, created, updated, task_list_name, data_type }]` |

### AST Node Types
| Category | Nodes |
|----------|-------|
| Root | `Program` |
| Declarations | `Namespace`, `UsesDecl`, `FacetDecl`, `EventFacetDecl`, `WorkflowDecl`, `ImplicitDecl`, `SchemaDecl` |
| Schemas | `SchemaField`, `ArrayType` |
| Signatures | `FacetSig`, `Parameter`, `TypeRef`, `ReturnClause` |
| Mixins | `MixinSig`, `MixinCall` |
| Blocks | `AndThenBlock`, `Block`, `ForeachClause`, `PromptBlock`, `ScriptBlock` |
| Statements | `StepStmt`, `YieldStmt` |
| Expressions | `CallExpr`, `NamedArg`, `Reference`, `Literal` |
| Metadata | `SourceLocation`, `ASTNode` |

---

## How Claude should review changes

### Language/compiler correctness
- Parsing errors must include line/column
- Grammar must be LALR-compatible (no conflicts)
- AST nodes must use dataclasses
- JSON output must be stable and consistent

### Testing requirements
- All grammar constructs must have parser tests
- Error cases must verify line/column reporting
- Emitter must round-trip all AST node types

### Code quality
- Type hints on all functions
- Docstrings on public API
- No runtime dependencies beyond lark (dashboard, mcp deps are optional)

---

## Glossary

### Compiler terms
- **AgentFlow**: The platform for distributed workflow execution
- **AFL**: Agent Flow Language — the DSL for defining workflows
- **Facet**: Base declaration type with parameters
- **Event Facet**: Facet that triggers external execution
- **Workflow**: Entry point facet with execution body
- **Mixin**: Composable capability attached to facets/calls
- **Step**: Named assignment in an `andThen` block
- **Yield**: Final output merge statement in a block
- **Schema**: Named typed structure for defining JSON shapes; usable as a type in parameter signatures
- **ArrayType**: Array type syntax `[ElementType]` for schema fields and parameters
- **PromptBlock**: Block syntax for LLM-based event facets with `system`, `template`, and `model` directives
- **ScriptBlock**: Block syntax for inline sandboxed Python execution in facets
- **Provenance**: Metadata tracking where source code originated (file, MongoDB, Maven)
- **Source Loader**: Utility for loading AFL sources from different locations (file, MongoDB, Maven Central)

### Runtime terms
- **StepDefinition**: Runtime representation of a step with state and attributes
- **StepState**: Current execution state (e.g., `state.facet.initialization.Begin`)
- **StateChanger**: Drives step through state machine transitions
- **StateHandler**: Processes specific states (initialization, execution, completion)
- **Evaluator**: Main execution loop; runs iterations until fixed point
- **Iteration**: Single pass over all eligible steps; changes committed atomically
- **DependencyGraph**: Maps step references to determine creation order
- **PersistenceAPI**: Protocol for step/event storage (in-memory or database)
- **EventDefinition**: Domain lifecycle record for external work — tracks what needs to happen, the payload, and outcome (Created → Dispatched → Processing → Completed/Error)
- **TaskDefinition**: Claimable work item in the distributed queue — provides routing, atomic claiming, and locking so runners can compete safely. Created alongside an EventDefinition at EVENT_TRANSMIT; consumed by runners/agents (see `spec/50_event_system.md` §9)
- **RunnerService**: Long-lived distributed process that polls for blocked steps and tasks
- **RunnerConfig**: Configuration dataclass for runner service parameters
- **ToolRegistry**: Registry of handler functions for event facet dispatch
- **AFL Agent**: A service that accepts events/tasks, performs the required action, updates the step, and signals the step to continue
- **AgentPoller**: Standalone polling library for building AFL Agent services without the full RunnerService
- **AgentPollerConfig**: Configuration dataclass for AgentPoller parameters
- **MCP Server**: Model Context Protocol server exposing AFL tools and resources to LLM agents

### Agent integration library terms
- **Agent Integration Library**: Language-specific library for building AFL agents (Python, Scala, Go, TypeScript, Java)
- **Protocol Constants**: Shared constants (`agents/protocol/constants.json`) defining collection names, state values, document schemas, and MongoDB operations for cross-language interoperability
- **afl:resume**: Protocol task inserted by external agents after writing step returns; signals the Python RunnerService to resume the workflow
- **afl:execute**: Protocol task for executing a compiled workflow from a flow stored in MongoDB
- **Async Handler**: Handler function that returns a coroutine/Promise/Future; supported in Python (`register_async`), TypeScript, and Java

### MCP terms
- **MCP**: Model Context Protocol — JSON-RPC 2.0 protocol for LLM agent ↔ tool server communication
- **Tool**: MCP action endpoint (has side effects); invoked via `tools/call` with name + arguments
- **Resource**: MCP read-only data endpoint; accessed via `resources/read` with a URI
- **stdio transport**: Default MCP transport; server reads/writes JSON-RPC on stdin/stdout
- **TextContent**: MCP response content type; all AFL tools return `TextContent` with JSON payloads
- **inputSchema**: JSON Schema attached to each Tool definition; SDK validates arguments before dispatch
