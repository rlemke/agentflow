"""Volcano query event handlers."""

from .volcano_handlers import register_volcano_handlers

__all__ = [
    "register_all_handlers",
    "register_volcano_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all event facet handlers with the given poller."""
    register_volcano_handlers(poller)
