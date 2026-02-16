# Maven Build Lifecycle — User Guide

> See also: [README](README.md)

## When to Use This Example

Use this as your starting point if you are:
- Modeling a **Maven build lifecycle** (resolve, compile, test, package, publish)
- Learning AFL's **mixin composition** pattern (`with Retry()`, `with Repository()`)
- Exploring the **MavenArtifactRunner** execution model — running JVM programs as Maven artifacts
- Building workflows where **reusable behaviors** need to be attached flexibly per-step
- Designing **multi-module builds** with `andThen foreach`

## What You'll Learn

1. How to model Maven build lifecycle stages as AFL event facets
2. How mixin facets define reusable cross-cutting behaviors
3. How to attach mixins at **call time** (per-step) with `with`
4. How `implicit` declarations provide namespace-level defaults
5. How to combine foreach iteration with per-iteration mixins
6. How the **MavenArtifactRunner** resolves Maven artifacts and launches JVM subprocesses
7. How to **encapsulate complex pipelines** behind simple composed facets

## Step-by-Step Walkthrough

### 1. Define Schemas

All return types are schemas defined in a namespace:

```afl
namespace maven.types {
    schema ArtifactInfo {
        group_id: String,
        artifact_id: String,
        version: String,
        classifier: String,
        packaging: String,
        path: String,
        size_bytes: Long,
        checksum: String
    }

    schema BuildResult {
        artifact_path: String,
        build_tool: String,
        version: String,
        success: Boolean,
        duration_ms: Long,
        warnings: Long,
        errors: Long
    }
    // ... more schemas
}
```

### 2. Define Mixin Facets

Mixins are regular facets (not event facets) that represent cross-cutting concerns:

```afl
namespace maven.mixins {
    facet Retry(maxAttempts: Int = 3, backoffSeconds: Int = 30)
    facet Timeout(minutes: Int = 30)
    facet Repository(url: String, id: String = "central", type: String = "release")
    facet Profile(name: String, active: Boolean = true)
    facet JvmArgs(args: String = "-Xmx512m")
    facet Settings(path: String = "~/.m2/settings.xml")
}
```

These carry configuration data — the runtime and agent can inspect them when processing a step.

### 3. Define Event Facets

Event facets represent operations that agents execute:

```afl
namespace maven.build {
    use maven.types

    event facet CompileProject(workspace_path: String,
        goals: String = "clean compile",
        jdk_version: String = "17",
        skip_tests: Boolean = true) => (result: BuildResult)

    event facet RunUnitTests(workspace_path: String,
        test_suite: String = "**/*Test.java",
        parallel: Boolean = false,
        fork_count: Int = 1) => (report: TestReport)
}
```

### 4. Attach Mixins at Call Time

Add one or more mixins to any step:

```afl
// Build with retry
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
```

**Grammar rule**: The `) with` must be on the same line as the closing `)`. Newlines between `)` and `with` cause parse errors.

### 5. Define Implicit Defaults

Set namespace-wide default values:

```afl
implicit defaultRetry = Retry(maxAttempts = 3, backoffSeconds = 30)
implicit defaultTimeout = Timeout(minutes = 30)
implicit defaultRepository = Repository(url = "https://repo1.maven.org/maven2", id = "central", type = "release")
```

### 6. Combine with foreach

Attach mixins to steps inside foreach iteration:

```afl
workflow MultiModuleBuild(group_id: String,
    workspace_path: String,
    modules: Json) => (...) andThen foreach mod in $.modules {

    build = maven.build.CompileProject(workspace_path = $.workspace_path,
        goals = "clean compile -pl " ++ $.mod.name) with Timeout(minutes = 20)

    tests = maven.build.RunUnitTests(workspace_path = $.workspace_path,
        test_suite = $.mod.test_suite) with Timeout(minutes = 15) with Retry(maxAttempts = 2)

    yield MultiModuleBuild(...)
}
```

Note: Mixin arguments can use dynamic expressions like `"clean compile -pl " ++ $.mod.name`.

### 7. Run Maven Artifacts

The `RunMavenArtifact` event facet models the core MavenArtifactRunner operation — resolving a Maven artifact and launching it as a JVM subprocess:

```afl
namespace maven.runner {
    use maven.types

    event facet RunMavenArtifact(step_id: String,
        group_id: String, artifact_id: String, version: String,
        classifier: String = "",
        entrypoint: String = "",
        jvm_args: String = "",
        workflow_id: String = "",
        runner_id: String = "") => (result: ExecutionResult)
}
```

Use it in workflows to resolve dependencies and then run the artifact:

```afl
run = maven.runner.RunMavenArtifact(step_id = $.step_id,
    group_id = $.group_id, artifact_id = $.artifact_id,
    version = $.version) with Timeout(minutes = 10)
```

### 8. Running

```bash
source .venv/bin/activate
pip install -e ".[dev]"

# Compile check
for f in examples/maven/afl/*.afl; do
    python -m afl.cli "$f" --check && echo "OK: $f"
done

# Compile workflows with all dependencies
python -m afl.cli \
    --primary examples/maven/afl/maven_workflows.afl \
    --library examples/maven/afl/maven_types.afl \
    --library examples/maven/afl/maven_mixins.afl \
    --library examples/maven/afl/maven_resolve.afl \
    --library examples/maven/afl/maven_build.afl \
    --library examples/maven/afl/maven_publish.afl \
    --library examples/maven/afl/maven_quality.afl \
    --library examples/maven/afl/maven_runner.afl \
    --check

# Run the agent (AgentPoller mode)
PYTHONPATH=. python examples/maven/agent.py

# Run the agent (MavenArtifactRunner mode)
AFL_USE_MAVEN_RUNNER=1 PYTHONPATH=. python examples/maven/agent.py
```

