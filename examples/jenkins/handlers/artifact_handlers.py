"""Jenkins artifact event facet handlers.

Handles ArchiveArtifacts, PublishToRegistry, and DockerPush event facets
from the jenkins.artifact namespace. Each handler simulates an artifact
operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "jenkins.artifact"


def _archive_artifacts_handler(payload: dict) -> dict[str, Any]:
    """Archive build artifacts."""
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    includes = payload.get("includes", "**/*.jar")
    return {
        "artifact": {
            "name": "app-1.0.0.jar",
            "path": f"{workspace}/target/app-1.0.0.jar",
            "size_bytes": 15_728_640,
            "checksum": "sha256:a1b2c3d4e5f6789012345678abcdef0123456789",
            "registry_url": "",
            "tag": "1.0.0",
        },
    }


def _publish_to_registry_handler(payload: dict) -> dict[str, Any]:
    """Publish an artifact to a registry (Maven, npm, etc.)."""
    registry_url = payload.get("registry_url", "https://registry.example.com")
    version = payload.get("version", "1.0.0")
    group_id = payload.get("group_id", "com.example")
    return {
        "artifact": {
            "name": f"{group_id}:app",
            "path": payload.get("artifact_path", "/target/app.jar"),
            "size_bytes": 15_728_640,
            "checksum": "sha256:b2c3d4e5f6789012345678abcdef0123456789ab",
            "registry_url": f"{registry_url}/{group_id.replace('.', '/')}/app/{version}",
            "tag": version,
        },
    }


def _docker_push_handler(payload: dict) -> dict[str, Any]:
    """Push a Docker image to a container registry."""
    image_tag = payload.get("image_tag", "app:latest")
    registry_url = payload.get("registry_url", "registry.example.com")
    tag = image_tag.split(":")[-1] if ":" in image_tag else "latest"
    image_name = image_tag.split(":")[0]
    return {
        "artifact": {
            "name": image_name,
            "path": f"{registry_url}/{image_tag}",
            "size_bytes": 256_000_000,
            "checksum": "sha256:c3d4e5f6789012345678abcdef0123456789abcd",
            "registry_url": f"{registry_url}/{image_name}",
            "tag": tag,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.ArchiveArtifacts": _archive_artifacts_handler,
    f"{NAMESPACE}.PublishToRegistry": _publish_to_registry_handler,
    f"{NAMESPACE}.DockerPush": _docker_push_handler,
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


def register_artifact_handlers(poller) -> None:
    """Register all artifact event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered artifact handler: %s", fqn)
