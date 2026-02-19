# OSM Geocoder — User Guide

> See also: [Examples Guide](../doc/GUIDE.md) | [README](README.md)

## When to Use This Example

Use this as your starting point if you are:
- Building a **production-scale agent** with hundreds of event facets
- Organizing handlers across **many modules and namespaces**
- Working with **geographic data**, OSM APIs, or spatial operations
- Understanding how to structure a **large AFL project** with 40+ source files

## What You'll Learn

1. How to organize a large AFL project with namespace-per-domain architecture
2. How to build handler modules for different categories of operations
3. How factory-built handlers work with geographic registries
4. How to use the `AgentPoller` for a standalone agent service
5. How to write integration tests for composed workflows
6. How to **encapsulate low-level operations** behind simple composed facets for library reuse
7. How to use the **Geofabrik mirror** for offline and CI workflows

## Overview

This is the largest example in the repository:
- **44 AFL files** covering geocoding, caching, operations, boundaries, routes, parks, population, buildings, amenities, roads, visualization, GraphHopper routing, and more
- **580+ handler dispatch keys** across 15 modules
- **37 test files** including integration tests
- **17 documentation files** covering each handler category

## Project Structure

### AFL Files — Organized by Domain

| Category | Files | Facets | Description |
|----------|-------|--------|-------------|
| Core | `geocoder.afl`, `osmtypes.afl` | ~3 | Schema + geocoding workflow |
| Cache | `osmcache.afl` | ~250 | Per-region cache facets (11 geographic namespaces) |
| Operations | `osmoperations.afl` | 13 | Download, tile, routing graph, PostGIS import |
| Boundaries | `osmboundaries.afl` | 7 | Administrative and natural boundaries |
| Routes | `osmroutes.afl` | 8 | Bicycle, hiking, train, bus routes |
| Parks | `osmparks.afl` | 8 | National parks, protected areas |
| Population | `osmfilters_population.afl` | 11 | Population-based filtering |
| Buildings | `osmbuildings.afl` | 9 | Building footprint extraction |
| Amenities | `osmamenities.afl` | 29 | Restaurants, shops, healthcare |
| Roads | `osmroads.afl` | 15 | Road network by classification |
| POI | `osmpoi.afl` | 8 | Points of interest |
| Visualization | `osmvisualization.afl` | 5 | Map rendering, GeoJSON |
| GraphHopper | `osmgraphhopper.afl` + cache | ~200 | Routing graph operations |
| Workflows | Regional + composed | — | Per-continent/country workflows |

### Handler Modules — Organized by Category

Each handler module follows the dispatch adapter pattern:

```
handlers/
├── __init__.py                 # register_all_handlers()
├── cache_handlers.py           # ~250 handlers (factory-built from registry)
├── operations_handlers.py      # 13 handlers
├── poi_handlers.py             # 8 handlers
├── boundary_handlers.py        # 7 handlers
├── filter_handlers.py          # 7 handlers
├── route_handlers.py           # 8 handlers
├── population_handlers.py      # 11 handlers
├── park_handlers.py            # 8 handlers
├── building_handlers.py        # 9 handlers
├── amenity_handlers.py         # 29 handlers
├── road_handlers.py            # 15 handlers
├── tiger_handlers.py           # 9 handlers (US Census data)
├── visualization_handlers.py   # 5 handlers
├── graphhopper_handlers.py     # ~200 handlers
└── postgis_handlers.py         # PostGIS import handler
```

## Step-by-Step Walkthrough

### 1. The Core Pattern — Geocoding

The simplest operation in this example:

```afl
namespace osm.geo {
    event facet Geocode(address: String) => (result: GeoCoordinate)

    workflow GeocodeAddress(address: String) => (location: GeoCoordinate) andThen {
        geo = Geocode(address = $.address)
        yield GeocodeAddress(location = geo.result)
    }
}
```

The handler calls the Nominatim API:

```python
def _geocode_handler(payload):
    address = payload["address"]
    response = requests.get("https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json", "limit": 1})
    data = response.json()[0]
    return {"result": {"lat": data["lat"], "lon": data["lon"], "display_name": data["display_name"]}}
```

### 2. Factory-Built Cache Handlers

The cache system uses a geographic registry:

