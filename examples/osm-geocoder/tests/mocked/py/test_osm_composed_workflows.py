"""Integration tests for all 15 composed workflows in osmworkflows_composed.afl.

Verifies that every workflow compiles correctly and has the expected params,
returns, steps, and cache call targets.  Pure compile-time tests — no MongoDB
or runtime execution required.
"""

from pathlib import Path
from typing import Optional

import pytest

from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

_OSM_AFL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "afl"


def _compile_all() -> dict:
    """Compile all 43 AFL files with osmworkflows_composed.afl as primary."""
    all_afl = sorted(_OSM_AFL_DIR.glob("*.afl"))
    filenames = [f.name for f in all_afl]

    # Put osmworkflows_composed.afl first as primary
    filenames.remove("osmworkflows_composed.afl")
    filenames.insert(0, "osmworkflows_composed.afl")

    entries = []
    for i, name in enumerate(filenames):
        path = _OSM_AFL_DIR / name
        entries.append(
            SourceEntry(
                text=path.read_text(),
                origin=FileOrigin(path=str(path)),
                is_library=(i > 0),
            )
        )

    compiler_input = CompilerInput(
        primary_sources=[entries[0]],
        library_sources=entries[1:],
    )

    parser = AFLParser()
    program_ast, _registry = parser.parse_sources(compiler_input)

    result = validate(program_ast)
    if result.errors:
        messages = "; ".join(str(e) for e in result.errors)
        raise ValueError(f"Validation errors: {messages}")

    return emit_dict(program_ast, include_locations=False)


def _find_wf(node: dict, name: str) -> Optional[dict]:
    """Recursively search compiled program for a workflow by name."""
    for wf in node.get("workflows", []):
        if wf["name"] == name:
            return wf
    for ns in node.get("namespaces", []):
        found = _find_wf(ns, name)
        if found is not None:
            return found
    return None


def _step_call_target(step: dict) -> str:
    """Extract the fully-qualified call target from a step dict."""
    return step["call"]["target"]


def _param_dict(wf: dict) -> dict[str, str]:
    """Return {name: type} for workflow params."""
    return {p["name"]: p["type"] for p in wf.get("params", [])}


def _return_dict(wf: dict) -> dict[str, str]:
    """Return {name: type} for workflow returns."""
    return {r["name"]: r["type"] for r in wf.get("returns", [])}


def _steps(wf: dict) -> list[dict]:
    """Return the list of step dicts from the workflow body."""
    return wf["body"]["steps"]


def _step_names(wf: dict) -> list[str]:
    """Return ordered list of step variable names."""
    return [s["name"] for s in _steps(wf)]


# ---------------------------------------------------------------------------
# Module-scoped fixture — compile once, reuse across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def program():
    """Compiled program from all 43 AFL files."""
    return _compile_all()


# ---------------------------------------------------------------------------
# All 16 workflow names for completeness checks
# ---------------------------------------------------------------------------

ALL_WORKFLOW_NAMES = [
    "VisualizeBicycleRoutes",
    "AnalyzeParks",
    "LargeCitiesMap",
    "TransportOverview",
    "NationalParksAnalysis",
    "CityAnalysis",
    "TransportMap",
    "StateBoundariesWithStats",
    "DiscoverCitiesAndTowns",
    "RegionalAnalysis",
    "ValidateAndSummarize",
    "OsmoseQualityCheck",
    "TransitAnalysis",
    "TransitAccessibility",
    "RoadZoomBuilder",
]

# Workflows that use osm.geo.Operations.Cache(region = $.region)
_OPERATIONS_CACHE_WORKFLOWS = [
    "VisualizeBicycleRoutes",
    "AnalyzeParks",
    "LargeCitiesMap",
    "TransportOverview",
    "NationalParksAnalysis",
    "CityAnalysis",
    "TransportMap",
    "StateBoundariesWithStats",
    "DiscoverCitiesAndTowns",
    "RegionalAnalysis",
    "ValidateAndSummarize",
    "OsmoseQualityCheck",
    "TransitAccessibility",
    "RoadZoomBuilder",
]


