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

## Completed (v0.9.5) - Standalone Local PBF/GeoJSON Verifier
- **OSMOSE API removed**: replaced external OSMOSE REST API integration (`osmose.openstreetmap.fr`) with a standalone local verifier — no network dependency
- **osmose_verifier.py**: new core module with `VerificationHandler(osmium.SimpleHandler)` for single-pass PBF processing (nodes → ways → relations); checks reference integrity, coordinate ranges (including null island), degenerate geometry, unclosed polygons, tag completeness, duplicate IDs; also validates GeoJSON files for structure, geometry, and property completeness
- **Severity levels**: level 1 (error) for reference integrity failures, out-of-bounds coords, degenerate geometry, duplicates; level 2 (warning) for missing name on named features, unclosed polygons; level 3 (info) for empty tag values
- **New event facets**: `VerifyAll(cache, output_dir, check_*)`, `VerifyGeometry(cache)`, `VerifyTags(cache, required_tags)`, `VerifyGeoJSON(input_path)`, `ComputeVerifySummary(input_path)`
- **New schemas**: `VerifyResult` (output_path, issue_count, node/way/relation counts, format, verify_date), `VerifySummary` (issue counts by type and severity, tag_coverage_pct, avg_tags_per_element)
- **osmose_handlers.py**: thin wrappers delegating to `osmose_verifier`; `register_osmose_handlers(poller)` signature preserved — `__init__.py` unchanged
- **Pattern 12 rewrite**: `OsmoseQualityCheck` workflow now uses cache-based local verification (Cache → VerifyAll → ComputeVerifySummary) instead of bbox-based API queries
- 1092 tests passing

## Completed (v0.9.6) - GTFS Transit Feed Support
- **osmgtfs.afl**: new `osm.geo.Transit.GTFS` namespace with `use osm.types`; 9 schemas (`StopResult`, `RouteResult`, `FrequencyResult`, `TransitStats`, `NearestStopResult`, `AccessibilityResult`, `CoverageResult`, `DensityResult`, `TransitReport`) and 10 event facets
- **GTFSFeed schema**: added to `osm.types` namespace (url, path, date, size, wasInCache, agency_name, has_shapes) — analogous to `OSMCache` and `GraphHopperCache`
- **Core event facets**: `DownloadFeed` (ZIP download with URL-hash caching), `ExtractStops` (stops.txt → GeoJSON points, location_type=0 filter), `ExtractRoutes` (shapes.txt linestrings with stop-sequence fallback), `ServiceFrequency` (trips-per-stop-per-day from stop_times.txt + calendar.txt), `TransitStatistics` (aggregate counts by route type)
- **OSM integration facets**: `NearestStops` (brute-force haversine nearest-neighbor lookup), `StopAccessibility` (400m/800m/beyond walk-distance bands)
- **Coverage facets**: `CoverageGaps` (grid overlay detecting cells with OSM features but no stops), `RouteDensity` (routes per grid cell), `GenerateReport` (consolidated analysis)
- **gtfs_extractor.py**: pure-stdlib implementation (`csv`, `zipfile`, `json`, `math`) — no new dependencies; `GTFSRouteType(IntEnum)` with `from_string()` and `label()` classmethods; safety cap of 10,000 grid cells; handles GTFS ZIPs with nested subdirectories; streams stop_times.txt for large feeds
- **gtfs_handlers.py**: thin factory-pattern wrappers (10 factories + `GTFS_FACETS` list + `register_gtfs_handlers(poller)`); follows `park_handlers.py` pattern with `_*_to_dict()` converters and `_empty_*()` helpers
- **Pattern 13 — TransitAnalysis**: `DownloadFeed → ExtractStops + ExtractRoutes → TransitStatistics` composed workflow
- **Pattern 14 — TransitAccessibility**: `OSM Cache + DownloadFeed → ExtractBuildings + ExtractStops → StopAccessibility → CoverageGaps` composed workflow
- 1092 tests passing

