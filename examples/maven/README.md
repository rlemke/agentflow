# Maven Build Lifecycle Agent

A Maven build lifecycle agent demonstrating AFL's **mixin composition**, **composed facets**, **multiple andThen blocks**, **arithmetic expressions**, **statement-level andThen bodies**, the **MavenArtifactRunner** execution model, and **workflow-as-step orchestration** — running external JVM programs packaged as Maven artifacts alongside standard handler-based execution.

## What it does

This example demonstrates:
- **Maven build lifecycle** modeled as AFL event facets (resolve, compile, test, package, publish)
- **Mixin facets** for cross-cutting concerns (`with Retry()`, `with Timeout()`, `with Repository()`)
- **Implicit declarations** providing namespace-level defaults
- **Foreach iteration** for multi-module parallel builds
- **Tri-mode agent** supporting AgentPoller, RegistryRunner, and MavenArtifactRunner
- **MavenArtifactRunner** — JVM subprocess execution model (resolves Maven artifacts, launches `java -jar` subprocesses)
- **Maven plugin goal execution** — `RunMavenPlugin` event facet for running plugin goals within a workspace
- **Workflow-as-step orchestration** — composing workflows from sub-workflows (`BuildTestAndRun`, `PluginVerifyAndRun`)

### Mixin Composition Patterns

```afl
// Build with retry on compilation failure
build = maven.build.CompileProject(workspace_path = $.workspace_path,
    goals = "clean compile") with Retry(maxAttempts = 2, backoffSeconds = 60)

// Tests with timeout
tests = maven.build.RunUnitTests(workspace_path = $.workspace_path,
    parallel = true) with Timeout(minutes = 20)

// Deploy with repository mixin
deploy = maven.publish.DeployToRepository(artifact_path = pkg.info.path,
    repository_url = $.repository_url,
    group_id = $.group_id, artifact_id = $.artifact_id,
    version = $.version) with Repository(url = $.repository_url, type = "release")

// Foreach with per-module mixins
workflow MultiModuleBuild(...) => (...) andThen foreach mod in $.modules {
    build = maven.build.CompileProject(workspace_path = $.workspace_path,
        goals = "clean compile -pl " ++ $.mod.name) with Timeout(minutes = 20)
}
```

### Execution flow

1. A workflow (e.g., `BuildAndTest`) receives inputs like group ID, artifact ID, and workspace path
2. Each step creates an event task — the runtime pauses and waits for an agent
3. The agent picks up the task, processes it, and writes results back
4. Mixin facets (Retry, Timeout, Repository, etc.) are composed onto each step
5. The workflow resumes, feeds outputs to the next step, and eventually yields final results

## Pipelines

### Pipeline 1: BuildAndTest

Basic Maven lifecycle — resolve, compile, test, package.

```
ResolveDependencies  -->  CompileProject  -->  RunUnitTests  -->  PackageArtifact
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`
**Outputs**: `artifact_path`, `test_passed`, `test_total`, `build_version`

### Pipeline 2: ReleaseArtifact

Full release pipeline with retry and repository mixins.

```
ResolveDependencies  -->  CompileProject + Retry  -->  RunUnitTests + Timeout  -->  PackageArtifact  -->  DeployToRepository + Repository
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`, `repository_url`
**Outputs**: `deploy_url`, `published`, `test_passed`

### Pipeline 3: DependencyAudit

Quality pipeline — resolve and analyze dependencies, run quality checks.

```
ResolveDependencies  -->  AnalyzeDependencyTree  -->  [parallel] CheckstyleAnalysis | DependencyCheck
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`
**Outputs**: `total_dependencies`, `conflicts`, `quality_issues`, `security_issues`

### Pipeline 4: MultiModuleBuild

Parallel per-module builds using `andThen foreach`.

```
foreach module:
    CompileProject + Timeout  -->  RunUnitTests + Timeout + Retry  -->  PackageArtifact + Timeout
```

