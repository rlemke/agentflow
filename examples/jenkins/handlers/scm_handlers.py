"""Jenkins SCM event facet handlers.

Handles GitCheckout and GitMerge event facets from jenkins.scm namespace.
Each handler simulates a Jenkins SCM operation with realistic output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "jenkins.scm"


def _git_checkout_handler(payload: dict) -> dict[str, Any]:
    """Clone/checkout a git repository."""
    repo = payload.get("repo", "unknown")
    branch = payload.get("branch", "main")
    return {
        "info": {
            "repo": repo,
            "branch": branch,
            "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "commit_message": f"Latest commit on {branch}",
            "author": "jenkins-ci",
            "workspace_path": f"/var/jenkins/workspace/{repo.split('/')[-1]}",
            "clone_duration_ms": 4500,
        },
    }


def _git_merge_handler(payload: dict) -> dict[str, Any]:
    """Merge a source branch into a target branch."""
    source = payload.get("source_branch", "feature")
    target = payload.get("target_branch", "main")
    workspace = payload.get("workspace_path", "/var/jenkins/workspace/repo")
    return {
        "info": {
            "repo": workspace.split("/")[-1],
            "branch": target,
            "commit_sha": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            "commit_message": f"Merge {source} into {target}",
            "author": "jenkins-ci",
            "workspace_path": workspace,
            "clone_duration_ms": 0,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.GitCheckout": _git_checkout_handler,
    f"{NAMESPACE}.GitMerge": _git_merge_handler,
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


def register_scm_handlers(poller) -> None:
    """Register all SCM event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered SCM handler: %s", fqn)
