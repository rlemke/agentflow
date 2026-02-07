# OSM Geocoder Integration Tests

Real end-to-end integration tests that compile from `.afl` source files,
persist to MongoDB, and run through the AgentPoller task queue pipeline.

## Prerequisites

- **MongoDB** running locally (or configured via `afl.config.json`)
- **Python packages**: `pip install -e ".[dev,mongodb]"`

### Optional (for data pipeline tests)

- **requests**: HTTP downloads from Geofabrik
- **osmium**: PBF file parsing (`pip install osmium`)
- **folium**: Map rendering (`pip install folium`)
- **GraphHopper JAR**: Routing graph builds (set `GRAPHHOPPER_JAR` env var)

## Running

```bash
# All integration tests (skips tests with missing optional deps):
pytest examples/osm-geocoder/integration/ -v --mongodb

# Just AddOne (no external deps beyond MongoDB):
pytest examples/osm-geocoder/integration/test_addone.py -v --mongodb

# Region resolution (no network, just MongoDB + pure Python resolver):
pytest examples/osm-geocoder/integration/test_region_resolution.py -v --mongodb

# Population pipeline (needs network + osmium):
pytest examples/osm-geocoder/integration/test_population_pipeline.py -v --mongodb

# City routing (needs network + osmium + folium + GraphHopper):
pytest examples/osm-geocoder/integration/test_city_routing.py -v --mongodb
```

Without `--mongodb`, all tests are skipped.

## Test Descriptions

| Test | Steps | External Deps | Description |
|------|-------|---------------|-------------|
| `test_addone.py` | 1 | None | Compile AFL → MongoStore → AgentPoller → AddOne handler |
| `test_region_resolution.py` | 1 | None | Multi-file AFL compilation + real region resolver |
| `test_population_pipeline.py` | 4 | requests, osmium | Geofabrik download → osmium extraction → filtering → stats |
| `test_city_routing.py` | 9 | requests, osmium, folium, GraphHopper | Full CityRouteMap pipeline |

## Architecture

```
conftest.py          → MongoDB fixtures (MongoStore, Evaluator, AgentPoller)
helpers.py           → compile_afl_files(), extract_workflow(), run_to_completion()
afl/*.afl            → Test-specific AFL source files
test_*.py            → Integration test modules
```

The `run_to_completion()` helper implements the core loop:
1. `evaluator.execute()` — start the workflow, pause at first event
2. `poller.poll_once()` — claim task, dispatch to handler, continue step
3. `evaluator.resume()` — resume workflow after event completion
4. Repeat until COMPLETED or ERROR
