"""OSM Geocoder event handlers.

Registers handlers for all OSM, Census TIGER, and visualization event facets.
"""

from .boundary_handlers import register_boundary_handlers
from .cache_handlers import register_cache_handlers
from .downloader import download as download_region  # noqa: F401
from .filter_handlers import register_filter_handlers
from .operations_handlers import register_operations_handlers
from .poi_handlers import register_poi_handlers
from .route_handlers import register_route_handlers
from .tiger_handlers import register_tiger_handlers
from .visualization_handlers import register_visualization_handlers

__all__ = [
    "register_all_handlers",
    "register_boundary_handlers",
    "register_cache_handlers",
    "register_filter_handlers",
    "register_operations_handlers",
    "register_poi_handlers",
    "register_route_handlers",
    "register_tiger_handlers",
    "register_visualization_handlers",
    "download_region",
]


def register_all_handlers(poller) -> None:
    """Register all event facet handlers with the given poller."""
    register_boundary_handlers(poller)
    register_cache_handlers(poller)
    register_filter_handlers(poller)
    register_operations_handlers(poller)
    register_poi_handlers(poller)
    register_route_handlers(poller)
    register_tiger_handlers(poller)
    register_visualization_handlers(poller)
