"""Maven build lifecycle handlers."""

from .resolve_handlers import register_resolve_handlers
from .build_handlers import register_build_handlers
from .publish_handlers import register_publish_handlers
from .quality_handlers import register_quality_handlers
from .runner_handlers import register_runner_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_resolve_handlers",
    "register_build_handlers",
    "register_publish_handlers",
    "register_quality_handlers",
    "register_runner_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all Maven event facet handlers with the given poller."""
    register_resolve_handlers(poller)
    register_build_handlers(poller)
    register_publish_handlers(poller)
    register_quality_handlers(poller)
    register_runner_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all Maven event facet handlers with a RegistryRunner."""
    from .resolve_handlers import register_handlers as reg_resolve
    from .build_handlers import register_handlers as reg_build
    from .publish_handlers import register_handlers as reg_publish
    from .quality_handlers import register_handlers as reg_quality
    from .runner_handlers import register_handlers as reg_runner

    reg_resolve(runner)
    reg_build(runner)
    reg_publish(runner)
    reg_quality(runner)
    reg_runner(runner)
