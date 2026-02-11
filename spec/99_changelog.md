# Implementation Changelog

## Completed (v0.1.0) - Compiler
- Lark LALR grammar for AFL syntax
- AST dataclasses for all language constructs
- Parser with line/column error reporting
- JSON emitter with optional source locations
- Semantic validator (name uniqueness, references, yields)
- CLI for file and stdin parsing with validation

## Completed (v0.2.0) - Runtime
- State machine with 20+ states for step execution
- Three state changers (Step, Block, Yield) with transition tables
- Iterative evaluator with atomic commits at iteration boundaries
- Dependency-driven step creation from AST
- Expression evaluation (InputRef, StepRef, BinaryExpr, ConcatExpr)
- In-memory persistence for testing
- MongoDB persistence with auto-created collections and indexes
- Configurable database name for developer/test isolation
- Event lifecycle management
- Structured telemetry logging
- Spec examples 21.1 and 21.2 passing

## Completed (v0.3.0) - Dashboard
- FastAPI + Jinja2 + htmx web dashboard for monitoring workflows
- Summary home page with runner/server/task counts
- Runner list (filterable by state), detail with steps/logs/params
- Step detail with attributes (params/returns), retry action
- Flow list, detail, AFL source view with syntax highlighting, compiled JSON view
- Server status, log viewer, task queue pages
- Action endpoints: cancel/pause/resume runners, retry failed steps
- JSON API endpoints for programmatic access
- htmx auto-refresh (5s polling) for live step/runner state updates
- 361 tests passing

## Completed (v0.4.0) - Distributed Runner Service
- RunnerService: long-lived process polling for blocked steps and pending tasks
- Distributed locking via MongoDB for coordinated multi-instance execution
- ToolRegistry dispatch with continue_step and workflow resume
- Server registration with heartbeat and handled-count stats
- ThreadPoolExecutor for concurrent work item processing
- Per-work-item lock extension threads
- Graceful shutdown with SIGTERM/SIGINT signal handling
- RunnerConfig dataclass for all tunable parameters
- CLI entry point (python -m afl.runtime.runner) with argparse
- get_steps_by_state() persistence API extension
- Embedded HTTP status server (`/health`, `/status`) with auto-port probing

## Completed (v0.4.1) - Event Task-Queue Architecture
- Qualified facet names: steps store `"namespace.FacetName"` for namespaced facets
- `resolve_qualified_name()` on `ExecutionContext` and `DependencyGraph`
- `get_facet_definition()` supports both qualified (`ns.Facet`) and short (`Facet`) lookups
- Task creation at EVENT_TRANSMIT: `EventTransmitHandler` creates `TaskDefinition` in task queue
- Tasks committed atomically alongside steps and events via `IterationChanges.created_tasks`
- `claim_task()` on `PersistenceAPI`: atomic PENDING -> RUNNING transition
- MemoryStore `claim_task()` with `threading.Lock` for atomicity
- MongoStore `claim_task()` via `find_one_and_update()` with compound index
- Partial unique index `(step_id, state=running)` ensures one agent per event step
- RunnerService claims event tasks from task queue instead of polling step state
- `_process_event_task()`: dispatch -> continue_step -> resume -> mark completed/failed
- `runner_id` propagated from RunnerService through Evaluator to task creation
- `--topics` accepts qualified facet names (e.g. `ns.CountDocuments`)
- 618 tests passing

## Completed (v0.5.0) - MCP Server
- MCP server exposing AFL compiler and runtime to LLM agents
- 6 tools: compile, validate, execute_workflow, continue_step, resume_workflow, manage_runner
- 10 resources: runners, steps, flows, servers, tasks (with sub-resources)
- stdio transport (standard for local MCP servers)
- Reusable serializers module for entity-to-dict conversion
- CLI entry point (python -m afl.mcp) with argparse
- 599 tests passing

