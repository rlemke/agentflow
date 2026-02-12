"""Operations event facet handlers for OSM data processing.

Handles Download, Tile, RoutingGraph, Status, Cache, and related operations
defined in osmoperations.afl under the osm.geo.Operations namespace.
"""

import logging
import re

from .cache_handlers import REGION_REGISTRY

log = logging.getLogger(__name__)

NAMESPACE = "osm.geo.Operations"

# All event facets in osm.geo.Operations and their return parameter names.
# NOTE: Cache is handled separately (takes region:String, not cache:OSMCache).
OPERATIONS_FACETS: dict[str, str | None] = {
    "Download": None,  # => ()
    "Tile": "tiles",
    "RoutingGraph": "graph",
    "Status": "stats",
    "GeoOSMCache": "graph",
    "PostGisImport": "stats",
    "DownloadAll": None,  # => ()
    "TileAll": "tiles",
    "RoutingGraphAll": "graph",
    "StatusAll": "stats",
    "GeoOSMCacheAll": "graph",
    "DownloadShapefile": None,  # => ()
    "DownloadShapefileAll": None,  # => ()
}

# Flat lookup: region name -> Geofabrik path (built from cache_handlers registry)
_REGION_LOOKUP: dict[str, str] = {}
for _ns, _facets in REGION_REGISTRY.items():
    for _name, _path in _facets.items():
        if _name not in _REGION_LOOKUP:
            _REGION_LOOKUP[_name] = _path

# Pattern to extract region path from a Geofabrik URL
_GEOFABRIK_REGION_RE = re.compile(r"https?://download\.geofabrik\.de/(.+)-latest\.[^/]+$")


def _extract_region_path(url: str) -> str:
    """Extract the region path from a Geofabrik download URL.

    E.g. "https://download.geofabrik.de/africa/algeria-latest.osm.pbf"
    returns "africa/algeria".
    """
    m = _GEOFABRIK_REGION_RE.match(url)
    if m:
        return m.group(1)
    return url


def _make_operation_handler(facet_name: str, return_param: str | None):
    """Create a handler for an operations event facet."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        log.info("%s processing cache: %s", facet_name, cache.get("url", "unknown"))

        if return_param is None:
            return {}

        return {
            return_param: {
                "url": cache.get("url", ""),
                "path": cache.get("path", ""),
                "date": cache.get("date", ""),
                "size": cache.get("size", 0),
                "wasInCache": True,
            }
        }

    return handler


def _make_shapefile_handler(facet_name: str):
    """Create a handler for a shapefile download event facet."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        url = cache.get("url", "")
        region_path = _extract_region_path(url)
        log.info("%s downloading shapefile for: %s", facet_name, region_path)
        from .downloader import download

        return download(region_path, fmt="shp")

    return handler


def _cache_handler(payload: dict) -> dict:
    """Handle the Cache event facet: resolve a region name and download the PBF.

    Takes region:String, looks up the Geofabrik path from the region registry,
    downloads (with local caching), and returns cache:OSMCache.
    """
    from .downloader import download

    region = payload.get("region", "")

    # Try exact match first
    region_path = _REGION_LOOKUP.get(region)

    # Fall back to case-insensitive search
    if not region_path:
        region_lower = region.lower()
        for name, path in _REGION_LOOKUP.items():
            if name.lower() == region_lower:
                region_path = path
                break

    if not region_path:
        log.warning("Cache: unknown region '%s', using as raw path", region)
        region_path = region.lower()

    log.info("Cache: resolving region '%s' -> '%s'", region, region_path)
    return {"cache": download(region_path)}


def register_operations_handlers(poller) -> None:
    """Register all operations event facet handlers with the poller."""
    # Register the Cache handler (takes region:String, not cache:OSMCache)
    poller.register(f"{NAMESPACE}.Cache", _cache_handler)

    shapefile_facets = {"DownloadShapefile", "DownloadShapefileAll"}
    for facet_name, return_param in OPERATIONS_FACETS.items():
        qualified_name = f"{NAMESPACE}.{facet_name}"
        if facet_name in shapefile_facets:
            poller.register(qualified_name, _make_shapefile_handler(facet_name))
        else:
            poller.register(qualified_name, _make_operation_handler(facet_name, return_param))
