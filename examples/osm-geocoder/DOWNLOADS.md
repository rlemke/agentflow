# Downloads and Operations

The operations layer handles data processing tasks that act on cached OSM data. Operations receive an `OSMCache` struct from a cache facet and perform work such as downloading files, generating map tiles, building routing graphs, or importing data into PostGIS.

## AFL facets

All operations are defined in `afl/osmoperations.afl` under two namespaces.

### Data facets

The `osm.geo.Operations.Data` namespace defines metadata facets used as parameters:

```afl
namespace osm.geo.Operations.Data {
    facet OsmDate(date: String = "latest")
    facet OsmDownloadUrl(url: String = null)
    facet OsmCachedLocation(location: String = null)
    facet OsmForce(force: Boolean = false)
}
```

These are plain facets (not event facets) — they carry configuration values but do not trigger agent execution.

### Event facets

The `osm.geo.Operations` namespace defines 13 event facets:

```afl
namespace osm.geo.Operations {
    event facet Download(cache:OSMCache) => ()
    event facet Tile(cache:OSMCache) => (tiles:OSMCache)
    event facet RoutingGraph(cache:OSMCache) => (graph:OSMCache)
    event facet Status(cache:OSMCache) => (stats:OSMCache)
    event facet GeoOSMCache(cache:OSMCache) => (graph:OSMCache)
    event facet PostGisImport(cache:OSMCache) => (stats:OSMCache)
    event facet DownloadAll(cache:OSMCache) => ()
    event facet TileAll(cache:OSMCache) => (tiles:OSMCache)
    event facet RoutingGraphAll(cache:OSMCache) => (graph:OSMCache)
    event facet StatusAll(cache:OSMCache) => (stats:OSMCache)
    event facet GeoOSMCacheAll(cache:OSMCache) => (graph:OSMCache)
    event facet DownloadShapefile(cache:OSMCache) => ()
    event facet DownloadShapefileAll(cache:OSMCache) => ()
}
```

### Facet reference

| Facet | Return | Description |
|-------|--------|-------------|
| `Download` | `()` | Download a PBF file for a single region |
| `DownloadAll` | `()` | Download a PBF file for a bulk/aggregate region |
| `DownloadShapefile` | `()` | Download a Geofabrik free shapefile for a single region |
| `DownloadShapefileAll` | `()` | Download a shapefile for a bulk/aggregate region |
| `Tile` | `tiles:OSMCache` | Generate map tiles from a single region's PBF |
| `TileAll` | `tiles:OSMCache` | Generate map tiles from a bulk region |
| `RoutingGraph` | `graph:OSMCache` | Build a routing graph from a single region's PBF |
| `RoutingGraphAll` | `graph:OSMCache` | Build a routing graph from a bulk region |
| `Status` | `stats:OSMCache` | Report processing status for a single region |
| `StatusAll` | `stats:OSMCache` | Report processing status for a bulk region |
| `GeoOSMCache` | `graph:OSMCache` | Generate GeoJSON cache from a single region |
| `GeoOSMCacheAll` | `graph:OSMCache` | Generate GeoJSON cache from a bulk region |
| `PostGisImport` | `stats:OSMCache` | Import a region into PostGIS |

The `*All` variants are identical in signature to their single-region counterparts. The distinction is semantic — workflows use them to signal that the input is a continent or aggregate extract rather than a single country.

## Python handlers

Operations handlers are registered in `handlers/operations_handlers.py`. The module defines two handler factories:

### Standard operation handler

For most facets, `_make_operation_handler` creates a pass-through handler that logs the operation and returns the cache data under the appropriate return parameter name:

```python
def _make_operation_handler(facet_name: str, return_param: str | None):
    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        if return_param is None:
            return {}
        return {return_param: {
            "url": cache.get("url", ""),
            "path": cache.get("path", ""),
            # ...
        }}
    return handler
```

Facets with `=> ()` (no return) use `return_param=None` and return an empty dict.

### Shapefile handler

`DownloadShapefile` and `DownloadShapefileAll` use a specialized handler that extracts the region path from the cache URL and downloads in shapefile format. See [SHAPEFILES.md](SHAPEFILES.md) for details.

### Handler dispatch

Registration routes each facet to the correct factory:

```python
OPERATIONS_FACETS = {
    "Download": None,        # => ()
    "Tile": "tiles",
    "RoutingGraph": "graph",
    "Status": "stats",
    "GeoOSMCache": "graph",
    "PostGisImport": "stats",
    "DownloadAll": None,
    "TileAll": "tiles",
    "RoutingGraphAll": "graph",
    "StatusAll": "stats",
    "GeoOSMCacheAll": "graph",
    "DownloadShapefile": None,
    "DownloadShapefileAll": None,
}
```

All handlers are registered under the qualified name `osm.geo.Operations.<FacetName>`.

## Downloader module

The `handlers/downloader.py` module is a standalone HTTP client with filesystem caching. It has no AgentFlow dependencies and can be used independently.

### API

```python
from handlers.downloader import download, geofabrik_url, cache_path

# Build a Geofabrik URL
geofabrik_url("europe/albania")              # https://download.geofabrik.de/europe/albania-latest.osm.pbf
geofabrik_url("europe/albania", fmt="shp")   # https://download.geofabrik.de/europe/albania-latest.free.shp.zip

# Get the local cache path
cache_path("europe/albania")                 # /tmp/osm-cache/europe/albania-latest.osm.pbf

# Download (returns OSMCache dict)
result = download("europe/albania")
result = download("europe/albania", fmt="shp")
```

### Supported formats

| Format key | File extension | Description |
|-----------|---------------|-------------|
| `"pbf"` | `osm.pbf` | Protocol Buffer Format — compact binary OSM data (default) |
| `"shp"` | `free.shp.zip` | Geofabrik free shapefile extract (zipped) |

### Caching behavior

- Files are cached under `/tmp/osm-cache/` mirroring the Geofabrik directory structure
- PBF and shapefile formats are cached independently (different file extensions)
- A file is considered cached if it exists on disk — no TTL or staleness check
- Downloads use streaming (`iter_content`) with an 8 KB chunk size
- The `User-Agent` header is set to `AgentFlow-OSM-Example/1.0`
- HTTP errors propagate as `requests.HTTPError` exceptions
- Timeout is 300 seconds per download

### Return value

The `download()` function returns an `OSMCache`-compatible dict:

```python
{
    "url": "https://download.geofabrik.de/europe/albania-latest.osm.pbf",
    "path": "/tmp/osm-cache/europe/albania-latest.osm.pbf",
    "date": "2026-02-01T12:00:00+00:00",
    "size": 14523648,
    "wasInCache": False
}
```

## How workflows use operations

Regional workflows compose cache lookups with operations in an `andThen` block:

```afl
facet AfricaIndividually() => (cache: [OSMCache]) andThen {
    algeria = Algeria()                            // cache lookup
    dl_algeria = Download(cache = algeria.cache)   // PBF download

    // ... more countries

    yield AfricaIndividually(cache = dl_algeria.cache ++ ...)
}
```

Steps within an `andThen` block execute based on data dependencies. All cache lookups run in parallel, and each download runs as soon as its cache step completes.

## Tests

```bash
# Downloader unit tests (PBF and shapefile)
PYTHONPATH=. python -m pytest examples/osm-geocoder/test_downloader.py -v

# All OSM geocoder tests
PYTHONPATH=. python -m pytest examples/osm-geocoder/ -v
```
