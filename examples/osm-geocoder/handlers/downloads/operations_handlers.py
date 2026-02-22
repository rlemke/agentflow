"""Operations event facet handlers for OSM data processing.

Handles Download, Tile, RoutingGraph, Status, Cache, and related operations
defined in osmoperations.afl under the osm.geo.Operations namespace.
"""

import logging
import os
import re

from ..cache.cache_handlers import REGION_REGISTRY

log = logging.getLogger(__name__)

NAMESPACE = "osm.geo.Operations"

# All event facets in osm.geo.Operations and their return parameter names.
# NOTE: Cache is handled separately (takes region:String, not cache:OSMCache).
OPERATIONS_FACETS: dict[str, str | None] = {
    "Tile": "tiles",
    "RoutingGraph": "graph",
    "Status": "stats",
    "GeoOSMCache": "graph",
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
        step_log = payload.get("_step_log")
        if step_log:
            step_log(f"{facet_name}: processing {cache.get('url', 'unknown')}")
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
        step_log = payload.get("_step_log")
        log.info("%s downloading shapefile for: %s", facet_name, region_path)
        from ..shared.downloader import download

        result = download(region_path, fmt="shp")
        source = result.get("source", "unknown")
        if step_log:
            step_log(f"{facet_name}: shapefile for {region_path} (source={source})")
        return result

    return handler


def _download_handler(payload: dict) -> dict:
    """Handle the Download event facet: download any URL to any file path.

    Takes url:String, path:String, force:Boolean and downloads the content.
    The path may be a local filesystem path or an hdfs:// URI.
    Returns downloadCache:OSMCache.
    """
    from ..shared.downloader import download_url

    url = payload.get("url", "")
    path = payload.get("path", "")
    force = payload.get("force", False)
    step_log = payload.get("_step_log")
    if step_log:
        step_log(f"Download: {url} -> {path}")

    log.info("Download: %s -> %s (force=%s)", url, path, force)
    return {"downloadCache": download_url(url, path, force=force)}


def _cache_handler(payload: dict) -> dict:
    """Handle the Cache event facet: resolve a region name and download the PBF.

    Takes region:String, looks up the Geofabrik path from the region registry,
    downloads (with local caching), and returns cache:OSMCache.
    """
    from ..shared.downloader import download

    region = payload.get("region", "")
    step_log = payload.get("_step_log")

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
    cache = download(region_path)
    source = cache.get("source", "unknown")
    if step_log:
        step_log(f"Cache: region '{region}' -> '{region_path}' (source={source})")
    return {"cache": cache}


def register_operations_handlers(poller) -> None:
    """Register all operations event facet handlers with the poller."""
    # Register the Cache handler (takes region:String, not cache:OSMCache)
    poller.register(f"{NAMESPACE}.Cache", _cache_handler)
    # Register the Download handler (takes url:String, path:String, force:Boolean)
    poller.register(f"{NAMESPACE}.Download", _download_handler)

    shapefile_facets = {"DownloadShapefile", "DownloadShapefileAll"}
    for facet_name, return_param in OPERATIONS_FACETS.items():
        qualified_name = f"{NAMESPACE}.{facet_name}"
        if facet_name in shapefile_facets:
            poller.register(qualified_name, _make_shapefile_handler(facet_name))
        else:
            poller.register(qualified_name, _make_operation_handler(facet_name, return_param))


# RegistryRunner dispatch adapter
_DISPATCH: dict[str, callable] = {}


def _build_dispatch() -> None:
    _DISPATCH[f"{NAMESPACE}.Cache"] = _cache_handler
    _DISPATCH[f"{NAMESPACE}.Download"] = _download_handler
    shapefile_facets = {"DownloadShapefile", "DownloadShapefileAll"}
    for facet_name, return_param in OPERATIONS_FACETS.items():
        qualified_name = f"{NAMESPACE}.{facet_name}"
        if facet_name in shapefile_facets:
            _DISPATCH[qualified_name] = _make_shapefile_handler(facet_name)
        else:
            _DISPATCH[qualified_name] = _make_operation_handler(facet_name, return_param)


_build_dispatch()


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )
