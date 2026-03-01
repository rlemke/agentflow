"""Deploy handlers for the devops-deploy example."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.deploy_utils import apply_deployment, normalize_config, wait_for_rollout

NAMESPACE = "deploy.Deploy"


def handle_normalize_config(params: dict[str, Any]) -> dict[str, Any]:
    """Handle NormalizeConfig event facet."""
    service = params.get("service", "")
    environment = params.get("environment", "staging")
    replicas = params.get("replicas", 2)
    if isinstance(replicas, str):
        try:
            replicas = int(replicas)
        except ValueError:
            replicas = 2
    cpu_limit = params.get("cpu_limit", "500m")
    memory_limit = params.get("memory_limit", "512Mi")

    config = normalize_config(service, environment, replicas, cpu_limit, memory_limit)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Config normalized for {config['namespace']}/{service}"
        if callable(step_log):
            step_log(msg, "success")
        else:
            step_log.append({"message": msg, "level": "success"})

    return {"config": config}


def handle_apply_deployment(params: dict[str, Any]) -> dict[str, Any]:
    """Handle ApplyDeployment event facet."""
    service = params.get("service", "")
    image_tag = params.get("image_tag", "")
    config = params.get("config", {})
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (json.JSONDecodeError, ValueError):
            config = {}

    deployment_id, status = apply_deployment(service, image_tag, config)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Applied deployment {deployment_id}: {status}"
        if callable(step_log):
            step_log(msg, "success")
        else:
            step_log.append({"message": msg, "level": "success"})

    return {"deployment_id": deployment_id, "status": status}


def handle_wait_for_rollout(params: dict[str, Any]) -> dict[str, Any]:
    """Handle WaitForRollout event facet."""
    deployment_id = params.get("deployment_id", "")
    timeout_seconds = params.get("timeout_seconds", 300)
    if isinstance(timeout_seconds, str):
        try:
            timeout_seconds = int(timeout_seconds)
        except ValueError:
            timeout_seconds = 300

    ready, ready_replicas, message = wait_for_rollout(deployment_id, timeout_seconds)

    step_log = params.get("_step_log")
    if step_log is not None:
        if callable(step_log):
            step_log(message, "success" if ready else "warning")
        else:
            step_log.append({"message": message, "level": "success" if ready else "warning"})

    return {"ready": ready, "ready_replicas": ready_replicas, "message": message}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.NormalizeConfig": handle_normalize_config,
    f"{NAMESPACE}.ApplyDeployment": handle_apply_deployment,
    f"{NAMESPACE}.WaitForRollout": handle_wait_for_rollout,
}


def handle(payload: dict) -> dict:
    """RegistryRunner entrypoint."""
    facet = payload["_facet_name"]
    handler = _DISPATCH[facet]
    return handler(payload)


def register_handlers(runner) -> None:
    """Register with RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_deploy_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
