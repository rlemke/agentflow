# OSM Geocoder Agent

A geocoding agent that resolves street addresses to geographic coordinates using the [OpenStreetMap Nominatim API](https://nominatim.openstreetmap.org/), plus handlers for ~580 OSM data processing event facets covering caching, boundaries, routes, parks, population, buildings, amenities, roads, visualization, GraphHopper routing graphs, and more.

## What it does

This example demonstrates:
- **Schema declarations** for typed data structures (`GeoCoordinate`, `OSMCache`)
- **Event facets** for external agent dispatch (`osm.geo.Geocode`, cache, operations, POI)
- **AgentPoller** for building a standalone agent service
- **Foreach iteration** for batch geocoding (`GeocodeAll`)
- **Namespace-qualified handlers** registered programmatically from region registries
- **Multi-format downloads** — PBF (default) and Geofabrik free shapefiles (`.shp.zip`) — see [SHAPEFILES.md](SHAPEFILES.md)

### AFL Workflow

```afl
schema GeoCoordinate {
    lat: String
    lon: String
    display_name: String
}

namespace osm.geo {
    event facet Geocode(address: String) => (result: GeoCoordinate)

    workflow GeocodeAddress(address: String) => (location: GeoCoordinate) andThen {
        geo = Geocode(address = $.address)
        yield GeocodeAddress(location = geo.result)
    }
}
```

### Execution flow

1. `GeocodeAddress` workflow receives an address string
2. The `Geocode` event step pauses execution and creates a task
3. The geocoder agent picks up the task, calls the Nominatim API
4. The agent writes the result back and the workflow resumes
5. The workflow yields the `GeoCoordinate` as its output

## Prerequisites

```bash
# From the repo root
source .venv/bin/activate
pip install -r examples/osm-geocoder/requirements.txt
```

## Running

### Offline test (no network, mock handler)

```bash
PYTHONPATH=. python examples/osm-geocoder/test_geocoder.py
```

Expected output:
```
Executing GeocodeAddress workflow...
  Status: ExecutionStatus.PAUSED
Agent processing Geocode event...
  Dispatched: 1 task(s)
Resuming workflow...
  Status: ExecutionStatus.COMPLETED
  Outputs: {'location': {'lat': '48.8566', 'lon': '2.3522', 'display_name': 'Mock result for: 1600 Pennsylvania Avenue, Washington DC'}}

All assertions passed.
```

### Live agent (calls Nominatim API)

```bash
PYTHONPATH=. python examples/osm-geocoder/agent.py
```

This starts a long-running agent that polls for `osm.geo.Geocode` tasks and ~330 OSM data events (caching, boundaries, routes, parks, population, visualization, etc.). In production, you would pair it with a runner service that executes workflows.

### Compile check

```bash
# Check all AFL sources
for f in examples/osm-geocoder/afl/*.afl; do scripts/compile "$f" --check; done
```

## Handler modules

The `handlers/` package organizes event facet handlers by category:

| Module | Event facets | Description |
|--------|-------------|-------------|
| `cache_handlers.py` | ~250 | Geographic region cache lookups across 11 namespaces — see [CACHE.md](CACHE.md) |
| `operations_handlers.py` | 13 | Downloads and data processing operations — see [DOWNLOADS.md](DOWNLOADS.md) |
| `poi_handlers.py` | 8 | Point-of-interest extraction — see [POI.md](POI.md) |
| `boundary_handlers.py` | 7 | Administrative and natural boundary extraction — see [BOUNDARIES.md](BOUNDARIES.md) |
| `filter_handlers.py` | 7 | Radius-based and OSM type filtering — see [FILTERS.md](FILTERS.md) |
| `tiger_handlers.py` | 9 | US Census TIGER voting district data — see [VOTING.md](VOTING.md) |
| `visualization_handlers.py` | 5 | GeoJSON map rendering with Leaflet — see [VISUALIZATION.md](VISUALIZATION.md) |
| `route_handlers.py` | 8 | Bicycle, hiking, train, bus route extraction — see [ROUTES.md](ROUTES.md) |
| `population_handlers.py` | 11 | Population-based filtering for cities, states, etc. — see [POPULATION.md](POPULATION.md) |
| `park_handlers.py` | 8 | National parks, state parks, protected areas — see [PARKS.md](PARKS.md) |
| `building_handlers.py` | 9 | Building footprint extraction with classification — see [BUILDINGS.md](BUILDINGS.md) |
| `amenity_handlers.py` | 29 | Amenity extraction (food, shopping, healthcare, etc.) — see [AMENITIES.md](AMENITIES.md) |
| `road_handlers.py` | 15 | Road network extraction by classification — see [ROADS.md](ROADS.md) |
| `graphhopper_handlers.py` | ~200 | GraphHopper routing graph operations — see [GRAPHHOPPER.md](GRAPHHOPPER.md) |
| `__init__.py` | — | `register_all_handlers(poller)` convenience function |

## AFL source files

| File | Description |
|------|-------------|
| `afl/geocoder.afl` | Schema, event facet, and workflows for address geocoding |
| `afl/osmtypes.afl` | `OSMCache` schema used by all OSM facets |
| `afl/osmcache.afl` | ~250 cache event facets across 11 geographic namespaces |
| `afl/osmoperations.afl` | Data processing operations (download, tile, routing, shapefile download) |
| `afl/osmpoi.afl` | Point-of-interest extraction facets |
| `afl/osmboundaries.afl` | Administrative and natural boundary extraction facets |
| `afl/osmfilters.afl` | Radius-based and OSM type filtering facets |
| `afl/osmfilters_population.afl` | Population-based filtering facets |
| `afl/osmvoting.afl` | US Census TIGER voting district facets |
| `afl/osmvisualization.afl` | GeoJSON visualization and map rendering facets |
| `afl/osmroutes.afl` | Bicycle, hiking, train, bus route extraction facets |
| `afl/osmparks.afl` | National parks, state parks, protected areas facets |
| `afl/osmbuildings.afl` | Building footprint extraction facets |
| `afl/osmamenities.afl` | Amenity extraction facets (food, shopping, healthcare, etc.) |
| `afl/osmroads.afl` | Road network extraction facets |
| `afl/osmgraphhopper.afl` | GraphHopper routing graph operation facets |
| `afl/osmgraphhoppercache.afl` | Per-region GraphHopper cache facets (~200 facets) |
| `afl/osmgraphhopper_workflows.afl` | Regional routing graph workflow compositions |
| `afl/osmworkflows_composed.afl` | Example composed workflows demonstrating facet composition |
| `afl/osmafrica.afl` | Africa workflow composing cache + download steps |
| `afl/osmasia.afl` | Asia workflow |
| `afl/osmaustralia.afl` | Australia/Oceania workflow |
| `afl/osmcanada.afl` | Canada provinces workflow |
| `afl/osmcentralamerica.afl` | Central America workflow |
| `afl/osmeurope.afl` | Europe workflow |
| `afl/osmnorthamerica.afl` | North America workflow |
| `afl/osmsouthamerica.afl` | South America workflow |
| `afl/osmunitedstates.afl` | US states workflow |
| `afl/osmcontinents.afl` | Continents workflow |
| `afl/osmworld.afl` | World workflow composing all regional workflows |
| `afl/osmshapefiles.afl` | Europe shapefile download workflow (reuses cache facets with `DownloadShapefile`) |
| `afl/example_routes_visualization.afl` | Example workflows combining routes and visualization |

## Other files

| File | Description |
|------|-------------|
| `agent.py` | Live agent using AgentPoller + Nominatim API + all OSM handlers |
| `test_geocoder.py` | Offline end-to-end test with mock handler |
| `test_downloader.py` | Downloader unit tests (PBF and shapefile formats) |
| `test_filters.py` | Radius and OSM type filter tests |
| `test_tiger.py` | Census TIGER voting district tests |
| `test_visualization.py` | Map visualization tests |
| `test_routes.py` | Route extraction tests |
| `test_population.py` | Population filter tests |
| `test_parks.py` | Park extraction tests |
| `requirements.txt` | Python dependencies (`requests`, `pyosmium`, `shapely`, `pyproj`, `folium`) |

## Documentation

| File | Description |
|------|-------------|
| `CACHE.md` | Cache system documentation (OSMCache schema, namespaces, region registry) |
| `DOWNLOADS.md` | Downloads and operations documentation (downloader API, operation facets, formats) |
| `POI.md` | POI extraction documentation (event facets, handler dispatch, return grouping) |
| `SHAPEFILES.md` | Shapefile download documentation (format details, handler flow, availability notes) |
| `BOUNDARIES.md` | Administrative and natural boundary extraction |
| `FILTERS.md` | Radius-based filtering and OSM type filtering |
| `VOTING.md` | US Census TIGER voting district data |
| `VISUALIZATION.md` | GeoJSON map rendering with Leaflet/Folium |
| `ROUTES.md` | Bicycle, hiking, train, bus route extraction |
| `POPULATION.md` | Population-based filtering for places |
| `PARKS.md` | National parks, state parks, protected areas |
| `BUILDINGS.md` | Building footprint extraction with classification |
| `AMENITIES.md` | Amenity extraction (restaurants, shops, healthcare, etc.) |
| `ROADS.md` | Road network extraction by classification |
| `GRAPHHOPPER.md` | GraphHopper routing graph building and caching |
| `COMPOSED_WORKFLOWS.md` | Examples demonstrating facet-based workflow composition |
