"""Tests for census-us handler dispatch adapter pattern.

Verifies that each handler module's handle() function dispatches correctly
using the _facet_name key, that _DISPATCH dicts have the expected keys,
and that register_handlers() calls runner.register_handler the expected
number of times.
"""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CENSUS_DIR = str(Path(__file__).resolve().parent.parent)


def _census_import(module_name: str):
    """Import a census-us handlers submodule, ensuring correct sys.path."""
    if CENSUS_DIR in sys.path:
        sys.path.remove(CENSUS_DIR)
    sys.path.insert(0, CENSUS_DIR)

    full_name = f"handlers.{module_name}"

    # If module is already loaded from the right location, return it
    if full_name in sys.modules:
        mod = sys.modules[full_name]
        mod_file = getattr(mod, "__file__", "")
        if mod_file and "census-us" in mod_file:
            return mod
        del sys.modules[full_name]

    # Ensure the handlers package itself is from census-us
    if "handlers" in sys.modules:
        pkg = sys.modules["handlers"]
        pkg_file = getattr(pkg, "__file__", "")
        if pkg_file and "census-us" not in pkg_file:
            stale = [k for k in sys.modules
                     if k == "handlers" or k.startswith("handlers.")]
            for k in stale:
                del sys.modules[k]

    return importlib.import_module(full_name)


