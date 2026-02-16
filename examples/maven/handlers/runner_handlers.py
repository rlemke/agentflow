"""Maven artifact runner event facet handlers.

Handles the RunMavenArtifact event facet from the maven.runner namespace.
Simulates resolving a Maven artifact and launching it as a JVM subprocess.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "maven.runner"


def _run_maven_artifact_handler(payload: dict) -> dict[str, Any]:
    """Simulate running a Maven artifact as a JVM subprocess."""
    step_id = payload.get("step_id", "unknown")
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "app")
    version = payload.get("version", "1.0.0")
    classifier = payload.get("classifier", "")
    entrypoint = payload.get("entrypoint", "")
    jvm_args = payload.get("jvm_args", "")

    group_path = group_id.replace(".", "/")
    jar_name = f"{artifact_id}-{version}"
    if classifier:
        jar_name += f"-{classifier}"
    jar_name += ".jar"
    artifact_path = f"/tmp/maven-cache/{group_path}/{artifact_id}/{version}/{jar_name}"

    cmd = "java"
    if jvm_args:
        cmd += f" {jvm_args}"
    if entrypoint:
        cmd += f" -cp {artifact_path} {entrypoint} {step_id}"
    else:
        cmd += f" -jar {artifact_path} {step_id}"

    return {
        "result": {
            "exit_code": 0,
            "success": True,
            "duration_ms": 1250,
            "stdout": f"[{artifact_id}] Step {step_id} completed successfully",
            "stderr": "",
            "artifact_path": artifact_path,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.RunMavenArtifact": _run_maven_artifact_handler,
}


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_runner_handlers(poller) -> None:
    """Register all runner event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered runner handler: %s", fqn)