```python
REGION_REGISTRY = {
    "osm.cache.Africa": {
        "Algeria": "https://download.geofabrik.de/africa/algeria-latest.osm.pbf",
        "Angola": "https://download.geofabrik.de/africa/angola-latest.osm.pbf",
        # ... 50+ countries
    },
    "osm.cache.Europe": { ... },
    # ... 11 namespaces
}

# Factory generates one handler per region per namespace
for namespace, regions in REGION_REGISTRY.items():
    for region_name, url in regions.items():
        _DISPATCH[f"{namespace}.{region_name}"] = _make_cache_handler(region_name, url)
```

### 3. Running the Offline Test

```bash
source .venv/bin/activate
pip install -r examples/osm-geocoder/requirements.txt

# No network required — uses mock handler
PYTHONPATH=. python examples/osm-geocoder/test_geocoder.py
```

### 4. Running the Live Agent

```bash
# Starts polling for all OSM event facets
PYTHONPATH=. python examples/osm-geocoder/agent.py
```

### 5. Compile Checking All AFL

```bash
for f in examples/osm-geocoder/afl/*.afl; do
    python -m afl.cli "$f" --check && echo "OK: $f"
done
```

### 6. Geofabrik Mirror for Offline Workflows

In CI or air-gapped environments, use the local mirror to avoid network requests:

```bash
# Prefetch all regions (or a subset) into a mirror directory
scripts/osm-prefetch --mirror-dir /data/osm-mirror --include "europe/"

# Activate the mirror — the downloader reads from it before hitting the network
export AFL_GEOFABRIK_MIRROR=/data/osm-mirror

# Run the agent as usual — downloads are served from the mirror
PYTHONPATH=. python examples/osm-geocoder/agent.py
```

