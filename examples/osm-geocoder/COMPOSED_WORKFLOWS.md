# Composed Workflows

This document demonstrates the power of facet-based workflow composition. By combining cache, extraction, filtering, statistics, and visualization facets, you can build sophisticated data processing pipelines.

## Composition Patterns

### Pattern 1: Cache → Extract → Visualize

The basic three-stage pipeline for quick visualization.

```afl
workflow VisualizeBicycleRoutes(region: String = "Liechtenstein")
    => (map_path: String, route_count: Long) andThen {

    // Stage 1: Get cached region data
    cache = osm.geo.Operations.Cache(region = $.region)

    // Stage 2: Extract bicycle routes
    routes = osm.geo.Routes.BicycleRoutes(
        cache = cache.cache,
        include_infrastructure = true
    )

    // Stage 3: Visualize on map
    map = osm.geo.Visualization.RenderMap(
        geojson_path = routes.result.output_path,
        title = "Bicycle Routes",
        color = "#27ae60"
    )

    yield VisualizeBicycleRoutes(
        map_path = map.result.output_path,
        route_count = routes.result.feature_count
    )
}
```

### Pattern 2: Cache → Extract → Statistics

Analysis pipeline without visualization.

```afl
workflow AnalyzeParks(region: String = "Liechtenstein")
    => (total_parks: Long, total_area: Double, national: Long, state: Long) andThen {

    cache = osm.geo.Operations.Cache(region = $.region)
    parks = osm.geo.Parks.ExtractParks(cache = cache.cache, park_type = "all")
    stats = osm.geo.Parks.ParkStatistics(input_path = parks.result.output_path)

    yield AnalyzeParks(
        total_parks = stats.stats.total_parks,
        total_area = stats.stats.total_area_km2,
        national = stats.stats.national_parks,
        state = stats.stats.state_parks
    )
}
```

### Pattern 3: Cache → Extract → Filter → Visualize

Four-stage pipeline with filtering.

```afl
workflow LargeCitiesMap(region: String = "Liechtenstein", min_pop: Long = 10000)
    => (map_path: String, city_count: Long) andThen {

    cache = osm.geo.Operations.Cache(region = $.region)
    cities = osm.geo.Population.Cities(cache = cache.cache, min_population = 0)

    // Filter by population
    large = osm.geo.Population.FilterByPopulation(
        input_path = cities.result.output_path,
        min_population = $.min_pop,
        place_type = "city",
        operator = "gte"
    )

    map = osm.geo.Visualization.RenderMap(
        geojson_path = large.result.output_path,
        title = "Large Cities",
        color = "#e74c3c"
    )

    yield LargeCitiesMap(
        map_path = map.result.output_path,
        city_count = large.result.feature_count
    )
}
```

### Pattern 4: Parallel Extraction → Aggregated Statistics

Multiple extractions with combined analysis.

```afl
workflow TransportOverview(region: String = "Liechtenstein")
    => (bicycle_km: Double, hiking_km: Double, train_km: Double, bus_routes: Long) andThen {

    // Shared cache
    cache = osm.geo.Operations.Cache(region = $.region)

    // Parallel extraction (conceptually)
    bicycle = osm.geo.Routes.BicycleRoutes(cache = cache.cache, include_infrastructure = false)
    hiking = osm.geo.Routes.HikingTrails(cache = cache.cache, include_infrastructure = false)
    train = osm.geo.Routes.TrainRoutes(cache = cache.cache, include_infrastructure = false)
    bus = osm.geo.Routes.BusRoutes(cache = cache.cache, include_infrastructure = false)

    // Statistics for each
    bicycle_stats = osm.geo.Routes.RouteStatistics(input_path = bicycle.result.output_path)
    hiking_stats = osm.geo.Routes.RouteStatistics(input_path = hiking.result.output_path)
    train_stats = osm.geo.Routes.RouteStatistics(input_path = train.result.output_path)
    bus_stats = osm.geo.Routes.RouteStatistics(input_path = bus.result.output_path)

    yield TransportOverview(
        bicycle_km = bicycle_stats.stats.total_length_km,
        hiking_km = hiking_stats.stats.total_length_km,
        train_km = train_stats.stats.total_length_km,
        bus_routes = bus_stats.stats.route_count
    )
}
```

### Pattern 5: Full Five-Stage Pipeline

Cache → Extract → Filter → Statistics → Visualize

