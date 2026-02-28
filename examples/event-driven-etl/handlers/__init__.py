"""Handler registration for the event-driven ETL example."""

from __future__ import annotations

from .extract.extract_handlers import register_extract_handlers
from .load.load_handlers import register_load_handlers
from .transform.transform_handlers import register_transform_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_extract_handlers(poller)
    register_transform_handlers(poller)
    register_load_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .extract.extract_handlers import register_handlers as reg_extract
    from .load.load_handlers import register_handlers as reg_load
    from .transform.transform_handlers import register_handlers as reg_transform

    reg_extract(runner)
    reg_transform(runner)
    reg_load(runner)