See [DOWNLOADS.md](DOWNLOADS.md#local-geofabrik-mirror) for all prefetch options and the full check order (cache → mirror → download).

## Key Concepts

### Namespace-Per-Domain Architecture

Each category of operations gets its own namespace:

```
osm.geo           — core geocoding
osm.cache.*       — per-region caching (11 geographic namespaces)
osm.geo.Operations — data processing
osm.geo.Boundaries — boundary extraction
osm.geo.Routes     — route extraction
osm.geo.Filters    — spatial filtering
```

This keeps namespaces focused and allows selective imports.

### Geographic Registry Pattern

Instead of hand-coding 250+ handler functions, use a registry:

```python
# Registry: namespace -> {region -> URL}
REGISTRY = {"osm.cache.Africa": {"Algeria": "...", "Angola": "...", ...}, ...}

# Factory: one handler per entry
def _make_handler(name, url):
    def handler(payload):
        return {"cache": {"url": url, "path": f"/cache/{name}.osm.pbf", ...}}
    return handler

# Build dispatch table from registry
_DISPATCH = {}
for ns, regions in REGISTRY.items():
    for name, url in regions.items():
        _DISPATCH[f"{ns}.{name}"] = _make_handler(name, url)
```

### Facet Encapsulation — Hiding Data Pipeline Complexity

The raw event facets (`Cache`, `Download`, `Tile`, `RoutingGraph`, `PostGisImport`, etc.) are low-level operations that require OSM domain expertise to chain correctly. Instead, **wrap multi-step data pipelines in composed facets** that expose a simple, domain-focused interface:

```afl
namespace osm.library {
    use osm.types

    // Composed facet: encapsulates cache + download + tile generation.
    // Users never see the three-step chain — they just call PrepareRegion.
    facet PrepareRegion(region: String) => (cache: OSMCache,
            tile_path: String) andThen {

        cached = osm.geo.Operations.Cache(region = $.region)

        downloaded = osm.geo.Operations.Download(cache = cached.cache)

        tiled = osm.geo.Operations.Tile(cache = downloaded.downloadCache)

        yield PrepareRegion(
            cache = downloaded.downloadCache,
            tile_path = tiled.tiles.path)
    }

    // Composed facet: encapsulates cache + download + routing graph build.
    // Hides PBF downloads and GraphHopper configuration behind one call.
    facet BuildRoutingData(region: String) => (cache: OSMCache,
            graph_path: String) andThen {

        cached = osm.geo.Operations.Cache(region = $.region)

        downloaded = osm.geo.Operations.Download(cache = cached.cache)

        graph = osm.geo.Operations.RoutingGraph(cache = downloaded.downloadCache)

        yield BuildRoutingData(
            cache = downloaded.downloadCache,
            graph_path = graph.graph.path)
    }

    // Composed facet: encapsulates full GIS import pipeline.
    // Cache → download → PostGIS import in one call.
    facet ImportToPostGIS(region: String) => (cache: OSMCache,
            import_status: String) andThen {

        cached = osm.geo.Operations.Cache(region = $.region)

        downloaded = osm.geo.Operations.Download(cache = cached.cache)

        imported = osm.geo.Operations.PostGisImport(cache = downloaded.downloadCache)

        yield ImportToPostGIS(
            cache = downloaded.downloadCache,
            import_status = "complete")
    }

    // Workflow: clean and simple — users call composed facets, not raw operations
    workflow PrepareEuropeRouting(countries: Json) => (graph_path: String,
            region: String) andThen foreach country in $.countries {

        routable = BuildRoutingData(region = $.country.name)

        yield PrepareEuropeRouting(
            graph_path = routable.graph_path,
            region = $.country.name)
    }
}
```

**Why this matters:**

| Layer | What the User Sees | What's Hidden |
|-------|-------------------|---------------|
| Event facets | `Cache`, `Download`, `Tile`, `RoutingGraph`, `PostGisImport` | Handler implementations, PBF/tile formats |
| Composed facets | `PrepareRegion(region)`, `BuildRoutingData(region)`, `ImportToPostGIS(region)` | Cache configuration, download URLs, tool-specific parameters |
| Workflows | `PrepareEuropeRouting(countries)` | The entire data pipeline structure |

This is the **library facet** pattern — the GIS team defines `PrepareRegion` and `BuildRoutingData` with correct operation ordering; application teams call them without needing to understand cache semantics, PBF file formats, or GraphHopper configuration.

### Composed Workflows

Regional workflows compose cache + download steps:

```afl
// Africa workflow composes cache lookups with download operations
namespace osm.africa {
    use osm.types
    workflow DownloadAfrica() => (...) andThen {
        algeria = osm.cache.Africa.Algeria()
        angola = osm.cache.Africa.Angola()
        // ... download each country
    }
}
```

## Adapting for Your Use Case

### Add a new handler category

1. Create `afl/osm_newcategory.afl` with event facets
2. Create `handlers/newcategory_handlers.py` with dispatch adapter
3. Wire into `handlers/__init__.py`
4. Add tests in the example's test files

### Build a focused agent from a subset

You don't need to register all 580+ handlers. Use topic filtering:

```bash
AFL_USE_REGISTRY=1 AFL_RUNNER_TOPICS=osm.geo,osm.cache.Europe \
    PYTHONPATH=. python examples/osm-geocoder/agent.py
```

### Use as a base for your own geographic agent

Fork the handler structure but replace the OSM-specific logic with your own data source.

## Documentation Index

Each handler category has detailed documentation:

| Document | Content |
|----------|---------|
| [CACHE.md](CACHE.md) | Cache system, namespaces, region registry |
| [DOWNLOADS.md](DOWNLOADS.md) | Download operations, PBF/shapefile formats |
| [POI.md](POI.md) | Point-of-interest extraction |
| [BOUNDARIES.md](BOUNDARIES.md) | Administrative/natural boundaries |
| [FILTERS.md](FILTERS.md) | Radius and OSM type filtering |
| [ROUTES.md](ROUTES.md) | Bicycle, hiking, train, bus routes |
| [POPULATION.md](POPULATION.md) | Population-based filtering |
| [PARKS.md](PARKS.md) | National parks, protected areas |
| [BUILDINGS.md](BUILDINGS.md) | Building footprint extraction |
| [AMENITIES.md](AMENITIES.md) | Amenity extraction |
| [ROADS.md](ROADS.md) | Road network extraction |
| [VISUALIZATION.md](VISUALIZATION.md) | Map rendering with Leaflet |
| [GRAPHHOPPER.md](GRAPHHOPPER.md) | Routing graph operations |
| [VOTING.md](VOTING.md) | US Census TIGER data |
| [SHAPEFILES.md](SHAPEFILES.md) | Shapefile downloads |
| [COMPOSED_WORKFLOWS.md](COMPOSED_WORKFLOWS.md) | Workflow composition examples |

## Next Steps

- **[continental-lz](../continental-lz/USER_GUIDE.md)** — run OSM pipelines at continental scale with Docker
- **[jenkins](../jenkins/USER_GUIDE.md)** — mixin composition patterns
- **[genomics](../genomics/USER_GUIDE.md)** — foreach fan-out for batch processing
