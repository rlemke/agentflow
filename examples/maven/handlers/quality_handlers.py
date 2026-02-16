"""Maven quality analysis event facet handlers.

Handles CheckstyleAnalysis and DependencyCheck event facets from the
maven.quality namespace. Each handler simulates a quality analysis
operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "maven.quality"


def _checkstyle_handler(payload: dict) -> dict[str, Any]:
    """Run Checkstyle analysis."""
    workspace = payload.get("workspace_path", "/home/user/project")
    config_file = payload.get("config_file", "checkstyle.xml")
    severity = payload.get("severity_threshold", "warning")
    return {
        "report": {
            "tool": f"checkstyle/{config_file}",
            "issues": 12,
            "critical": 0,
            "major": 3,
            "minor": 9,
            "report_path": f"{workspace}/target/checkstyle-result.xml",
            "passed": True,
        },
    }


def _dependency_check_handler(payload: dict) -> dict[str, Any]:
    """Run OWASP dependency check."""
    workspace = payload.get("workspace_path", "/home/user/project")
    fail_on_cvss = payload.get("fail_on_cvss", 7.0)
    return {
        "report": {
            "tool": "owasp-dependency-check",
            "issues": 5,
            "critical": 0,
            "major": 2,
            "minor": 3,
            "report_path": f"{workspace}/target/dependency-check-report.html",
            "passed": True,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.CheckstyleAnalysis": _checkstyle_handler,
    f"{NAMESPACE}.DependencyCheck": _dependency_check_handler,
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


def register_quality_handlers(poller) -> None:
    """Register all quality event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered quality handler: %s", fqn)