## Completed (v0.9.7) - Low-Zoom Road Infrastructure Builder (Zoom 2–7)
- **osmzoombuilder.afl**: new `osm.geo.Roads.ZoomBuilder` namespace with `use osm.types`; 6 schemas (`LogicalEdge`, `ZoomEdgeResult`, `ZoomBuilderResult`, `ZoomBuilderMetrics`, `ZoomBuilderConfig`, `CellBudget`) and 9 event facets (`BuildLogicalGraph`, `BuildAnchors`, `ComputeSBS`, `ComputeScores`, `DetectBypasses`, `DetectRings`, `SelectEdges`, `ExportZoomLayers`, `BuildZoomLayers`)
- **zoom_graph.py**: `TopologyHandler(osmium.SimpleHandler)` for two-pass PBF processing — caches node coordinates, collects highway-tagged ways, identifies decision nodes (degree ≥ 3, FC change, ref change, endpoints), splits ways at decision nodes, merges degree-2 chains into logical edges; `LogicalEdge` dataclass with FC scoring (base score + ref/bridge/tunnel/surface/access modifiers); `RoadGraph` class with adjacency lists, Dijkstra shortest path for backbone repair, JSON serialization/deserialization
- **zoom_sbs.py**: Structural Betweenness Sampling — `SegmentIndex` grid-based spatial index (~500m cells) for route-to-logical-edge snapping with point-to-segment perpendicular distance; `build_anchors()` snaps cities to nearest graph nodes with population thresholds per zoom level; `sample_od_pairs()` with minimum straight-line distance filtering and deterministic RNG; `route_batch_parallel()` via `ThreadPoolExecutor` hitting GraphHopper HTTP API; `accumulate_votes()` and `normalize_sbs()` (log-normalized against P95)
- **zoom_detection.py**: bypass detection via settlement models (city/town/village core radii), entry/exit node identification at outer boundary crossings, route comparison (unconstrained vs through-center waypoint) with time ratio, core fraction, and FC advantage thresholds; ring road detection for cities ≥ 100K population using radial entry nodes, orbital candidate vote accumulation, and geometry validation (coefficient of variation ≤ 0.35, mean radius range check)
- **zoom_selection.py**: per-zoom score computation with weight schedule (SB weight decreasing z2→z7, FC weight increasing); H3 hexagonal cell budgets at resolution 7 with density-adaptive factors (sparse 1.3× to ultra-dense 0.4×); greedy budgeted selection; backbone connectivity repair via BFS + Dijkstra path insertion; sparse region floor enforcement; monotonic reveal (cumulative set union z2→z7) assigning final `minZoom` per edge
- **zoom_builder.py**: 9-step pipeline orchestrator wiring graph construction → anchor building → SBS computation (z2–z6, z7 reuses z6) → bypass/ring detection → scoring → cell budgets → selection → monotonic reveal → export; outputs `segment_scores.csv`, `edge_importance.jsonl`, per-zoom cumulative GeoJSON (`roads_z{2..7}.geojson`), and `metrics.json`
- **zoom_handlers.py**: 9 thin factory-pattern wrappers following `park_handlers.py` convention; `ZOOM_FACETS` list + `register_zoom_handlers(poller)`
- **Pattern 15 — RoadZoomBuilder**: `Cache → BuildGraph → BuildZoomLayers(cache, graph)` composed workflow
- 1092 tests passing

## Completed (v0.9.8) - Fix Hardcoded Cache Calls in Composed Workflows
- **osmworkflows_composed.afl**: 13 workflows accepted a `region: String` parameter but hardcoded the cache call to `osm.geo.cache.Europe.Liechtenstein()`, ignoring the parameter entirely; replaced all 13 with `osm.geo.Operations.Cache(region = $.region)` so the region parameter is actually respected
- **Affected workflows**: `VisualizeBicycleRoutes`, `AnalyzeParks`, `LargeCitiesMap`, `TransportOverview`, `NationalParksAnalysis`, `TransportMap`, `StateBoundariesWithStats`, `DiscoverCitiesAndTowns`, `RegionalAnalysis`, `ValidateAndSummarize`, `OsmoseQualityCheck`, `TransitAccessibility`, `RoadZoomBuilder`
- **Unchanged** (correctly hardcoded — no `region` parameter): `GermanyCityAnalysis` (`Europe.Germany()`), `FranceCityAnalysis` (`Europe.France()`), `TransitAnalysis` (no cache, takes `gtfs_url` only)
- 1174 tests passing

