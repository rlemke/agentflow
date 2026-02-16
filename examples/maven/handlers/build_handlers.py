"""Maven build event facet handlers.

Handles CompileProject, RunUnitTests, PackageArtifact, and GenerateJavadoc
event facets from the maven.build namespace. Each handler simulates a
Maven build operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "maven.build"


def _compile_handler(payload: dict) -> dict[str, Any]:
    """Compile a Maven project."""
    workspace = payload.get("workspace_path", "/home/user/project")
    goals = payload.get("goals", "clean compile")
    jdk = payload.get("jdk_version", "17")
    return {
        "result": {
            "artifact_path": f"{workspace}/target/classes",
            "build_tool": f"maven-3.9.6/jdk-{jdk}",
            "version": "1.0.0",
            "success": True,
            "duration_ms": 12000,
            "warnings": 2,
            "errors": 0,
        },
    }


def _run_unit_tests_handler(payload: dict) -> dict[str, Any]:
    """Run unit tests via Maven Surefire."""
    workspace = payload.get("workspace_path", "/home/user/project")
    parallel = payload.get("parallel", False)
    fork_count = payload.get("fork_count", 1)
    return {
        "report": {
            "total": 156,
            "passed": 152,
            "failed": 0,
            "skipped": 4,
            "duration_ms": 28000,
            "report_path": f"{workspace}/target/surefire-reports",
            "coverage_pct": 87.5,
        },
    }


def _package_handler(payload: dict) -> dict[str, Any]:
    """Package a Maven artifact."""
    workspace = payload.get("workspace_path", "/home/user/project")
    packaging = payload.get("packaging", "jar")
    classifier = payload.get("classifier", "")
    jar_name = "my-app-1.0.0"
    if classifier:
        jar_name += f"-{classifier}"
    return {
        "info": {
            "group_id": "com.example",
            "artifact_id": "my-app",
            "version": "1.0.0",
            "classifier": classifier,
            "packaging": packaging,
            "path": f"{workspace}/target/{jar_name}.{packaging}",
            "size_bytes": 524288,
            "checksum": "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
        },
    }


def _generate_javadoc_handler(payload: dict) -> dict[str, Any]:
    """Generate Javadoc documentation."""
    workspace = payload.get("workspace_path", "/home/user/project")
    output_dir = payload.get("output_dir", "target/site/apidocs")
    return {
        "result": {
            "artifact_path": f"{workspace}/{output_dir}",
            "build_tool": "maven-javadoc-plugin-3.6.3",
            "version": "1.0.0",
            "success": True,
            "duration_ms": 8000,
            "warnings": 5,
            "errors": 0,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.CompileProject": _compile_handler,
    f"{NAMESPACE}.RunUnitTests": _run_unit_tests_handler,
    f"{NAMESPACE}.PackageArtifact": _package_handler,
    f"{NAMESPACE}.GenerateJavadoc": _generate_javadoc_handler,
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


def register_build_handlers(poller) -> None:
    """Register all build event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered build handler: %s", fqn)
