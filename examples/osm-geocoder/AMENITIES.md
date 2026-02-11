# Amenity Extraction

Extract amenities (points of interest with services) from OSM data with automatic categorization.

## Features

- **Category classification**: Food, shopping, services, healthcare, education, entertainment, transport
- **Detailed metadata**: Name, opening hours, phone, website, brand, cuisine
- **Search capability**: Filter amenities by name pattern (regex)
- **Statistics**: Count amenities by category with metadata coverage

## AFL Facets

```afl
namespace osm.geo.Amenities {
    // General extraction
    event facet ExtractAmenities(cache: OSMCache, category: String = "all") => (result: AmenityResult)

    // Food & Drink
    event facet FoodAndDrink(cache: OSMCache) => (result: AmenityResult)
    event facet Restaurants(cache: OSMCache) => (result: AmenityResult)
    event facet Cafes(cache: OSMCache) => (result: AmenityResult)
    event facet Bars(cache: OSMCache) => (result: AmenityResult)
    event facet FastFood(cache: OSMCache) => (result: AmenityResult)

    // Shopping
    event facet Shopping(cache: OSMCache) => (result: AmenityResult)
    event facet Supermarkets(cache: OSMCache) => (result: AmenityResult)

    // Services
    event facet Banks(cache: OSMCache) => (result: AmenityResult)
    event facet ATMs(cache: OSMCache) => (result: AmenityResult)
    event facet PostOffices(cache: OSMCache) => (result: AmenityResult)
    event facet FuelStations(cache: OSMCache) => (result: AmenityResult)
    event facet ChargingStations(cache: OSMCache) => (result: AmenityResult)
    event facet Parking(cache: OSMCache) => (result: AmenityResult)

    // Healthcare
    event facet Healthcare(cache: OSMCache) => (result: AmenityResult)
    event facet Hospitals(cache: OSMCache) => (result: AmenityResult)
    event facet Clinics(cache: OSMCache) => (result: AmenityResult)
    event facet Pharmacies(cache: OSMCache) => (result: AmenityResult)
    event facet Dentists(cache: OSMCache) => (result: AmenityResult)

    // Education
    event facet Education(cache: OSMCache) => (result: AmenityResult)
    event facet Schools(cache: OSMCache) => (result: AmenityResult)
    event facet Universities(cache: OSMCache) => (result: AmenityResult)
    event facet Libraries(cache: OSMCache) => (result: AmenityResult)

    // Entertainment
    event facet Entertainment(cache: OSMCache) => (result: AmenityResult)
    event facet Cinemas(cache: OSMCache) => (result: AmenityResult)
    event facet Theatres(cache: OSMCache) => (result: AmenityResult)

    // Statistics and filtering
    event facet AmenityStatistics(input_path: String) => (stats: AmenityStats)
    event facet SearchAmenities(input_path: String, name_pattern: String) => (result: AmenityResult)
    event facet FilterByCategory(input_path: String, category: String) => (result: AmenityResult)
}
```

## Result Schemas

```afl
schema AmenityResult {
    output_path: String
    feature_count: Long
    amenity_category: String
    amenity_types: String
    format: String
    extraction_date: String
}

schema AmenityStats {
    total_amenities: Long
    food: Long
    shopping: Long
    services: Long
    healthcare: Long
    education: Long
    entertainment: Long
    transport: Long
    other: Long
    with_name: Long
    with_opening_hours: Long
}
```

## Amenity Categories

| Category | OSM Tags |
|----------|----------|
| Food | `restaurant`, `cafe`, `bar`, `pub`, `fast_food`, `food_court`, `ice_cream`, `biergarten` |
| Shopping | `supermarket`, `convenience`, `mall`, `department_store`, `clothes`, `shoes`, `electronics` + any `shop=*` |
| Services | `bank`, `atm`, `post_office`, `fuel`, `car_wash`, `car_rental`, `charging_station`, `parking` |
| Healthcare | `hospital`, `clinic`, `doctors`, `dentist`, `pharmacy`, `veterinary` |
| Education | `school`, `university`, `college`, `library`, `kindergarten` |
| Entertainment | `cinema`, `theatre`, `nightclub`, `casino`, `arts_centre` |
| Transport | `bus_station`, `ferry_terminal`, `taxi` |

## Example Workflow

```afl
workflow FindRestaurants(region: String = "Liechtenstein")
    => (map_path: String, restaurant_count: Long) andThen {

    // Stage 1: Get cached region data
    cache = osm.geo.Operations.Cache(region = $.region)

    // Stage 2: Extract restaurants
    restaurants = osm.geo.Amenities.Restaurants(cache = cache.cache)

    // Stage 3: Visualize on map
    map = osm.geo.Visualization.RenderMap(
        geojson_path = restaurants.result.output_path,
        title = "Restaurants",
        color = "#e74c3c"
    )

    yield FindRestaurants(
        map_path = map.result.output_path,
        restaurant_count = restaurants.result.feature_count
    )
}
```

## Search Example

```afl
workflow FindCoffeeShops(region: String = "Liechtenstein")
    => (result_path: String, count: Long) andThen {

    cache = osm.geo.Operations.Cache(region = $.region)
    cafes = osm.geo.Amenities.Cafes(cache = cache.cache)

    // Search by name pattern (regex)
    starbucks = osm.geo.Amenities.SearchAmenities(
        input_path = cafes.result.output_path,
        name_pattern = "(?i)starbucks|costa|nero"
    )

    yield FindCoffeeShops(
        result_path = starbucks.result.output_path,
        count = starbucks.result.feature_count
    )
}
```

## GeoJSON Output

Each amenity feature includes:

```json
{
  "type": "Feature",
  "properties": {
    "osm_id": 12345678,
    "osm_type": "node",
    "amenity": "restaurant",
    "shop": "",
    "category": "food",
    "name": "La Trattoria",
    "opening_hours": "Mo-Sa 11:00-22:00",
    "phone": "+1-555-0123",
    "website": "https://example.com",
    "cuisine": "italian",
    "brand": ""
  },
  "geometry": {
    "type": "Point",
    "coordinates": [9.5209, 47.1410]
  }
}
```

## Dependencies

Amenity extraction requires:
- `pyosmium` - For parsing OSM PBF files

Optional; handlers return empty results if unavailable.