## Key Concepts

### MavenArtifactRunner Execution Model

The MavenArtifactRunner is a unique execution model in this example that bridges AFL workflows with JVM programs:

1. **Handler registration** — Register event facets with `mvn:` URI schemes:
   ```python
   runner.register_handler(
       facet_name="maven.build.CompileProject",
       module_uri="mvn:com.example:maven-compiler:1.0.0",
   )
   ```

2. **Artifact resolution** — When a task arrives, the runner parses the `mvn:groupId:artifactId:version[:classifier]` URI, downloads the JAR from the configured Maven repository (or uses the local cache), and stores it at `{cache_dir}/{groupPath}/{artifactId}/{version}/{name}.jar`.

3. **JVM subprocess** — The runner launches:
   - `java -jar artifact.jar <stepId>` (executable JAR)
   - `java -cp artifact.jar MainClass <stepId>` (with entrypoint)
   - JVM args from `metadata["jvm_args"]` are prepended
   - Environment variables: `AFL_STEP_ID`, `AFL_MONGODB_URL`, `AFL_MONGODB_DATABASE`

4. **Step continuation** — After the JVM program exits successfully (exit 0), the runner reads return values from MongoDB and calls `evaluator.continue_step()` + `evaluator.resume()` to advance the workflow.

This model is ideal when your event facet handlers are implemented in Java/Scala/Kotlin and packaged as Maven artifacts.

### Facet Encapsulation — Hiding Pipeline Complexity

Wrap complex pipelines in composed facets that bake in mixins:

```afl
namespace maven.library {
    use maven.types
    use maven.mixins

    // Composed facet: encapsulates resolve + compile + test with mixins baked in
    facet BuildAndVerify(group_id: String, artifact_id: String,
        version: String,
        workspace_path: String) => (artifact_path: String,
            test_passed: Long) andThen {

        deps = maven.resolve.ResolveDependencies(group_id = $.group_id,
            artifact_id = $.artifact_id, version = $.version)

        build = maven.build.CompileProject(workspace_path = $.workspace_path) with Retry(maxAttempts = 2)

        tests = maven.build.RunUnitTests(workspace_path = $.workspace_path) with Timeout(minutes = 20)

        pkg = maven.build.PackageArtifact(workspace_path = $.workspace_path)

        yield BuildAndVerify(
            artifact_path = pkg.info.path,
            test_passed = tests.report.passed)
    }
}
```

| Layer | What the User Sees | What's Hidden |
|-------|-------------------|---------------|
| Event facets | `CompileProject`, `RunUnitTests`, `PackageArtifact` | Handler implementations |
| Composed facets | `BuildAndVerify(group_id, workspace_path)` | Retry policies, timeout values, step ordering |
| Workflows | `ReleaseArtifact(group_id, version, repo_url)` | The entire pipeline structure |

### Handler Dispatch Pattern

Each handler module follows the same dispatch adapter:

```python
NAMESPACE = "maven.build"

_DISPATCH = {
    f"{NAMESPACE}.CompileProject": _compile_handler,
    f"{NAMESPACE}.RunUnitTests": _run_unit_tests_handler,
    # ...
}

def handle(payload: dict) -> dict:
    handler = _DISPATCH[payload["_facet_name"]]
    return handler(payload)
```

Handlers are pure functions: receive a payload dict, return a result dict. The mixin data is available in the payload for handlers that need to inspect it.

### AFL Grammar Constraints

These are critical when writing AFL with mixins:

1. **`) with` on same line**: `step = F(x = 1) with M()` — no newline between `)` and `with`
2. **`) =>` on same line**: `event facet F(x: String) => (y: String)` — no newline between `)` and `=>`
3. **Return before mixin in signature**: `=> (result: Type) with M()` — return clause first
4. **Reserved keywords**: `script` and `namespace` cannot be used as parameter names

## Adapting for Your Use Case

### Add a new build lifecycle stage

1. Define the event facet in `afl/maven_build.afl` (or a new namespace file)
2. Add a handler function in `handlers/build_handlers.py` and wire it into `_DISPATCH`
3. Update the workflow in `afl/maven_workflows.afl` to include the new step
4. Add tests

### Use the MavenArtifactRunner with real JVM handlers

1. Package your Java handler as an executable JAR
2. Publish it to a Maven repository (local Nexus, Artifactory, or Maven Central)
3. Register it with the runner:
   ```python
   runner.register_handler(
       facet_name="maven.build.CompileProject",
       module_uri="mvn:com.mycompany:maven-compile-handler:1.0.0",
       metadata={"jvm_args": ["-Xmx1g"]},
   )
   ```
4. Set `AFL_USE_MAVEN_RUNNER=1` and run the agent

### Add a new handler module

1. Create `handlers/my_handlers.py` with `NAMESPACE`, `_DISPATCH`, `handle()`, `register_handlers()`, and `register_my_handlers()`
2. Wire it into `handlers/__init__.py`
3. Add the corresponding AFL event facet file

## Next Steps

- **[jenkins](../jenkins/USER_GUIDE.md)** — see the original mixin composition example with Jenkins CI/CD
- **[aws-lambda](../aws-lambda/USER_GUIDE.md)** — combine mixins with real cloud API calls
- **[genomics](../genomics/USER_GUIDE.md)** — foreach fan-out patterns for parallel processing
