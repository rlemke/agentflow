"""OSM Geocoder event handlers.

Registers handlers for all OSM, Census TIGER, GraphHopper, elevation, and visualization event facets.
"""

from .airquality_handlers import register_airquality_handlers
from .amenity_handlers import register_amenity_handlers
from .boundary_handlers import register_boundary_handlers
from .building_handlers import register_building_handlers
from .cache_handlers import register_cache_handlers
from .downloader import download as download_region  # noqa: F401
from .elevation_handlers import register_elevation_handlers
from .filter_handlers import register_filter_handlers
from .graphhopper_handlers import register_graphhopper_handlers
from .gtfs_handlers import register_gtfs_handlers
from .operations_handlers import register_operations_handlers
from .osmose_handlers import register_osmose_handlers
from .park_handlers import register_park_handlers
from .postgis_handlers import register_postgis_handlers
from .poi_handlers import register_poi_handlers
from .population_handlers import register_population_handlers
from .region_handlers import register_region_handlers
from .road_handlers import register_road_handlers
from .route_handlers import register_route_handlers
from .routing_handlers import register_routing_handlers
from .tiger_handlers import register_tiger_handlers
from .validation_handlers import register_validation_handlers
from .visualization_handlers import register_visualization_handlers
from .zoom_handlers import register_zoom_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_airquality_handlers",
    "register_amenity_handlers",
    "register_boundary_handlers",
    "register_building_handlers",
    "register_cache_handlers",
    "register_elevation_handlers",
    "register_filter_handlers",
    "register_graphhopper_handlers",
    "register_gtfs_handlers",
    "register_operations_handlers",
    "register_osmose_handlers",
    "register_park_handlers",
    "register_postgis_handlers",
    "register_poi_handlers",
    "register_population_handlers",
    "register_region_handlers",
    "register_road_handlers",
    "register_route_handlers",
    "register_routing_handlers",
    "register_tiger_handlers",
    "register_validation_handlers",
    "register_visualization_handlers",
    "register_zoom_handlers",
    "download_region",
]


def register_all_handlers(poller) -> None:
    """Register all event facet handlers with the given poller."""
    register_airquality_handlers(poller)
    register_amenity_handlers(poller)
    register_boundary_handlers(poller)
    register_building_handlers(poller)
    register_cache_handlers(poller)
    register_elevation_handlers(poller)
    register_filter_handlers(poller)
    register_graphhopper_handlers(poller)
    register_gtfs_handlers(poller)
    register_operations_handlers(poller)
    register_osmose_handlers(poller)
    register_park_handlers(poller)
    register_postgis_handlers(poller)
    register_poi_handlers(poller)
    register_population_handlers(poller)
    register_region_handlers(poller)
    register_road_handlers(poller)
    register_route_handlers(poller)
    register_routing_handlers(poller)
    register_tiger_handlers(poller)
    register_validation_handlers(poller)
    register_visualization_handlers(poller)
    register_zoom_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all event facet handlers with a RegistryRunner."""
    from .airquality_handlers import register_handlers as reg_airquality
    from .amenity_handlers import register_handlers as reg_amenity
    from .boundary_handlers import register_handlers as reg_boundary
    from .building_handlers import register_handlers as reg_building
    from .cache_handlers import register_handlers as reg_cache
    from .elevation_handlers import register_handlers as reg_elevation
    from .filter_handlers import register_handlers as reg_filter
    from .graphhopper_handlers import register_handlers as reg_graphhopper
    from .gtfs_handlers import register_handlers as reg_gtfs
    from .operations_handlers import register_handlers as reg_operations
    from .osmose_handlers import register_handlers as reg_osmose
    from .park_handlers import register_handlers as reg_park
    from .postgis_handlers import register_handlers as reg_postgis
    from .poi_handlers import register_handlers as reg_poi
    from .population_handlers import register_handlers as reg_population
    from .region_handlers import register_handlers as reg_region
    from .road_handlers import register_handlers as reg_road
    from .route_handlers import register_handlers as reg_route
    from .routing_handlers import register_handlers as reg_routing
    from .tiger_handlers import register_handlers as reg_tiger
    from .validation_handlers import register_handlers as reg_validation
    from .visualization_handlers import register_handlers as reg_visualization
    from .zoom_handlers import register_handlers as reg_zoom

    reg_airquality(runner)
    reg_amenity(runner)
    reg_boundary(runner)
    reg_building(runner)
    reg_cache(runner)
    reg_elevation(runner)
    reg_filter(runner)
    reg_graphhopper(runner)
    reg_gtfs(runner)
    reg_operations(runner)
    reg_osmose(runner)
    reg_park(runner)
    reg_postgis(runner)
    reg_poi(runner)
    reg_population(runner)
    reg_region(runner)
    reg_road(runner)
    reg_route(runner)
    reg_routing(runner)
    reg_tiger(runner)
    reg_validation(runner)
    reg_visualization(runner)
    reg_zoom(runner)
