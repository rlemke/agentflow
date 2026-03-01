"""Monitor handlers for the devops-deploy example."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.deploy_utils import check_health, triage_incident

NAMESPACE = "deploy.Monitor"


def handle_check_health(params: dict[str, Any]) -> dict[str, Any]:
    """Handle CheckHealth event facet."""
    service = params.get("service", "")
    deployment_id = params.get("deployment_id", "")
    checks = params.get("checks", ["readiness", "liveness", "connectivity"])
    if isinstance(checks, str):
        try:
            checks = json.loads(checks)
        except (json.JSONDecodeError, ValueError):
            checks = ["readiness", "liveness", "connectivity"]

    healthy, results = check_health(service, deployment_id, checks)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Health check: {'healthy' if healthy else 'unhealthy'}"
        if callable(step_log):
            step_log(msg, "success" if healthy else "warning")
        else:
            step_log.append({"message": msg, "level": "success" if healthy else "warning"})

    return {
        "result": {
            "healthy": healthy,
            "results": results,
            "checks_run": len(checks),
        }
    }


def handle_triage_incident(params: dict[str, Any]) -> dict[str, Any]:
    """Handle TriageIncident event facet."""
    service = params.get("service", "")
    health_results = params.get("health_results", {})
    if isinstance(health_results, str):
        try:
            health_results = json.loads(health_results)
        except (json.JSONDecodeError, ValueError):
            health_results = {}
    deployment_id = params.get("deployment_id", "")

    severity, recommendation, failed_checks = triage_incident(
        service, health_results, deployment_id
    )

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Triage: {severity} — {recommendation}"
        if callable(step_log):
            step_log(msg, "warning")
        else:
            step_log.append({"message": msg, "level": "warning"})

    return {
        "severity": severity,
        "recommendation": recommendation,
        "failed_checks": failed_checks,
    }


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.CheckHealth": handle_check_health,
    f"{NAMESPACE}.TriageIncident": handle_triage_incident,
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


def register_monitor_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
