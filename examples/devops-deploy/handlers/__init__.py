"""Handler registration for the devops-deploy example."""

from __future__ import annotations

from .build.build_handlers import register_build_handlers
from .deploy.deploy_handlers import register_deploy_handlers
from .monitor.monitor_handlers import register_monitor_handlers
from .rollback.rollback_handlers import register_rollback_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_build_handlers(poller)
    register_deploy_handlers(poller)
    register_monitor_handlers(poller)
    register_rollback_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .build.build_handlers import register_handlers as reg_build
    from .deploy.deploy_handlers import register_handlers as reg_deploy
    from .monitor.monitor_handlers import register_handlers as reg_monitor
    from .rollback.rollback_handlers import register_handlers as reg_rollback

    reg_build(runner)
    reg_deploy(runner)
    reg_monitor(runner)
    reg_rollback(runner)