## Completed (v0.5.1) - Agent Poller Library
- `Evaluator.fail_step(step_id, error_message)`: marks event-blocked step as STATEMENT_ERROR
- `AgentPollerConfig` dataclass: service_name, server_group, task_list, poll_interval_ms, max_concurrent, heartbeat_interval_ms
- `AgentPoller` class: standalone event polling library for building AFL Agent services
- `register(facet_name, callback)`: register callbacks for qualified event facet names
- `start()` / `stop()`: blocking poll loop with server registration and heartbeat
- `poll_once()`: synchronous single cycle for testing (no thread pool)
- Short name fallback: qualified task name `ns.Facet` matches handler registered as `Facet`
- AST caching: `cache_workflow_ast()` / `_load_workflow_ast()` for workflow resume
- Error handling: callback exceptions -> `fail_step()` + task FAILED
- RunnerService updated to call `fail_step()` on event task failure
- AddOne agent integration test: end-to-end event facet handling with `handlers.AddOne`
- 639 tests passing

## Completed (v0.5.2) - Schema Declarations
- `schema` declarations at top level and inside namespaces
- `SchemaDecl`, `SchemaField`, `ArrayType` AST nodes
- Array types `[Type]` supported in schema fields and parameter signatures
- Schema names usable as types in facet/workflow parameters
- Schema name uniqueness validation (same pool as facets/workflows)
- Schema field name uniqueness validation
- JSON emitter support for schemas and array types
- 660 tests passing

## Completed (v0.6.0) - Scala Agent Library
- sbt project under `agents/scala/afl-agent/` with Scala 3.3.x
- `Protocol` object: constants matching `agents/protocol/constants.json`
- `AgentPollerConfig` case class with `fromConfig`/`resolve`/`fromEnvironment`
- `AgentPoller` class: poll loop, handler registration, lifecycle (mirrors Python AgentPoller)
- `MongoOps` class: claimTask, readStepParams, writeStepReturns, markTaskCompleted/Failed, insertResumeTask
- `ServerRegistration` class: register/deregister/heartbeat via MongoDB
- BSON model codecs: `TaskDocument`, `StepAttributes`, `ServerDocument` with fromBson/toBson
- Short name fallback: qualified task name `ns.Facet` matches handler registered as `Facet`
- `afl:resume` protocol task insertion for Python RunnerService workflow resumption
- 42 tests passing (protocol constants verification, serialization round-trips, poller unit tests)

## Completed (v0.5.3) - OSM Geocoder Example
- 22 AFL source files defining geographic data processing workflows
- `OSMCache` and `GraphHopperCache` schema declarations (`osmtypes.afl`)
- ~250 cache event facets across 11 geographic namespaces (`osmcache.afl`)
- 13 operations event facets: Download, Tile, RoutingGraph, Status, PostGisImport, DownloadShapefile (plus *All variants) (`osmoperations.afl`)
- 8 POI event facets: POI, Cities, Towns, Suburbs, Villages, Hamlets, Countries (`osmpoi.afl`)
- **GraphHopper routing graph integration**:
  - 6 operation facets: BuildGraph, BuildMultiProfile, BuildGraphAll, ImportGraph, ValidateGraph, CleanGraph (`osmgraphhopper.afl`)
  - ~200 per-region cache facets across 9 namespaces (`osmgraphhoppercache.afl`)
  - Regional workflow compositions: BuildMajorEuropeGraphs, BuildNorthAmericaGraphs, BuildWestCoastGraphs, BuildEastCoastGraphs (`osmgraphhopper_workflows.afl`)
  - `recreate` flag parameter to control graph rebuilding (default: use cached graph if exists)
  - Supports routing profiles: car, bike, foot, motorcycle, truck, hike, mtb, racingbike
