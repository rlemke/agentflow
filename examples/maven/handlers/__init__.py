"""Maven runner handlers."""

from .runner_handlers import register_runner_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_runner_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all Maven event facet handlers with the given poller."""
    register_runner_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all Maven event facet handlers with a RegistryRunner."""
    from .runner_handlers import register_handlers as reg_runner

    reg_runner(runner)