## Completed (v0.9.9) - Fix AgentPoller Resume & Add Missing Handlers
- **AgentPoller program_ast propagation**: `_resume_workflow()` was calling `evaluator.resume(workflow_id, workflow_ast)` without `program_ast`, causing `get_facet_definition()` to return `None` for all facets; `EventTransmitHandler` then passed through without blocking, so event facet steps completed immediately with empty outputs
- **New `_program_ast_cache`**: `AgentPoller` now maintains a separate `_program_ast_cache` dict alongside `_ast_cache`; `cache_workflow_ast()` accepts optional `program_ast` parameter; `_resume_workflow()` looks up and passes cached `program_ast` to `evaluator.resume()`
- **`run_to_completion()` fix**: integration test helper now passes `program_ast` when calling `poller.cache_workflow_ast()`
- **`osm.geo.Operations.Cache` handler**: new `_cache_handler()` in `operations_handlers.py` resolves region names to Geofabrik paths via flat lookup built from `cache_handlers.REGION_REGISTRY`, with case-insensitive fallback; downloads PBF and returns `cache: OSMCache`
- **`osm.geo.Operations.Validation.*` handlers**: new `validation_handlers.py` with 5 handlers (`ValidateCache`, `ValidateGeometry`, `ValidateTags`, `ValidateBounds`, `ValidationSummary`) delegating to `osmose_verifier`; registered in `handlers/__init__.py` via `register_validation_handlers(poller)`
- **Unit test updates**: `test_agent_poller_extended.py` updated for `program_ast=None` keyword argument; new `test_resume_with_cached_program_ast` test
- 1121 unit tests, 29 integration tests passing

## Completed (v0.9.10) - GraphHopper 8.0 Config-File CLI
- **`_run_graphhopper_import()` rewrite**: GraphHopper 8.0 replaced `--datareader.file=` command-line flags with a YAML config file passed as a positional argument to the `import` subcommand; updated handler to generate a temporary config file with `datareader.file`, `graph.location`, `import.osm.ignored_highways`, and profile with `custom_model_files: []`
- **Profile-aware ignored highways**: motorized profiles (`car`, `motorcycle`, `truck`) ignore `footway,cycleway,path,pedestrian,steps`; non-motorized profiles (`bike`, `mtb`, `racingbike`) ignore `motorway,trunk`; other profiles (e.g. `foot`, `hike`) ignore nothing
- **`test_liechtenstein_city_routes` now passes**: full 9-step CityRouteMap pipeline (ResolveRegion → Cache → BuildGraph → ExtractPlaces → FindCities → BicycleRoutes → RenderMap → FormatGeoJSON → Visualization) completes end-to-end
- 1121 unit tests, 30 integration tests passing

