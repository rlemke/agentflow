"""Jenkins test event facet handlers.

Handles RunTests, CodeQuality, and SecurityScan event facets from the
jenkins.test namespace. Each handler simulates a testing/quality operation
with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "jenkins.test"


def _run_tests_handler(payload: dict) -> dict[str, Any]:
    """Run a test suite."""
    framework = payload.get("framework", "junit")
    suite = payload.get("suite", "unit")
    return {
        "report": {
            "total": 342,
            "passed": 335,
            "failed": 2,
            "skipped": 5,
            "duration_ms": 28000,
            "report_path": f"/var/jenkins/workspace/app/target/surefire-reports/{suite}-report.xml",
            "coverage_pct": 87.3,
        },
    }


def _code_quality_handler(payload: dict) -> dict[str, Any]:
    """Run a code quality analysis."""
    tool = payload.get("tool", "sonarqube")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    return {
        "report": {
            "tool": tool,
            "issues": 42,
            "critical": 0,
            "major": 5,
            "minor": 37,
            "report_path": f"{workspace}/target/sonar-report.json",
            "passed": True,
        },
    }


def _security_scan_handler(payload: dict) -> dict[str, Any]:
    """Run a security vulnerability scan."""
    scanner = payload.get("scanner", "trivy")
    threshold = payload.get("severity_threshold", "HIGH")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/app")
    return {
        "report": {
            "tool": scanner,
            "issues": 8,
            "critical": 0,
            "major": 2,
            "minor": 6,
            "report_path": f"{workspace}/target/security-report.json",
            "passed": True,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.RunTests": _run_tests_handler,
    f"{NAMESPACE}.CodeQuality": _code_quality_handler,
    f"{NAMESPACE}.SecurityScan": _security_scan_handler,
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


def register_test_handlers(poller) -> None:
    """Register all test event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered test handler: %s", fqn)
