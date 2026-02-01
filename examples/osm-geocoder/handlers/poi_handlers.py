"""POI event facet handlers for OSM point-of-interest extraction.

Handles Cities, Towns, Suburbs, Villages, Hamlets, Countries, POI,
and GeoOSMCache events defined in osmpoi.afl under osm.geo.POIs.
"""

import logging

log = logging.getLogger(__name__)

NAMESPACE = "osm.geo.POIs"

# Event facets in osm.geo.POIs and their return parameter names
POI_FACETS: dict[str, str] = {
    "POI": "pois",
    "Cities": "cities",
    "Towns": "towns",
    "Suburbs": "towns",
    "Villages": "villages",
    "Hamlets": "villages",
    "Countries": "villages",
    "GeoOSMCache": "geojson",
}


def _make_poi_handler(facet_name: str, return_param: str):
    """Create a handler for a POI event facet."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        log.info("%s extracting from: %s", facet_name, cache.get("url", "unknown"))

        return {
            return_param: {
                "url": cache.get("url", ""),
                "path": cache.get("path", ""),
                "date": cache.get("date", ""),
                "size": 0,
                "wasInCache": True,
            }
        }

    return handler


def register_poi_handlers(poller) -> None:
    """Register all POI event facet handlers with the poller."""
    for facet_name, return_param in POI_FACETS.items():
        qualified_name = f"{NAMESPACE}.{facet_name}"
        poller.register(qualified_name, _make_poi_handler(facet_name, return_param))