class TestDownloadHandlers:
    def test_dispatch_keys(self):
        mod = _census_import("downloads.download_handlers")
        assert len(mod._DISPATCH) == 2
        assert "census.Operations.DownloadACS" in mod._DISPATCH
        assert "census.Operations.DownloadTIGER" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _census_import("downloads.download_handlers")
        mock_file = {
            "url": "https://example.com/acs.zip",
            "path": "/tmp/acs.zip",
            "date": "2026-01-01T00:00:00+00:00",
            "size": 1024,
            "wasInCache": True,
        }
        with patch.object(mod, "download_acs", return_value=mock_file):
            result = mod.handle({
                "_facet_name": "census.Operations.DownloadACS",
                "state_fips": "01",
            })
        assert isinstance(result, dict)
        assert "file" in result
        assert result["file"]["wasInCache"] is True

    def test_handle_unknown_facet(self):
        mod = _census_import("downloads.download_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "census.Operations.NonExistent"})

    def test_register_handlers(self):
        mod = _census_import("downloads.download_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 2


class TestACSHandlers:
    def test_dispatch_keys(self):
        mod = _census_import("acs.acs_handlers")
        assert len(mod._DISPATCH) == 5
        for key in mod._DISPATCH:
            assert key.startswith("census.ACS.")

    def test_handle_dispatches(self):
        mod = _census_import("acs.acs_handlers")
        result = mod.handle({
            "_facet_name": "census.ACS.ExtractPopulation",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"]["table_id"] == "B01003"

    def test_handle_unknown_facet(self):
        mod = _census_import("acs.acs_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "census.ACS.NonExistent"})

    def test_register_handlers(self):
        mod = _census_import("acs.acs_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 5

    def test_extract_population(self):
        mod = _census_import("acs.acs_handlers")
        result = mod.handle({
            "_facet_name": "census.ACS.ExtractPopulation",
            "file": {"path": ""},
            "state_fips": "01",
            "geo_level": "county",
        })
        assert result["result"]["table_id"] == "B01003"
        assert result["result"]["geography_level"] == "county"

    def test_extract_income(self):
        mod = _census_import("acs.acs_handlers")
        result = mod.handle({
            "_facet_name": "census.ACS.ExtractIncome",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["table_id"] == "B19013"

    def test_extract_housing(self):
        mod = _census_import("acs.acs_handlers")
        result = mod.handle({
            "_facet_name": "census.ACS.ExtractHousing",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["table_id"] == "B25001"

    def test_extract_education(self):
        mod = _census_import("acs.acs_handlers")
        result = mod.handle({
            "_facet_name": "census.ACS.ExtractEducation",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["table_id"] == "B15003"

    def test_extract_commuting(self):
        mod = _census_import("acs.acs_handlers")
        result = mod.handle({
            "_facet_name": "census.ACS.ExtractCommuting",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["table_id"] == "B08301"


class TestTIGERHandlers:
    def test_dispatch_keys(self):
        mod = _census_import("tiger.tiger_handlers")
        assert len(mod._DISPATCH) == 4
        for key in mod._DISPATCH:
            assert key.startswith("census.TIGER.")

    def test_handle_dispatches(self):
        mod = _census_import("tiger.tiger_handlers")
        result = mod.handle({
            "_facet_name": "census.TIGER.ExtractCounties",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"]["format"] == "GeoJSON"

    def test_handle_unknown_facet(self):
        mod = _census_import("tiger.tiger_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "census.TIGER.NonExistent"})

    def test_register_handlers(self):
        mod = _census_import("tiger.tiger_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 4

    def test_extract_counties(self):
        mod = _census_import("tiger.tiger_handlers")
        result = mod.handle({
            "_facet_name": "census.TIGER.ExtractCounties",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["geography_level"] == "COUNTY"

    def test_extract_tracts(self):
        mod = _census_import("tiger.tiger_handlers")
        result = mod.handle({
            "_facet_name": "census.TIGER.ExtractTracts",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["geography_level"] == "TRACT"

    def test_extract_block_groups(self):
        mod = _census_import("tiger.tiger_handlers")
        result = mod.handle({
            "_facet_name": "census.TIGER.ExtractBlockGroups",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["geography_level"] == "BG"

    def test_extract_places(self):
        mod = _census_import("tiger.tiger_handlers")
        result = mod.handle({
            "_facet_name": "census.TIGER.ExtractPlaces",
            "file": {"path": ""},
            "state_fips": "01",
        })
        assert result["result"]["geography_level"] == "PLACE"


class TestJoinGeoDensity:
    """Test population density computation in join_geo."""

    def test_density_computed_from_aland_and_population(self, tmp_path):
        mod = _census_import("summary.summary_builder")
        # ACS CSV with population estimate
        acs_csv = tmp_path / "pop.csv"
        acs_csv.write_text("GEOID,B01003_001E,NAME\n0500000US01001,50000,Autauga\n")
        # TIGER GeoJSON with ALAND (100 km² = 1e8 m²)
        tiger_geojson = tmp_path / "counties.geojson"
        tiger_geojson.write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"GEOID": "0500000US01001", "ALAND": 100000000},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }],
        }))
        result = mod.join_geo(str(acs_csv), str(tiger_geojson))
        assert result.feature_count == 1
        # Read output and check density
        with open(result.output_path) as f:
            data = json.load(f)
        props = data["features"][0]["properties"]
        # 50000 / (1e8 / 1e6) = 50000 / 100 = 500.0
        assert props["population_density_km2"] == 500.0

    def test_density_skipped_when_aland_missing(self, tmp_path):
        mod = _census_import("summary.summary_builder")
        acs_csv = tmp_path / "pop.csv"
        acs_csv.write_text("GEOID,B01003_001E,NAME\nGEO1,1000,Place\n")
        tiger_geojson = tmp_path / "geo.geojson"
        tiger_geojson.write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"GEOID": "GEO1"},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }],
        }))
        result = mod.join_geo(str(acs_csv), str(tiger_geojson))
        with open(result.output_path) as f:
            data = json.load(f)
        props = data["features"][0]["properties"]
        assert "population_density_km2" not in props

    def test_density_zero_when_aland_is_zero(self, tmp_path):
        mod = _census_import("summary.summary_builder")
        acs_csv = tmp_path / "pop.csv"
        acs_csv.write_text("GEOID,B01003_001E,NAME\nGEO1,500,Place\n")
        tiger_geojson = tmp_path / "geo.geojson"
        tiger_geojson.write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"GEOID": "GEO1", "ALAND": 0},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }],
        }))
        result = mod.join_geo(str(acs_csv), str(tiger_geojson))
        with open(result.output_path) as f:
            data = json.load(f)
        props = data["features"][0]["properties"]
        assert props["population_density_km2"] == 0.0


class TestSummaryHandlers:
    def test_dispatch_keys(self):
        mod = _census_import("summary.summary_handlers")
        assert len(mod._DISPATCH) == 2
        assert "census.Summary.JoinGeo" in mod._DISPATCH
        assert "census.Summary.SummarizeState" in mod._DISPATCH

    def test_handle_join_geo(self):
        mod = _census_import("summary.summary_handlers")
        result = mod.handle({
            "_facet_name": "census.Summary.JoinGeo",
            "acs_path": "",
            "tiger_path": "",
        })
        assert isinstance(result, dict)
        assert "result" in result

    def test_handle_summarize_state(self):
        mod = _census_import("summary.summary_handlers")
        empty_acs = {
            "table_id": "", "output_path": "", "record_count": 0,
            "geography_level": "", "year": "", "extraction_date": "",
        }
        result = mod.handle({
            "_facet_name": "census.Summary.SummarizeState",
            "population": empty_acs,
            "income": empty_acs,
            "housing": empty_acs,
            "education": empty_acs,
            "commuting": empty_acs,
        })
        assert isinstance(result, dict)
        assert result["result"]["tables_joined"] == 0

    def test_handle_unknown_facet(self):
        mod = _census_import("summary.summary_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "census.Summary.NonExistent"})

    def test_register_handlers(self):
        mod = _census_import("summary.summary_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == 2


class TestInitRegistryHandlers:
    def test_register_all_registry_handlers(self):
        mod = _census_import("__init__")
        runner = MagicMock()
        mod.register_all_registry_handlers(runner)
        # 2 downloads + 5 ACS + 4 TIGER + 2 summary = 13
        assert runner.register_handler.call_count == 13

    def test_register_all_handlers(self):
        mod = _census_import("__init__")
        poller = MagicMock()
        mod.register_all_handlers(poller)
        assert poller.register.call_count == 13
