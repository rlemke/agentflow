"""Maven publish/deploy event facet handlers.

Handles DeployToRepository, PublishSnapshot, and PromoteRelease event facets
from the maven.publish namespace. Each handler simulates a Maven publish
operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "maven.publish"


def _deploy_handler(payload: dict) -> dict[str, Any]:
    """Deploy an artifact to a Maven repository."""
    repository_url = payload.get("repository_url", "https://repo.example.com/releases")
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "my-app")
    version = payload.get("version", "1.0.0")
    return {
        "result": {
            "repository_url": repository_url,
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": version,
            "published": True,
            "snapshot": False,
            "deploy_duration_ms": 5200,
        },
    }


def _publish_snapshot_handler(payload: dict) -> dict[str, Any]:
    """Publish a snapshot artifact."""
    repository_url = payload.get("repository_url", "https://repo.example.com/snapshots")
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "my-app")
    version = payload.get("version", "1.0.0-SNAPSHOT")
    return {
        "result": {
            "repository_url": repository_url,
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": version,
            "published": True,
            "snapshot": True,
            "deploy_duration_ms": 3800,
        },
    }


def _promote_release_handler(payload: dict) -> dict[str, Any]:
    """Promote a staging artifact to release."""
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "my-app")
    staging_version = payload.get("staging_version", "1.0.0-RC1")
    release_version = payload.get("release_version", "1.0.0")
    repository_url = payload.get("repository_url", "https://repo.example.com/releases")
    return {
        "result": {
            "repository_url": repository_url,
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": release_version,
            "published": True,
            "snapshot": False,
            "deploy_duration_ms": 7500,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.DeployToRepository": _deploy_handler,
    f"{NAMESPACE}.PublishSnapshot": _publish_snapshot_handler,
    f"{NAMESPACE}.PromoteRelease": _promote_release_handler,
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


def register_publish_handlers(poller) -> None:
    """Register all publish event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered publish handler: %s", fqn)
