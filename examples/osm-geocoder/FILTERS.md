# OSM Radius Filters

Filter OSM boundary polygons by their equivalent circular radius.

## Concept

The **equivalent radius** converts any polygon to a comparable size metric by computing the radius of a circle with the same area:

```
radius = √(area / π)
```

This allows filtering boundaries by size regardless of shape complexity.

## AFL Facets

All filter facets are defined in `osmfilters.afl` under the `osm.geo.Filters` namespace.

### FilterByRadius

Filter GeoJSON features by equivalent radius.

```afl
event facet FilterByRadius(
    input_path: String,       // Path to input GeoJSON file
    radius: Double,           // Threshold value
    unit: String = "kilometers",  // meters, kilometers, miles
    operator: String = "gte"  // gt, gte, lt, lte, eq, ne
) => (result: FilterResult)
```

### FilterByRadiusRange

Filter GeoJSON features within an inclusive radius range.

```afl
event facet FilterByRadiusRange(
    input_path: String,
    min_radius: Double,       // Lower bound (inclusive)
    max_radius: Double,       // Upper bound (inclusive)
    unit: String = "kilometers"
) => (result: FilterResult)
```

### FilterByTypeAndRadius

Filter GeoJSON features by boundary type and radius.

```afl
event facet FilterByTypeAndRadius(
    input_path: String,
    boundary_type: String,    // water, forest, park, etc.
    radius: Double,
    unit: String = "kilometers",
    operator: String = "gte"
) => (result: FilterResult)
```

### ExtractAndFilterByRadius

Extract boundaries from PBF and filter by radius in one step.

```afl
event facet ExtractAndFilterByRadius(
    cache: OSMCache,          // OSM cache with path to PBF file
    admin_levels: [Long],     // Admin levels to extract (2=country, 4=state, etc.)
    natural_types: [String],  // Natural types (water, forest, park)
    radius: Double,
    unit: String = "kilometers",
    operator: String = "gte"
) => (result: FilterResult)
```

## Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `gt` | Greater than | radius > 10km |
| `gte` | Greater than or equal | radius >= 10km |
| `lt` | Less than | radius < 10km |
| `lte` | Less than or equal | radius <= 10km |
| `eq` | Equal (1% tolerance) | radius ≈ 10km |
| `ne` | Not equal | radius ≠ 10km |
| `between` | Inclusive range | 5km ≤ radius ≤ 20km |

## Units

| Unit | Aliases |
|------|---------|
| `meters` | `m`, `meter` |
| `kilometers` | `km`, `kilometer` |
| `miles` | `mi`, `mile` |

## FilterResult Schema

```afl
schema FilterResult {
    output_path: String       // Path to filtered GeoJSON
    feature_count: Long       // Features after filtering
    original_count: Long      // Features before filtering
    boundary_type: String     // Type filter applied (or "all")
    filter_applied: String    // Human-readable filter description
    format: String            // Always "GeoJSON"
    extraction_date: String   // ISO timestamp
}
```

## Usage Examples

### Filter large lakes (>= 5km radius)

```afl
workflow LargeLakes(input: String) => (result: FilterResult) andThen {
    filtered = FilterByRadius(
        input_path = $.input,
        radius = 5.0,
        unit = "kilometers",
        operator = "gte"
    )
    yield LargeLakes(result = filtered.result)
}
```

### Filter medium-sized parks (1-10km radius)

```afl
workflow MediumParks(input: String) => (result: FilterResult) andThen {
    filtered = FilterByRadiusRange(
        input_path = $.input,
        min_radius = 1.0,
        max_radius = 10.0,
        unit = "kilometers"
    )
    yield MediumParks(result = filtered.result)
}
```

### Extract and filter state boundaries from PBF

```afl
workflow LargeStates() => (result: FilterResult)
    with Germany()
andThen {
    filtered = ExtractAndFilterByRadius(
        cache = Germany.cache,
        admin_levels = [4],
        natural_types = [],
        radius = 50.0,
        unit = "kilometers",
        operator = "gte"
    )
    yield LargeStates(result = filtered.result)
}
```

## Area Calculation

The module uses pyproj with an Albers Equal Area projection for accurate geodesic area measurements. When pyproj is unavailable, it falls back to a spherical approximation using coordinate scaling.

The projection is centered on each polygon's centroid for maximum accuracy:

```
+proj=aea +lat_1={lat-5} +lat_2={lat+5} +lat_0={lat} +lon_0={lon}
```

## Dependencies

- `shapely>=2.0` - Required for geometry operations
- `pyproj>=3.0` - Recommended for accurate geodesic area (optional, falls back to approximation)

## Running Tests

```bash
# From repo root
pytest examples/osm-geocoder/test_filters.py -v
```
