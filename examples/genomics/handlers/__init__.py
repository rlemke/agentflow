"""Genomics cohort analysis handlers."""

from .genomics_handlers import register_genomics_handlers

__all__ = ["register_all_handlers", "register_genomics_handlers"]


def register_all_handlers(poller) -> None:
    """Register all genomics event facet handlers with the given poller."""
    register_genomics_handlers(poller)
