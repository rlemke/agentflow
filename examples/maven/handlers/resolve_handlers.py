"""Maven dependency resolution event facet handlers.

Handles ResolveDependencies, DownloadArtifact, and AnalyzeDependencyTree
event facets from the maven.resolve namespace. Each handler simulates
a Maven dependency operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "maven.resolve"


def _resolve_dependencies_handler(payload: dict) -> dict[str, Any]:
    """Resolve Maven dependencies for a project."""
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "my-app")
    version = payload.get("version", "1.0.0")
    scope = payload.get("scope", "compile")
    return {
        "info": {
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": version,
            "classifier": "",
            "packaging": "jar",
            "path": f"/home/user/.m2/repository/{group_id.replace('.', '/')}/{artifact_id}/{version}/{artifact_id}-{version}.jar",
            "size_bytes": 245760,
            "checksum": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        },
    }


def _download_artifact_handler(payload: dict) -> dict[str, Any]:
    """Download a specific Maven artifact."""
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "my-lib")
    version = payload.get("version", "1.0.0")
    classifier = payload.get("classifier", "")
    jar_name = f"{artifact_id}-{version}"
    if classifier:
        jar_name += f"-{classifier}"
    return {
        "info": {
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": version,
            "classifier": classifier,
            "packaging": "jar",
            "path": f"/home/user/.m2/repository/{group_id.replace('.', '/')}/{artifact_id}/{version}/{jar_name}.jar",
            "size_bytes": 102400,
            "checksum": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
        },
    }


def _analyze_dependency_tree_handler(payload: dict) -> dict[str, Any]:
    """Analyze the full dependency tree."""
    group_id = payload.get("group_id", "com.example")
    artifact_id = payload.get("artifact_id", "my-app")
    version = payload.get("version", "1.0.0")
    return {
        "tree": {
            "root_artifact": f"{group_id}:{artifact_id}:{version}",
            "total_dependencies": 42,
            "direct_dependencies": 8,
            "transitive": 34,
            "conflicts": 2,
            "tree_output": f"{group_id}:{artifact_id}:jar:{version}\n+- org.slf4j:slf4j-api:jar:2.0.9\n+- com.google.guava:guava:jar:32.1.3-jre",
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.ResolveDependencies": _resolve_dependencies_handler,
    f"{NAMESPACE}.DownloadArtifact": _download_artifact_handler,
    f"{NAMESPACE}.AnalyzeDependencyTree": _analyze_dependency_tree_handler,
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


def register_resolve_handlers(poller) -> None:
    """Register all resolve event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered resolve handler: %s", fqn)
