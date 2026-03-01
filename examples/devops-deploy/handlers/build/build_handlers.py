"""Build handlers for the devops-deploy example."""

from __future__ import annotations

import os
from typing import Any

from handlers.shared.deploy_utils import analyze_deploy_risk, build_image, run_tests

NAMESPACE = "deploy.Build"


def handle_build_image(params: dict[str, Any]) -> dict[str, Any]:
    """Handle BuildImage event facet."""
    service = params.get("service", "")
    version = params.get("version", "")
    registry = params.get("registry", "gcr.io/myproject")

    result = build_image(service, version, registry)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Built {result['image_tag']} ({result['size_mb']} MB)"
        if callable(step_log):
            step_log(msg, "success")
        else:
            step_log.append({"message": msg, "level": "success"})

    return result


def handle_run_tests(params: dict[str, Any]) -> dict[str, Any]:
    """Handle RunTests event facet."""
    service = params.get("service", "")
    version = params.get("version", "")

    passed, total_tests, failed_count = run_tests(service, version)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Tests: {total_tests} total, {failed_count} failed"
        level = "success" if passed else "warning"
        if callable(step_log):
            step_log(msg, level)
        else:
            step_log.append({"message": msg, "level": level})

    return {"passed": passed, "total_tests": total_tests, "failed_count": failed_count}


def handle_analyze_deploy_risk(params: dict[str, Any]) -> dict[str, Any]:
    """Handle AnalyzeDeployRisk event facet."""
    service = params.get("service", "")
    version = params.get("version", "")
    environment = params.get("environment", "staging")
    change_size = params.get("change_size", 0)
    if isinstance(change_size, str):
        try:
            change_size = int(change_size)
        except ValueError:
            change_size = 0

    risk_level, risk_score, risk_factors = analyze_deploy_risk(
        service, version, environment, change_size
    )

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Risk: {risk_level} (score={risk_score})"
        if callable(step_log):
            step_log(msg, "info")
        else:
            step_log.append({"message": msg, "level": "info"})

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
    }


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.BuildImage": handle_build_image,
    f"{NAMESPACE}.RunTests": handle_run_tests,
    f"{NAMESPACE}.AnalyzeDeployRisk": handle_analyze_deploy_risk,
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


def register_build_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