- City-to-city pairwise routing workflow (`osmcityrouting.afl`): 9-step pipeline composing ResolveRegion -> Download -> BuildGraph -> ValidateGraph -> ExtractPlacesWithPopulation -> FilterByPopulationRange -> PopulationStatistics -> ComputePairwiseRoutes -> RenderLayers
- Regional workflows composing cache lookups with download operations (Africa, Asia, Australia, Canada, Central America, Europe, North America, South America, United States, Continents)
- Shapefile download workflow for Europe (`osmshapefiles.afl`)
- World workflow orchestrating all regional workflows (`osmworld.afl`)
- Python handler modules with Geofabrik URL registry and factory-pattern handler generation
- Multi-format downloader: `download(region, fmt="pbf"|"shp")` supports PBF and Geofabrik free shapefiles
- `register_all_handlers(poller)` for batch registration of ~480+ event facet handlers
- **Region name resolution** (`osmregion.afl`, `region_resolver.py`, `region_handlers.py`):
  - Resolves human-friendly names ("Colorado", "UK", "the Alps") to Geofabrik download paths
  - ~280 indexed regions, ~78 aliases, 25 geographic features
  - `prefer_continent` disambiguation for ambiguous names (e.g. Georgia)
  - 3 event facets: `ResolveRegion`, `ResolveRegions`, `ListRegions`
  - 3 composed region-based workflows
  - 20+ end-to-end pipeline examples with mock handlers
  - 80 unit tests for resolver
- 879+ tests passing (main suite) + 80 region resolver tests

## Completed (v0.7.0) - LLM Integration & Multi-Language Agents
- **Async AgentPoller**: `register_async()` for async/await handlers (LLM integration)
- **Partial results**: `update_step()` for streaming handler output
- **Prompt templates**: `prompt {}` block syntax for LLM-based event facets
  - `system`, `template`, `model` directives
  - Placeholder validation (`{param_name}` must match facet parameters)
- **Script blocks**: `script {}` block syntax for inline Python execution
  - Sandboxed execution with restricted built-ins
  - `params` dict for input, `result` dict for output
- **Source loaders**: MongoDB and Maven source loading implemented
  - `SourceLoader.load_mongodb(collection_id, display_name)` for flows collection
  - `SourceLoader.load_maven(group_id, artifact_id, version, classifier)` for Maven Central
  - CLI: `--mongo UUID:Name` and `--maven group:artifact:version[:classifier]`
- **Go agent library** (`agents/go/afl-agent/`)
- **TypeScript agent library** (`agents/typescript/afl-agent/`)
- **Java agent library** (`agents/java/afl-agent/`)
- 879 tests passing

## Completed (v0.7.1) - Live Integration Examples
- Integration test infrastructure (`examples/osm-geocoder/integration/`)
- AddOne, region resolution, population pipeline, and city routing integration tests
- `ComputePairwiseRoutes` handler with GraphHopper API and great-circle fallback
- Tests require `--mongodb` flag, optional deps auto-skipped with `pytest.importorskip`

## Completed (v0.8.0) - Expressions, Collections & Multiple Blocks
- **BinaryExpr**: arithmetic operators `+`, `-`, `*`, `/`, `%` with correct precedence hierarchy
- **Statement-level andThen body**: steps can have inline `andThen` blocks for sub-workflows
- **Multiple andThen blocks**: facets/workflows support multiple concurrent `andThen` blocks
- **Collection literals**: array `[expr, ...]`, map `#{"key": expr, ...}`, indexing `expr[expr]`, grouping `(expr)`
- **Expression type checking**: lightweight type inference catches string+int and bool+arithmetic errors at compile time
- Grammar: `postfix_expr` for indexing, `additive_expr`/`multiplicative_expr` for arithmetic precedence
- AST: `BinaryExpr`, `ArrayLiteral`, `MapEntry`, `MapLiteral`, `IndexExpr` nodes
- Runtime: expression evaluation and dependency extraction for all new expression types
- Validator: `_extract_references` recursive walker, `_infer_type` type checker
- 963 tests passing

## Completed (v0.8.1) - Multi-Block Fix, Foreach Execution & Iteration Traces
- **Multi-block AST resolution fix**: workflows with multiple `andThen` blocks now track block body index via `statement_id="block-N"`; `get_block_ast()` selects the correct body element from list
- **Foreach runtime execution**: `andThen foreach var in expr { ... }` creates one sub-block per array element
  - `StepDefinition` gains `foreach_var`/`foreach_value` fields for iteration binding
  - `BlockExecutionBeginHandler` evaluates iterable expression, creates sub-blocks with cached body AST
  - `BlockExecutionContinueHandler` tracks sub-block completion directly (bypasses DependencyGraph)
  - `FacetInitializationBeginHandler` propagates foreach variable to `EvaluationContext` for expression evaluation
  - Empty iterables produce no sub-blocks and complete immediately