## Completed (v0.10.0) - Automatic Dependency Resolution & Source Publishing
- **`afl/resolver.py`**: new module with `NamespaceIndex` (filesystem scanner mapping namespace names to `.afl` files), `MongoDBNamespaceResolver` (queries `afl_sources` collection), and `DependencyResolver` (iterative fixpoint loop: parse → find missing `use` namespaces → load from filesystem/MongoDB → merge → repeat until stable; max 100 iterations safety bound)
- **`afl/publisher.py`**: new module with `SourcePublisher` — publishes AFL source files to MongoDB `afl_sources` collection indexed by namespace name; parses source to extract namespace names, creates one `PublishedSource` document per namespace with SHA-256 checksum; supports versioning, force-overwrite, unpublish, and list operations
- **`AFLParser.parse_and_resolve()`**: new method that calls `parse_sources()` then runs `DependencyResolver`; automatically scans primary file's sibling directory plus configured `source_paths`; optionally queries MongoDB when `mongodb_resolve=True`
- **`ResolverConfig` dataclass**: added to `AFLConfig` with `source_paths` (colon-separated `AFL_RESOLVER_SOURCE_PATHS`), `auto_resolve` (`AFL_RESOLVER_AUTO_RESOLVE`), `mongodb_resolve` (`AFL_RESOLVER_MONGODB_RESOLVE`)
- **`PublishedSource` entity**: new dataclass in `afl/runtime/entities.py` with `uuid`, `namespace_name`, `source_text`, `namespaces_defined`, `version`, `published_at`, `origin`, `checksum`
- **MongoStore extensions**: `afl_sources` collection with `(namespace_name, version)` unique compound index and `namespaces_defined` multikey index; new methods `save_published_source()`, `get_source_by_namespace()`, `get_sources_by_namespaces()` (batch `$in`), `delete_published_source()`, `list_published_sources()`
- **CLI subcommands**: `afl compile` (default, backward-compatible) with new `--auto-resolve`, `--source-path PATH`, `--mongo-resolve` flags; `afl publish` subcommand with `--version`, `--force`, `--list`, `--unpublish` options
- **Qualified call resolution**: resolver scans `CallExpr` names (e.g. `osm.geo.Operations.Cache`) to extract candidate namespace prefixes, not just `use` statements; candidates are matched against the filesystem index so only real namespaces are loaded; enables `--auto-resolve` for files like `osmworkflows_composed.afl` that reference facets by fully-qualified names without `use` imports
- **OSM geocoder verified**: `afl compile --primary osmworkflows_composed.afl --auto-resolve` resolves 29 namespaces in 3 iterations from a single primary file
- **Backward compatibility**: bare `afl input.afl -o out.json` still works unchanged; subcommand routing treats non-subcommand first arguments as compile input
- 1159 tests passing

## Completed (v0.10.1) - Publish & Run-Workflow Scripts
- **`scripts/publish`**: bash script with inline Python that compiles AFL source and publishes to MongoDB; creates `FlowDefinition` (with AFL source in `compiled_sources`), `WorkflowDefinition` entries for each workflow found, and publishes namespaces to `afl_sources` via `SourcePublisher`; supports `--auto-resolve`, `--source-path` (repeatable), `--primary`/`--library` (repeatable), `--version`, `--config`
- **`scripts/run-workflow`**: bash script with inline Python for interactive or non-interactive workflow execution from MongoDB; `--list` prints a table of all workflows; interactive mode lists workflows with numbers and prompts for selection; extracts parameters with types and compile-time defaults from the workflow AST; prompts for each parameter showing type and default; smart value parsing (bool, int, float, JSON objects/arrays, string fallback); `--workflow NAME` and `--input JSON` flags for non-interactive use; `--flow-id` to select by flow; executes via `Evaluator.execute()` with full `program_ast`
- **`MongoStore.get_all_workflows()`**: new method returning workflows sorted by `date` descending with configurable limit, following existing `get_all_runners()` pattern
- **Runner workflow lookup fix**: `_find_workflow_in_program` and `_search_namespace_workflows` now search both `namespaces`/`workflows` keys (emitter format) and `declarations` (alternative AST format); previously qualified workflow names like `handlers.AddOneWorkflow` failed in distributed execution because the runner only checked `declarations` while the emitter outputs under `namespaces`
- 1159 tests passing; 457 OSM geocoder tests passing (including distributed)

