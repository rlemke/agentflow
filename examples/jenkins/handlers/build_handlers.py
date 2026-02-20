"""Jenkins build event facet handlers.

Handles MavenBuild, GradleBuild, NpmBuild, and DockerBuild event facets
from the jenkins.build namespace. Each handler simulates a build operation
with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "jenkins.build"


def _maven_build_handler(payload: dict) -> dict[str, Any]:
    """Run a Maven build."""
    step_log = payload.get("_step_log")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    goals = payload.get("goals", "clean package")
    if step_log:
        step_log(f"MavenBuild: {goals} in {workspace}")
    jdk = payload.get("jdk_version", "17")
    return {
        "result": {
            "artifact_path": f"{workspace}/target/app-1.0.0.jar",
            "build_tool": f"maven-3.9.6/jdk-{jdk}",
            "version": "1.0.0",
            "success": True,
            "duration_ms": 45000,
            "warnings": 3,
            "errors": 0,
        },
    }


def _gradle_build_handler(payload: dict) -> dict[str, Any]:
    """Run a Gradle build."""
    step_log = payload.get("_step_log")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    tasks = payload.get("tasks", "build")
    if step_log:
        step_log(f"GradleBuild: {tasks} in {workspace}")
    jdk = payload.get("jdk_version", "17")
    return {
        "result": {
            "artifact_path": f"{workspace}/build/libs/app-1.0.0.jar",
            "build_tool": f"gradle-8.5/jdk-{jdk}",
            "version": "1.0.0",
            "success": True,
            "duration_ms": 38000,
            "warnings": 1,
            "errors": 0,
        },
    }


def _npm_build_handler(payload: dict) -> dict[str, Any]:
    """Run an npm build."""
    step_log = payload.get("_step_log")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    script = payload.get("build_script", "build")
    if step_log:
        step_log(f"NpmBuild: {script} in {workspace}")
    node_version = payload.get("node_version", "20")
    return {
        "result": {
            "artifact_path": f"{workspace}/dist",
            "build_tool": f"npm-10.2.0/node-{node_version}",
            "version": "1.0.0",
            "success": True,
            "duration_ms": 22000,
            "warnings": 0,
            "errors": 0,
        },
    }


def _docker_build_handler(payload: dict) -> dict[str, Any]:
    """Build a Docker image."""
    step_log = payload.get("_step_log")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    image_tag = payload.get("image_tag", "app:latest")
    if step_log:
        step_log(f"DockerBuild: {image_tag}")
    dockerfile = payload.get("dockerfile", "Dockerfile")
    return {
        "result": {
            "artifact_path": f"docker://{image_tag}",
            "build_tool": "docker-24.0.7",
            "version": image_tag.split(":")[-1] if ":" in image_tag else "latest",
            "success": True,
            "duration_ms": 60000,
            "warnings": 0,
            "errors": 0,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.MavenBuild": _maven_build_handler,
    f"{NAMESPACE}.GradleBuild": _gradle_build_handler,
    f"{NAMESPACE}.NpmBuild": _npm_build_handler,
    f"{NAMESPACE}.DockerBuild": _docker_build_handler,
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


def register_build_handlers(poller) -> None:
    """Register all build event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered build handler: %s", fqn)