- **Iteration-level trace tests**: step-by-step state progression verification at each commit boundary
  - Example 2 trace: 8 steps, 8 iterations, `Adder(a=1, b=2) -> result=3`
  - Example 3 trace: 11 steps, 11 iterations, nested `andThen -> result=13`
  - Example 4 trace: 11 steps, 2 evaluator runs (PAUSE at EventTransmit, resume after continue), `result=15`
  - Key runtime behavior: yield steps are created lazily (when dependencies are available), not eagerly in iteration 0
- **Acceptance tests**: event facet blocking at EventTransmit, step continue/resume, multi-run execution, nested statement blocks, facet definition lookup (namespaced EventFacetDecl)
- 978 tests passing

## Completed (v0.8.2) - Schema Field Comma Separators
- **Grammar**: `schema_fields` rule now requires commas between field definitions, consistent with `params` rule
- **Syntax**: `schema Foo { name: String, age: Int }` (commas required between fields, no trailing comma)
- Empty schemas and single-field schemas unchanged (no comma needed)
- Updated all 18 AFL example files (~45 schemas) across genomics and OSM geocoder examples
- Updated spec documentation (`10_language.md`, `12_validation.md`)
- 987 tests passing

## Completed (v0.9.0) - LLM Integration Features
- **Prompt template evaluation**: `PromptBlock` bodies on EventFacetDecl are interpolated with step params via `_evaluate_prompt_template()`; supports `system`, `template`, and `model` overrides
- **Multi-turn tool use loop**: `_call_claude()` now loops on `stop_reason="tool_use"`, executing intermediate tool calls and continuing the conversation until the target facet tool is called or `max_turns` is reached
- **Intelligent retry**: when the multi-turn loop fails to produce a target tool_use, the runner appends a retry message and re-attempts up to `max_retries` times
- **Script block execution**: `FacetScriptsBeginHandler` now executes `ScriptBlock` bodies via `ScriptExecutor`, writing results to step returns; error handling for syntax and runtime errors
- **LLMHandler utility class**: standalone `LLMHandler` + `LLMHandlerConfig` for building LLM-backed handlers compatible with `AgentPoller.register()`; supports prompt templates, multi-turn tool use, retry, and async dispatch
- `ToolDefinition` gains `prompt_block` field; `ClaudeAgentRunner` gains `max_turns` and `max_retries` constructor parameters
- 1015 tests passing

## Completed (v0.9.1) - HDFS Storage Abstraction
- **StorageBackend protocol**: `afl.runtime.storage` module with `exists`, `open`, `makedirs`, `getsize`, `getmtime`, `isfile`, `isdir`, `listdir`, `walk`, `rmtree`, `join`, `dirname`, `basename`
- **LocalStorageBackend**: thin wrapper around `os`, `os.path`, `shutil`, `builtins.open`
- **HDFSStorageBackend**: wraps `pyarrow.fs.HadoopFileSystem` with `hdfs://` URI parsing and caching per host:port
- **Factory function**: `get_storage_backend(path)` returns HDFS backend for `hdfs://` URIs, local singleton otherwise
- **Handler updates**: all OSM geocoder handlers (downloader, graphhopper, 6 extractors) and genomics cache handlers use storage abstraction
- **Configurable cache paths**: `AFL_CACHE_DIR` for OSM cache, `AFL_GENOMICS_CACHE_DIR` for genomics cache (supports `hdfs://` URIs)
- **Optional dependency**: `pyarrow>=14.0` in `[hdfs]` extra
- 1049 tests passing

