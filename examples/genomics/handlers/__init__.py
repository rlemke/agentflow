"""Genomics cohort analysis handlers."""

from .cache_handlers import register_cache_handlers
from .genomics_handlers import register_genomics_handlers
from .index_handlers import register_index_handlers
from .operations_handlers import register_operations_handlers
from .resolve_handlers import register_resolve_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_genomics_handlers",
    "register_cache_handlers",
    "register_resolve_handlers",
    "register_index_handlers",
    "register_operations_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all genomics event facet handlers with the given poller."""
    register_genomics_handlers(poller)
    register_cache_handlers(poller)
    register_resolve_handlers(poller)
    register_index_handlers(poller)
    register_operations_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all genomics event facet handlers with a RegistryRunner."""
    from .cache_handlers import register_handlers as reg_cache
    from .genomics_handlers import register_handlers as reg_genomics
    from .index_handlers import register_handlers as reg_index
    from .operations_handlers import register_handlers as reg_operations
    from .resolve_handlers import register_handlers as reg_resolve

    reg_genomics(runner)
    reg_cache(runner)
    reg_resolve(runner)
    reg_index(runner)
    reg_operations(runner)