class TestComposedWorkflows:
    """Integration tests for all 15 composed workflows."""

    # ------------------------------------------------------------------
    # Smoke / completeness
    # ------------------------------------------------------------------

    def test_all_workflows_compile(self, program):
        """All 43 AFL files compile together without errors."""
        assert program["type"] == "Program"

    def test_all_15_workflows_present(self, program):
        """Every one of the 15 composed workflows exists in the compiled output."""
        for name in ALL_WORKFLOW_NAMES:
            wf = _find_wf(program, name)
            assert wf is not None, f"Workflow {name!r} not found in compiled program"

    # ------------------------------------------------------------------
    # Pattern 1: Cache → Extract → Visualize
    # ------------------------------------------------------------------

    def test_visualize_bicycle_routes(self, program):
        wf = _find_wf(program, "VisualizeBicycleRoutes")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {"map_path": "String", "route_count": "Long"}

        assert len(_steps(wf)) == 3
        assert _step_names(wf) == ["cache", "routes", "map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 2: Cache → Extract → Statistics
    # ------------------------------------------------------------------

    def test_analyze_parks(self, program):
        wf = _find_wf(program, "AnalyzeParks")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {
            "total_parks": "Long",
            "total_area": "Double",
            "national": "Long",
            "state": "Long",
        }

        assert len(_steps(wf)) == 3
        assert _step_names(wf) == ["cache", "parks", "stats"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 3: Cache → Extract → Filter → Visualize
    # ------------------------------------------------------------------

    def test_large_cities_map(self, program):
        wf = _find_wf(program, "LargeCitiesMap")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String", "min_pop": "Long"}
        assert _return_dict(wf) == {"map_path": "String", "city_count": "Long"}

        assert len(_steps(wf)) == 4
        assert _step_names(wf) == ["cache", "cities", "large", "map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 4: Cache → Multiple Extractions → Combine Statistics
    # ------------------------------------------------------------------

    def test_transport_overview(self, program):
        wf = _find_wf(program, "TransportOverview")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {
            "bicycle_km": "Double",
            "hiking_km": "Double",
            "train_km": "Double",
            "bus_routes": "Long",
        }

        assert len(_steps(wf)) == 9
        assert _step_names(wf) == [
            "cache",
            "bicycle", "hiking", "train", "bus",
            "bicycle_stats", "hiking_stats", "train_stats", "bus_stats",
        ]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 5: Cache → Extract → Filter → Statistics → Visualize
    # ------------------------------------------------------------------

    def test_national_parks_analysis(self, program):
        wf = _find_wf(program, "NationalParksAnalysis")
        assert wf is not None

        params = _param_dict(wf)
        assert params == {"region": "String"}
        assert _return_dict(wf) == {
            "map_path": "String",
            "park_count": "Long",
            "total_area": "Double",
            "avg_area": "Double",
        }

        assert len(_steps(wf)) == 5
        assert _step_names(wf) == ["cache", "all_parks", "national", "stats", "map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 6: Parameterized City Analysis
    # ------------------------------------------------------------------

    def test_city_analysis(self, program):
        wf = _find_wf(program, "CityAnalysis")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String", "min_population": "Long"}
        assert _return_dict(wf) == {
            "map_path": "String",
            "large_cities": "Long",
            "total_pop": "Long",
        }

        assert len(_steps(wf)) == 4
        assert _step_names(wf) == ["cache", "cities", "stats", "map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 7: Multi-Layer Visualization
    # ------------------------------------------------------------------

    def test_transport_map(self, program):
        wf = _find_wf(program, "TransportMap")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {"map_path": "String"}

        assert len(_steps(wf)) == 4
        assert _step_names(wf) == ["cache", "bicycle", "hiking", "bicycle_map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 8: Boundary Analysis Pipeline
    # ------------------------------------------------------------------

    def test_state_boundaries_with_stats(self, program):
        wf = _find_wf(program, "StateBoundariesWithStats")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {"map_path": "String", "state_count": "Long"}

        assert len(_steps(wf)) == 3
        assert _step_names(wf) == ["cache", "boundaries", "map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 9: POI Discovery Pipeline
    # ------------------------------------------------------------------

    def test_discover_cities_and_towns(self, program):
        wf = _find_wf(program, "DiscoverCitiesAndTowns")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {
            "map_path": "String",
            "cities": "Long",
            "towns": "Long",
            "villages": "Long",
        }

        assert len(_steps(wf)) == 5
        assert _step_names(wf) == ["cache", "city_data", "town_data", "village_data", "map"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 10: Complete Regional Analysis
    # ------------------------------------------------------------------

    def test_regional_analysis(self, program):
        wf = _find_wf(program, "RegionalAnalysis")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String"}
        assert _return_dict(wf) == {
            "parks_count": "Long",
            "parks_area": "Double",
            "routes_km": "Double",
            "cities_count": "Long",
            "map_path": "String",
        }

        assert len(_steps(wf)) == 8
        assert _step_names(wf) == [
            "cache",
            "parks", "routes", "cities",
            "park_stats", "route_stats", "city_stats",
            "map",
        ]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 11: Cache → Validate → Summary
    # ------------------------------------------------------------------

    def test_validate_and_summarize(self, program):
        wf = _find_wf(program, "ValidateAndSummarize")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String", "output_dir": "String"}
        assert _return_dict(wf) == {
            "total": "Long",
            "valid": "Long",
            "invalid": "Long",
            "output_path": "String",
        }

        assert len(_steps(wf)) == 3
        assert _step_names(wf) == ["cache", "validation", "summary"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 12: Cache → Local Verify → Summary (OSMOSE)
    # ------------------------------------------------------------------

    def test_osmose_quality_check(self, program):
        wf = _find_wf(program, "OsmoseQualityCheck")
        assert wf is not None

        assert _param_dict(wf) == {"region": "String", "output_dir": "String"}
        assert _return_dict(wf) == {
            "total_issues": "Long",
            "geometry_issues": "Long",
            "tag_issues": "Long",
            "reference_issues": "Long",
            "tag_coverage_pct": "Double",
            "output_path": "String",
        }

        assert len(_steps(wf)) == 3
        assert _step_names(wf) == ["cache", "verify", "summary"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 13: GTFS Transit Analysis (no cache step)
    # ------------------------------------------------------------------

    def test_transit_analysis(self, program):
        wf = _find_wf(program, "TransitAnalysis")
        assert wf is not None

        assert _param_dict(wf) == {"gtfs_url": "String"}
        assert _return_dict(wf) == {
            "agency_name": "String",
            "stop_count": "Long",
            "route_count": "Long",
            "trip_count": "Long",
            "has_shapes": "Boolean",
            "stops_path": "String",
            "routes_path": "String",
        }

        assert len(_steps(wf)) == 4
        assert _step_names(wf) == ["dl", "stops", "routes", "stats"]
        # No cache step — first step downloads GTFS feed
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Transit.GTFS.DownloadFeed"

    # ------------------------------------------------------------------
    # Pattern 14: GTFS Transit Accessibility
    # ------------------------------------------------------------------

    def test_transit_accessibility(self, program):
        wf = _find_wf(program, "TransitAccessibility")
        assert wf is not None

        assert _param_dict(wf) == {"gtfs_url": "String", "region": "String"}
        assert _return_dict(wf) == {
            "pct_within_400m": "Double",
            "pct_within_800m": "Double",
            "coverage_pct": "Double",
            "gap_cells": "Long",
            "accessibility_path": "String",
            "coverage_path": "String",
        }

        assert len(_steps(wf)) == 6
        assert _step_names(wf) == ["cache", "dl", "buildings", "stops", "access", "gaps"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Pattern 15: Low-Zoom Road Infrastructure Builder
    # ------------------------------------------------------------------

    def test_road_zoom_builder(self, program):
        wf = _find_wf(program, "RoadZoomBuilder")
        assert wf is not None

        assert _param_dict(wf) == {
            "region": "String",
            "output_dir": "String",
            "max_concurrent": "Long",
        }
        assert _return_dict(wf) == {
            "total_edges": "Long",
            "selected_edges": "Long",
            "zoom_distribution": "String",
            "csv_path": "String",
            "metrics_path": "String",
        }

        assert len(_steps(wf)) == 3
        assert _step_names(wf) == ["cache", "graph", "zoom"]
        assert _step_call_target(_steps(wf)[0]) == "osm.geo.Operations.Cache"

    # ------------------------------------------------------------------
    # Cross-cutting: all generic cache workflows use Operations.Cache
    # ------------------------------------------------------------------

    def test_generic_cache_workflows_use_operations_cache(self, program):
        """Regression guard: 14 workflows must use osm.geo.Operations.Cache."""
        for name in _OPERATIONS_CACHE_WORKFLOWS:
            wf = _find_wf(program, name)
            assert wf is not None, f"{name} not found"
            cache_step = _steps(wf)[0]
            assert cache_step["name"] == "cache", (
                f"{name}: first step should be 'cache', got {cache_step['name']!r}"
            )
            assert _step_call_target(cache_step) == "osm.geo.Operations.Cache", (
                f"{name}: cache step should target osm.geo.Operations.Cache, "
                f"got {_step_call_target(cache_step)!r}"
            )