## Completed (v0.9.2) - ScriptExecutor Subprocess Timeout
- **Subprocess execution**: `ScriptExecutor._execute_python` now runs scripts in a subprocess via `subprocess.run([sys.executable, "-c", ...])` instead of in-process `exec()`
- **Timeout enforcement**: `timeout` parameter (default 30s) is enforced via `subprocess.run(timeout=...)`, killing runaway scripts
- **Safe builtins**: `_SAFE_BUILTIN_NAMES` list drives sandbox reconstruction in both parent and subprocess; user `print()` calls captured via `io.StringIO` to prevent JSON protocol corruption
- **Worker protocol**: user code is base64-encoded, params serialized as JSON in, result dict serialized as JSON out via stdout
- **Error handling**: `subprocess.TimeoutExpired` → `ScriptResult(success=False, error="Script timed out after {timeout}s")`; non-serializable params fail early before subprocess launch
- 1056 tests passing

## Completed (v0.9.3) - Composed Facet Decomposition & Default Parameters
- **Composed facet**: `LoadVolcanoData` decomposed from a single event facet into a regular facet with `andThen` body chaining three event facets: `CheckRegionCache` → `DownloadVolcanoData` → `FilterByType`
- **Facet default parameter resolution**: `FacetInitializationBeginHandler` now applies default values from the facet definition for any params not provided in the call; fixes InputRef (`$.param`) resolution in facet bodies when callers omit defaulted args
- **New event facets**: `CheckRegionCache(region)` → `VolcanoCache`, `DownloadVolcanoData(region, cache_path)` → `VolcanoDataset`, `FilterByType(volcanoes, volcano_type)` → `VolcanoDataset`
- **New schema**: `VolcanoCache { region, path, cached }` for cache check results
- **Volcano-query example**: 7 event facets + 1 composed facet, 6 pause/resume cycles (was 4 event facets, 4 cycles)
- 1056 tests passing

## Completed (v0.9.4) - Cross-Namespace Composition & Generic Cache Delegation
- **osmoperations.afl fixes**: removed double `=>` on `Cache` event facet, fixed `OsmCache` → `OSMCache` typo on `Download`
- **FormatGeoJSON**: new event facet in `osm.geo.Visualization` with `FormatResult` schema (`output_path`, `text`, `feature_count`, `format`, `title`)
- **osmcache.afl refactor**: 280 event facets across 11 namespaces (`Africa`, `Asia`, `Australia`, `Europe`, `NorthAmerica`, `Canada`, `CentralAmerica`, `SouthAmerica`, `UnitedStates`, `Antarctica`, `Continents`) converted from `event facet` to composed `facet` with `andThen` body delegating to generic `Cache(region = "<Name>")`
- **osmgraphhoppercache.afl refactor**: 262 event facets across 8 namespaces converted from `event facet` to composed `facet` with `andThen` body delegating to generic `BuildGraph(cache, profile, recreate)`
- **volcano-query rewrite**: replaced all custom schemas and 7 event facets with cross-namespace composition using `osm.geo.Operations` (Cache, Download), `osm.geo.Filters` (FilterByOSMTag), `osm.geo.Elevation` (FilterByMaxElevation), `osm.geo.Visualization` (RenderMap, FormatGeoJSON)
- **AFL-only example**: removed volcano-query handlers, test runner, and agent — now relies entirely on existing OSM geocoder infrastructure
- **dl_*.downloadCache fix**: 254 attribute references across 10 continent workflow files corrected from `dl_*.cache` to `dl_*.downloadCache` (latent bug exposed by `OsmCache` → `OSMCache` type fix)
- **osmvoting.afl fix**: moved `TIGERCache` and `VotingDistrictResult` schemas into `census.types` namespace (schemas cannot be top-level); added `use census.types` to `Districts`, `Processing`, and `Workflows` namespaces
- **osmworkflows_composed.afl fix**: corrected `osm.geo.POI` → `osm.geo.POIs` namespace reference; fixed return attribute names (`pois` → `cities`/`towns`/`villages`)
- **Cross-example disambiguation**: qualified `Download` as `osm.geo.Operations.Download` in volcano.afl; added `use genomics.cache.Operations` to genomics_cache_workflows.afl to resolve ambiguous facet references when compiling all examples together
- **All examples compile together**: 47 AFL sources (volcano-query + osm-geocoder + genomics), 0 errors
- 1056 tests passing
