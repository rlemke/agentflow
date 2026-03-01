"""Rollback handlers for the devops-deploy example."""

from __future__ import annotations

import os
from typing import Any

from handlers.shared.deploy_utils import rollback_deployment, verify_rollback

NAMESPACE = "deploy.Rollback"


def handle_rollback_deployment(params: dict[str, Any]) -> dict[str, Any]:
    """Handle RollbackDeployment event facet."""
    service = params.get("service", "")
    deployment_id = params.get("deployment_id", "")
    reason = params.get("reason", "")

    report = rollback_deployment(service, deployment_id, reason)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Rolled back {service}: {report['rollback_id']}"
        if callable(step_log):
            step_log(msg, "warning")
        else:
            step_log.append({"message": msg, "level": "warning"})

    return {"report": report}


def handle_verify_rollback(params: dict[str, Any]) -> dict[str, Any]:
    """Handle VerifyRollback event facet."""
    service = params.get("service", "")
    rollback_id = params.get("rollback_id", "")

    verified, message = verify_rollback(service, rollback_id)

    step_log = params.get("_step_log")
    if step_log is not None:
        if callable(step_log):
            step_log(message, "success" if verified else "error")
        else:
            step_log.append({"message": message, "level": "success" if verified else "error"})

    return {"verified": verified, "message": message}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.RollbackDeployment": handle_rollback_deployment,
    f"{NAMESPACE}.VerifyRollback": handle_verify_rollback,
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


def register_rollback_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