## Completed (v0.10.2) - Registry Runner
- **`HandlerRegistration` dataclass**: new entity in `entities.py` mapping a qualified facet name to a Python module + entrypoint; fields: `facet_name` (primary key), `module_uri` (dotted path or `file://` URI), `entrypoint`, `version`, `checksum` (cache invalidation), `timeout_ms`, `requirements`, `metadata`, `created`, `updated`
- **`PersistenceAPI` extensions**: 4 new abstract methods — `save_handler_registration()` (upsert by facet_name), `get_handler_registration()`, `list_handler_registrations()`, `delete_handler_registration()`
- **`MemoryStore` implementation**: dict-backed CRUD with `clear()` support
- **`MongoStore` implementation**: `handler_registrations` collection with unique index on `facet_name`; `_handler_reg_to_doc()` / `_doc_to_handler_reg()` serialization helpers
- **`RegistryRunnerConfig` dataclass**: extends `AgentPollerConfig` pattern with `registry_refresh_interval_ms` (default 30s) for periodic re-read of handler registrations from persistence
- **`RegistryRunner` class**: universal runner that reads handler registrations from persistence, dynamically loads Python modules, caches them by `(module_uri, checksum)`, and dispatches event tasks — eliminates the need for per-facet microservices
  - `register_handler()`: convenience method to create and persist a `HandlerRegistration`
  - `_import_handler()`: supports dotted module paths (`importlib.import_module`) and `file://` URIs (`spec_from_file_location`); validates entrypoint is callable
  - `_load_handler()`: cache lookup by `(module_uri, checksum)`, imports on miss
  - `_refresh_registry()` / `_maybe_refresh_registry()`: periodic re-read of registered facet names from persistence
  - `_process_event()`: looks up `HandlerRegistration` → loads handler → dispatches (sync or async) → `continue_step` → `_resume_workflow` → mark task COMPLETED; graceful error handling for missing registrations, import failures, and handler exceptions
  - Full lifecycle: `start()` / `stop()` / `poll_once()`, server registration, heartbeat, AST caching — mirrors `AgentPoller` patterns
- **Exported** from `afl.runtime`: `HandlerRegistration`, `RegistryRunner`, `RegistryRunnerConfig`
- 25 new tests across 6 test classes: `TestHandlerRegistrationCRUD`, `TestDynamicModuleLoading`, `TestModuleCaching`, `TestRegistryRunnerPollOnce`, `TestRegistryRunnerLifecycle`, `TestRegistryRefresh`
- 1184 tests passing

## Completed (v0.10.3) - Dispatch Adapter Migration for RegistryRunner
- **`RegistryRunner._process_event` payload injection**: shallow-copies `task.data` before handler invocation; injects `payload["_facet_name"] = task.name` so dispatch entrypoints know which facet they are handling; injects `payload["_handler_metadata"]` when registration has non-empty metadata; 4 new tests
- **Dispatch adapter pattern**: all 27 handler modules (22 OSM + 5 genomics) now expose a `_DISPATCH` dict (mapping qualified facet names to handler callables), a `handle(payload)` entrypoint that routes via `payload["_facet_name"]`, and a `register_handlers(runner)` function that persists `HandlerRegistration` entries
  - **Factory-based modules** (park, amenity, filter, population, road, route, building, visualization, gtfs, zoom): `_build_dispatch()` iterates `*_FACETS` list at module load time
  - **Direct dict modules** (region, elevation, routing, osmose, validation, airquality, genomics core, genomics resolve, genomics operations): `_DISPATCH` built as a literal dict
  - **Complex modules** (cache, operations, poi, graphhopper, tiger, boundary, genomics cache, genomics index): custom `_build_dispatch()` over nested registries
- **`__init__.py` extensions**: both `examples/osm-geocoder/handlers/__init__.py` and `examples/genomics/handlers/__init__.py` gain `register_all_registry_handlers(runner)` — imports and calls each module's `register_handlers(runner)`; existing `register_all_handlers(poller)` unchanged for backward compatibility
- **Agent entry points**: `examples/osm-geocoder/agent.py` updated with dual-mode support — `AFL_USE_REGISTRY=1` uses `RegistryRunner`, default uses `AgentPoller`; new `examples/genomics/agent.py` with same dual-mode pattern
- **New tests**: `test_handler_dispatch_osm.py` (58 tests) and `test_handler_dispatch_genomics.py` (18 tests) verify `_DISPATCH` key counts, `handle()` dispatch, unknown-facet errors, and `register_handlers()` call counts; use `sys.modules` cleanup for cross-file isolation
- 1264 tests passing