**Inputs**: `group_id`, `workspace_path`, `modules` (JSON array of `{name, test_suite, packaging}`)
**Outputs**: per-module `artifact_path`, `module_name`, `test_passed`

### Pipeline 5: RunArtifactPipeline

Resolve dependencies and run a Maven artifact as a JVM subprocess.

```
ResolveDependencies  -->  RunMavenArtifact + Timeout
```

**Inputs**: `group_id`, `artifact_id`, `version`, `step_id`, `workflow_id` (optional), `runner_id` (optional)
**Outputs**: `success`, `exit_code`, `duration_ms`

### Pipeline 6: BuildTestAndRun (workflow-as-step)

Orchestrates `BuildAndTest` and `RunArtifactPipeline` as sub-workflow steps.

```
BuildAndTest (sub-workflow)  -->  RunArtifactPipeline (sub-workflow)
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`, `step_id`
**Outputs**: `artifact_path`, `test_passed`, `run_success`, `run_exit_code`

### Pipeline 7: PluginVerifyAndRun (workflow-as-step)

Run checkstyle + spotbugs Maven plugin goals, then invoke `RunArtifactPipeline` as a sub-workflow.

```
RunMavenPlugin(checkstyle) + Timeout  -->  RunMavenPlugin(spotbugs) + Timeout  -->  RunArtifactPipeline (sub-workflow)
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`, `step_id`
**Outputs**: `checkstyle_success`, `spotbugs_success`, `run_success`, `run_exit_code`

### Pipeline 8: FullBuildPipeline (multiple andThen blocks)

Concurrent build and quality gate paths using **multiple andThen blocks**.

```
andThen block 0:  CompileAndTest (composed facet)
andThen block 1:  FullQualityGate (composed facet)
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`
**Outputs**: `artifact_path`, `test_passed`, `quality_issues`, `security_issues`, `total_issues`

### Pipeline 9: InstrumentedBuild (statement-level andThen + arithmetic)

Build pipeline with **statement-level andThen** on the deps step and **arithmetic** for duration aggregation.

```
ResolveDependencies andThen { DownloadArtifact }  -->  CompileProject + Retry  -->  RunUnitTests + Timeout  -->  PackageArtifact
```

**Inputs**: `group_id`, `artifact_id`, `version`, `workspace_path`
**Outputs**: `artifact_path`, `test_passed`, `total_duration_ms` (build + test duration)

## Prerequisites

```bash
# From the repo root
source .venv/bin/activate
pip install -e ".[dev]"
```

No additional dependencies are required — all handlers simulate Maven operations with realistic output structures.

## Running

### Compile check

```bash
# Check all AFL sources
for f in examples/maven/afl/*.afl; do
    afl "$f" --check && echo "OK: $f"
done

# Compile the workflows with all dependencies
afl --primary examples/maven/afl/maven_workflows.afl \
    --library examples/maven/afl/maven_types.afl \
    --library examples/maven/afl/maven_mixins.afl \
    --library examples/maven/afl/maven_resolve.afl \
    --library examples/maven/afl/maven_build.afl \
    --library examples/maven/afl/maven_publish.afl \
    --library examples/maven/afl/maven_quality.afl \
    --library examples/maven/afl/maven_runner.afl \
    --check
```

### AgentPoller mode (default)

```bash
PYTHONPATH=. python examples/maven/agent.py
```

### RegistryRunner mode (recommended for production)

```bash
AFL_USE_REGISTRY=1 PYTHONPATH=. python examples/maven/agent.py
```

### MavenArtifactRunner mode (JVM subprocess execution)

```bash
AFL_USE_MAVEN_RUNNER=1 PYTHONPATH=. python examples/maven/agent.py
```

With custom Maven repository and JDK:

```bash
AFL_USE_MAVEN_RUNNER=1 \
    AFL_MAVEN_REPOSITORY=https://nexus.example.com/repository/maven-public \
    AFL_JAVA_COMMAND=/usr/lib/jvm/java-17/bin/java \
    PYTHONPATH=. python examples/maven/agent.py
```