```afl
workflow NationalParksAnalysis(region: String = "Liechtenstein")
    => (map_path: String, park_count: Long, total_area: Double, avg_area: Double) andThen {

    cache = osm.geo.Operations.Cache(region = $.region)
    all_parks = osm.geo.Parks.ExtractParks(cache = cache.cache, park_type = "all")

    // Filter to national parks only
    national = osm.geo.Parks.FilterParksByType(
        input_path = all_parks.result.output_path,
        park_type = "national"
    )

    stats = osm.geo.Parks.ParkStatistics(input_path = national.result.output_path)

    map = osm.geo.Visualization.RenderMap(
        geojson_path = national.result.output_path,
        title = "National Parks",
        color = "#2ecc71"
    )

    yield NationalParksAnalysis(
        map_path = map.result.output_path,
        park_count = stats.stats.total_parks,
        total_area = stats.stats.total_area_km2,
        avg_area = stats.stats.total_area_km2
    )
}
```

### Pattern 6: Parameterized Regional Workflows

Same analysis pattern applied to different regions.

```afl
workflow GermanyCityAnalysis()
    => (map_path: String, large_cities: Long, total_pop: Long) andThen {

    cache = osm.geo.cache.Europe.Germany()
    cities = osm.geo.Population.Cities(cache = cache.cache, min_population = 100000)
    stats = osm.geo.Population.PopulationStatistics(
        input_path = cities.result.output_path,
        place_type = "city"
    )
    map = osm.geo.Visualization.RenderMap(
        geojson_path = cities.result.output_path,
        title = "German Cities > 100k",
        color = "#3498db"
    )

    yield GermanyCityAnalysis(
        map_path = map.result.output_path,
        large_cities = stats.stats.total_places,
        total_pop = stats.stats.total_population
    )
}

workflow FranceCityAnalysis()
    => (map_path: String, large_cities: Long, total_pop: Long) andThen {

    cache = osm.geo.cache.Europe.France()
    cities = osm.geo.Population.Cities(cache = cache.cache, min_population = 100000)
    stats = osm.geo.Population.PopulationStatistics(
        input_path = cities.result.output_path,
        place_type = "city"
    )
    map = osm.geo.Visualization.RenderMap(
        geojson_path = cities.result.output_path,
        title = "French Cities > 100k",
        color = "#e74c3c"
    )

    yield FranceCityAnalysis(
        map_path = map.result.output_path,
        large_cities = stats.stats.total_places,
        total_pop = stats.stats.total_population
    )
}
```

## Benefits of Facet Composition

1. **Reusability**: Cache facets are shared across workflows
2. **Modularity**: Each facet does one thing well
3. **Testability**: Facets can be tested in isolation
4. **Flexibility**: Combine facets in different ways for different use cases
5. **Parallelism**: Independent facets can execute concurrently
6. **Maintainability**: Changes to one facet don't affect others

## Available Facet Categories

| Category | Namespace | Description |
|----------|-----------|-------------|
| Cache | `osm.geo.cache.*` | ~250 geographic region caches |
| Operations | `osm.geo.Operations` | Download, tile, routing graph |
| POI | `osm.geo.POI` | Points of interest |
| Boundaries | `osm.geo.Boundaries` | Administrative/natural boundaries |
| Routes | `osm.geo.Routes` | Transportation routes |
| Parks | `osm.geo.Parks` | Parks and protected areas |
| Population | `osm.geo.Population` | Population-based filtering |
| Buildings | `osm.geo.Buildings` | Building footprints |
| Amenities | `osm.geo.Amenities` | Services and facilities |
| Roads | `osm.geo.Roads` | Road network |
| Filters | `osm.geo.Filters` | Radius and type filtering |
| Visualization | `osm.geo.Visualization` | Map rendering |
| TIGER | `osm.geo.TIGER` | US Census voting districts |

## See Also

- [CACHE.md](CACHE.md) - Cache system documentation
- [ROUTES.md](ROUTES.md) - Route extraction
- [PARKS.md](PARKS.md) - Park extraction
- [POPULATION.md](POPULATION.md) - Population filtering
- [BUILDINGS.md](BUILDINGS.md) - Building extraction
- [AMENITIES.md](AMENITIES.md) - Amenity extraction
- [ROADS.md](ROADS.md) - Road extraction
- [VISUALIZATION.md](VISUALIZATION.md) - Map rendering
