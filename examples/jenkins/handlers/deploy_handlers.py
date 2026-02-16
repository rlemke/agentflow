"""Jenkins deploy event facet handlers.

Handles DeployToEnvironment, DeployToK8s, and RollbackDeploy event facets
from the jenkins.deploy namespace. Each handler simulates a deployment
operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "jenkins.deploy"


def _deploy_to_environment_handler(payload: dict) -> dict[str, Any]:
    """Deploy an artifact to a target environment."""
    environment = payload.get("environment", "staging")
    strategy = payload.get("strategy", "rolling")
    version = payload.get("version", "1.0.0")
    return {
        "result": {
            "environment": environment,
            "strategy": strategy,
            "version": version,
            "url": f"https://{environment}.example.com",
            "replicas": 3,
            "healthy": True,
            "deploy_id": f"deploy-{environment}-{version}-001",
        },
    }


def _deploy_to_k8s_handler(payload: dict) -> dict[str, Any]:
    """Deploy to a Kubernetes cluster."""
    namespace = payload.get("k8s_namespace", "default")
    cluster = payload.get("cluster", "default")
    replicas = payload.get("replicas", 2)
    image_tag = payload.get("image_tag", "app:latest")
    return {
        "result": {
            "environment": f"k8s/{cluster}/{namespace}",
            "strategy": "rolling",
            "version": image_tag.split(":")[-1] if ":" in image_tag else "latest",
            "url": f"https://{namespace}.{cluster}.k8s.example.com",
            "replicas": replicas,
            "healthy": True,
            "deploy_id": f"k8s-{cluster}-{namespace}-001",
        },
    }


def _rollback_deploy_handler(payload: dict) -> dict[str, Any]:
    """Roll back a deployment."""
    deploy_id = payload.get("deploy_id", "deploy-unknown-001")
    environment = payload.get("environment", "staging")
    return {
        "result": {
            "environment": environment,
            "strategy": "rollback",
            "version": "previous",
            "url": f"https://{environment}.example.com",
            "replicas": 3,
            "healthy": True,
            "deploy_id": f"{deploy_id}-rollback",
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.DeployToEnvironment": _deploy_to_environment_handler,
    f"{NAMESPACE}.DeployToK8s": _deploy_to_k8s_handler,
    f"{NAMESPACE}.RollbackDeploy": _rollback_deploy_handler,
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


def register_deploy_handlers(poller) -> None:
    """Register all deploy event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered deploy handler: %s", fqn)