### With MongoDB persistence

```bash
AFL_MONGODB_URL=mongodb://localhost:27017 AFL_MONGODB_DATABASE=afl \
    PYTHONPATH=. python examples/maven/agent.py
```

### With topic filtering

```bash
AFL_USE_REGISTRY=1 AFL_RUNNER_TOPICS=maven.build,maven.publish \
    PYTHONPATH=. python examples/maven/agent.py
```

### Run tests

```bash
# Maven-specific tests
pytest tests/test_maven_compilation.py tests/test_handler_dispatch_maven.py tests/test_maven_runner.py -v

# Full suite
pytest tests/ -v
```

## Mixin Facets

| Facet | Parameters | Purpose |
|-------|-----------|---------|
| `Retry` | `maxAttempts` (default 3), `backoffSeconds` (default 30) | Retry failed operations with configurable backoff |
| `Timeout` | `minutes` (default 30) | Maximum execution time for an operation |
| `Repository` | `url`, `id` (default "central"), `type` (default "release") | Target Maven repository for publish/deploy |
| `Profile` | `name`, `active` (default true) | Maven build profile activation |
| `JvmArgs` | `args` (default "-Xmx512m") | JVM arguments for build process |
| `Settings` | `path` (default "~/.m2/settings.xml") | Custom settings.xml path |

### Implicit defaults

```afl
implicit defaultRetry = Retry(maxAttempts = 3, backoffSeconds = 30)
implicit defaultTimeout = Timeout(minutes = 30)
implicit defaultRepository = Repository(url = "https://repo1.maven.org/maven2", id = "central", type = "release")
```

## Handler modules

| Module | Namespace | Event Facets | Description |
|--------|-----------|--------------|-------------|
| `resolve_handlers.py` | `maven.resolve` | ResolveDependencies, DownloadArtifact, AnalyzeDependencyTree | Dependency resolution and artifact download |
| `build_handlers.py` | `maven.build` | CompileProject, RunUnitTests, PackageArtifact, GenerateJavadoc | Build lifecycle operations |
| `publish_handlers.py` | `maven.publish` | DeployToRepository, PublishSnapshot, PromoteRelease | Artifact publishing and deployment |
| `quality_handlers.py` | `maven.quality` | CheckstyleAnalysis, DependencyCheck | Code quality and security analysis |
| `runner_handlers.py` | `maven.runner` | RunMavenArtifact, RunMavenPlugin | JVM subprocess execution and Maven plugin goals |

## AFL source files

| File | Namespace | Description |
|------|-----------|-------------|
| `maven_types.afl` | `maven.types` | 9 schemas (ArtifactInfo, DependencyTree, BuildResult, TestReport, PublishResult, QualityReport, ProjectInfo, ExecutionResult, PluginExecutionResult) |
| `maven_mixins.afl` | `maven.mixins` | 6 mixin facets + 3 implicit defaults |
| `maven_resolve.afl` | `maven.resolve` | 3 dependency resolution event facets |
| `maven_build.afl` | `maven.build` | 4 build lifecycle event facets |
| `maven_publish.afl` | `maven.publish` | 3 publish/deploy event facets |
| `maven_quality.afl` | `maven.quality` | 2 quality analysis event facets |
| `maven_runner.afl` | `maven.runner` | 2 event facets for JVM execution (RunMavenArtifact, RunMavenPlugin) |
| `maven_workflows.afl` | `maven.workflows` | 5 workflow pipelines demonstrating mixin composition |
| `maven_orchestrator.afl` | `maven.orchestrator` | 2 orchestrator workflows using workflow-as-step (BuildTestAndRun, PluginVerifyAndRun) |
| `maven_composed.afl` | `maven.composed` | 2 composed facets with arithmetic (CompileAndTest, FullQualityGate) |
| `maven_pipelines.afl` | `maven.pipelines` | 2 pipeline workflows with multiple andThen blocks and statement-level andThen |
