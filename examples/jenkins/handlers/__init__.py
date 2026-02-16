"""Jenkins CI/CD pipeline handlers."""

from .scm_handlers import register_scm_handlers
from .build_handlers import register_build_handlers
from .test_handlers import register_test_handlers
from .artifact_handlers import register_artifact_handlers
from .deploy_handlers import register_deploy_handlers
from .notify_handlers import register_notify_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_scm_handlers",
    "register_build_handlers",
    "register_test_handlers",
    "register_artifact_handlers",
    "register_deploy_handlers",
    "register_notify_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all Jenkins event facet handlers with the given poller."""
    register_scm_handlers(poller)
    register_build_handlers(poller)
    register_test_handlers(poller)
    register_artifact_handlers(poller)
    register_deploy_handlers(poller)
    register_notify_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all Jenkins event facet handlers with a RegistryRunner."""
    from .scm_handlers import register_handlers as reg_scm
    from .build_handlers import register_handlers as reg_build
    from .test_handlers import register_handlers as reg_test
    from .artifact_handlers import register_handlers as reg_artifact
    from .deploy_handlers import register_handlers as reg_deploy
    from .notify_handlers import register_handlers as reg_notify

    reg_scm(runner)
    reg_build(runner)
    reg_test(runner)
    reg_artifact(runner)
    reg_deploy(runner)
    reg_notify(runner)
