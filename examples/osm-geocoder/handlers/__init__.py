"""OSM Geocoder event handlers.

Registers handlers for all OSM event facets with an AgentPoller.
"""

from .boundary_handlers import register_boundary_handlers
from .cache_handlers import register_cache_handlers
from .downloader import download as download_region  # noqa: F401
from .filter_handlers import register_filter_handlers
from .operations_handlers import register_operations_handlers
from .poi_handlers import register_poi_handlers

__all__ = [
    "register_all_handlers",
    "register_boundary_handlers",
    "register_cache_handlers",
    "register_filter_handlers",
    "register_operations_handlers",
    "register_poi_handlers",
    "download_region",
]


def register_all_handlers(poller) -> None:
    """Register all OSM event facet handlers with the given poller."""
    register_boundary_handlers(poller)
    register_cache_handlers(poller)
    register_filter_handlers(poller)
    register_operations_handlers(poller)
    register_poi_handlers(poller)
