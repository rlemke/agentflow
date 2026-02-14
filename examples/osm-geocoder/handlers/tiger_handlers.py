"""Census TIGER/Line event facet handlers for voting district data.

Handles voting district events defined in osmvoting.afl under census.tiger.
"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .tiger_downloader import (
    DISTRICT_CONGRESSIONAL,
    DISTRICT_STATE_HOUSE,
    DISTRICT_STATE_SENATE,
    DISTRICT_VOTING_PRECINCT,
    FIPS_TO_STATE,
    STATE_FIPS,
    download_congressional_districts,
    download_state_house_districts,
    download_state_senate_districts,
    download_voting_precincts,
    extract_shapefile,
    resolve_state_fips,
)

log = logging.getLogger(__name__)

NAMESPACE_DISTRICTS = "census.tiger.Districts"
NAMESPACE_PROCESSING = "census.tiger.Processing"
NAMESPACE_WORKFLOWS = "census.tiger.Workflows"

# Check for ogr2ogr (GDAL) availability
try:
    result = subprocess.run(
        ["ogr2ogr", "--version"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    HAS_OGR2OGR = result.returncode == 0
except (FileNotFoundError, subprocess.TimeoutExpired):
    HAS_OGR2OGR = False

# Check for geopandas availability (fallback for shapefile conversion)
try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


def _district_type_name(district_type: str) -> str:
    """Get human-readable name for a district type."""
    names = {
        DISTRICT_CONGRESSIONAL: "Congressional Districts",
        DISTRICT_STATE_SENATE: "State Senate Districts",
        DISTRICT_STATE_HOUSE: "State House Districts",
        DISTRICT_VOTING_PRECINCT: "Voting Precincts",
    }
    return names.get(district_type, district_type)


def _make_congressional_handler(facet_name: str):
    """Create handler for CongressionalDistricts event facet."""

    def handler(payload: dict) -> dict:
        year = payload.get("year", 2023)
        congress_number = payload.get("congress_number", 118)

        log.info("%s downloading CD for %dth Congress (year %d)",
                 facet_name, congress_number, year)

        try:
            cache = download_congressional_districts(year, congress_number)
            return {"cache": cache}
        except Exception as e:
            log.error("Failed to download Congressional Districts: %s", e)
            return {
                "cache": {
                    "url": "",
                    "path": "",
                    "date": datetime.now(timezone.utc).isoformat(),
                    "size": 0,
                    "wasInCache": False,
                    "year": year,
                    "district_type": DISTRICT_CONGRESSIONAL,
                    "state_fips": "US",
                }
            }

    return handler


def _make_state_senate_handler(facet_name: str):
    """Create handler for StateSenateDistricts event facet."""

    def handler(payload: dict) -> dict:
        state_fips = payload.get("state_fips", "")
        year = payload.get("year", 2023)

        log.info("%s downloading SLDU for state %s (year %d)",
                 facet_name, state_fips, year)

        try:
            cache = download_state_senate_districts(state_fips, year)
            return {"cache": cache}
        except Exception as e:
            log.error("Failed to download State Senate Districts: %s", e)
            return {
                "cache": {
                    "url": "",
                    "path": "",
                    "date": datetime.now(timezone.utc).isoformat(),
                    "size": 0,
                    "wasInCache": False,
                    "year": year,
                    "district_type": DISTRICT_STATE_SENATE,
                    "state_fips": state_fips,
                }
            }

    return handler


def _make_state_house_handler(facet_name: str):
    """Create handler for StateHouseDistricts event facet."""

    def handler(payload: dict) -> dict:
        state_fips = payload.get("state_fips", "")
        year = payload.get("year", 2023)

        log.info("%s downloading SLDL for state %s (year %d)",
                 facet_name, state_fips, year)

        try:
            cache = download_state_house_districts(state_fips, year)
            return {"cache": cache}
        except Exception as e:
            log.error("Failed to download State House Districts: %s", e)
            return {
                "cache": {
                    "url": "",
                    "path": "",
                    "date": datetime.now(timezone.utc).isoformat(),
                    "size": 0,
                    "wasInCache": False,
                    "year": year,
                    "district_type": DISTRICT_STATE_HOUSE,
                    "state_fips": state_fips,
                }
            }

    return handler


def _make_voting_precincts_handler(facet_name: str):
    """Create handler for VotingPrecincts event facet."""

    def handler(payload: dict) -> dict:
        state_fips = payload.get("state_fips", "")
        year = payload.get("year", 2020)

        log.info("%s downloading VTD for state %s (year %d)",
                 facet_name, state_fips, year)

        try:
            cache = download_voting_precincts(state_fips, year)
            return {"cache": cache}
        except Exception as e:
            log.error("Failed to download Voting Precincts: %s", e)
            return {
                "cache": {
                    "url": "",
                    "path": "",
                    "date": datetime.now(timezone.utc).isoformat(),
                    "size": 0,
                    "wasInCache": False,
                    "year": year,
                    "district_type": DISTRICT_VOTING_PRECINCT,
                    "state_fips": state_fips,
                }
            }

    return handler


def _make_shapefile_to_geojson_handler(facet_name: str):
    """Create handler for ShapefileToGeoJSON event facet."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        zip_path = cache.get("path", "")
        district_type = cache.get("district_type", "")
        state_fips = cache.get("state_fips", "US")
        year = cache.get("year", 0)

        log.info("%s converting %s to GeoJSON", facet_name, zip_path)

        if not zip_path or not os.path.exists(zip_path):
            return {
                "result": {
                    "output_path": "",
                    "feature_count": 0,
                    "district_type": _district_type_name(district_type),
                    "state": FIPS_TO_STATE.get(state_fips, state_fips),
                    "year": year,
                    "format": "GeoJSON",
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                }
            }

        try:
            # Extract the shapefile from ZIP
            extract_dir = os.path.dirname(zip_path)
            shp_path = extract_shapefile(zip_path, extract_dir)

            # Generate output path
            base_name = Path(shp_path).stem
            output_path = os.path.join(extract_dir, f"{base_name}.geojson")

            # Convert shapefile to GeoJSON
            feature_count = _convert_shapefile_to_geojson(shp_path, output_path)

            return {
                "result": {
                    "output_path": output_path,
                    "feature_count": feature_count,
                    "district_type": _district_type_name(district_type),
                    "state": FIPS_TO_STATE.get(state_fips, state_fips),
                    "year": year,
                    "format": "GeoJSON",
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                }
            }
        except Exception as e:
            log.error("Failed to convert shapefile: %s", e)
            return {
                "result": {
                    "output_path": "",
                    "feature_count": 0,
                    "district_type": _district_type_name(district_type),
                    "state": FIPS_TO_STATE.get(state_fips, state_fips),
                    "year": year,
                    "format": "GeoJSON",
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                }
            }

    return handler


def _convert_shapefile_to_geojson(shp_path: str, output_path: str) -> int:
    """Convert a shapefile to GeoJSON.

    Uses ogr2ogr if available, falls back to geopandas.

    Returns:
        Number of features converted
    """
    if HAS_OGR2OGR:
        return _convert_with_ogr2ogr(shp_path, output_path)
    elif HAS_GEOPANDAS:
        return _convert_with_geopandas(shp_path, output_path)
    else:
        raise RuntimeError(
            "No shapefile conversion tool available. "
            "Install GDAL (ogr2ogr) or geopandas."
        )


def _convert_with_ogr2ogr(shp_path: str, output_path: str) -> int:
    """Convert shapefile to GeoJSON using ogr2ogr."""
    cmd = [
        "ogr2ogr",
        "-f", "GeoJSON",
        "-t_srs", "EPSG:4326",  # Ensure WGS84
        output_path,
        shp_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ogr2ogr failed: {result.stderr}")

    # Count features
    with open(output_path, "r") as f:
        geojson = json.load(f)
    return len(geojson.get("features", []))


def _convert_with_geopandas(shp_path: str, output_path: str) -> int:
    """Convert shapefile to GeoJSON using geopandas."""
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs("EPSG:4326")  # Ensure WGS84
    gdf.to_file(output_path, driver="GeoJSON")
    return len(gdf)


def _make_state_fips_handler(facet_name: str):
    """Create handler for StateFIPS facet."""

    def handler(payload: dict) -> dict:
        state = payload.get("state", "")

        try:
            fips = resolve_state_fips(state)
            return {"fips": fips}
        except ValueError as e:
            log.error("Failed to resolve state FIPS: %s", e)
            return {"fips": ""}

    return handler


def _make_filter_districts_handler(facet_name: str):
    """Create handler for FilterDistricts event facet."""

    def handler(payload: dict) -> dict:
        input_path = payload.get("input_path", "")
        attribute = payload.get("attribute", "")
        value = payload.get("value", "")

        log.info("%s filtering %s where %s=%s",
                 facet_name, input_path, attribute, value)

        if not input_path or not os.path.exists(input_path):
            return {
                "result": {
                    "output_path": "",
                    "feature_count": 0,
                    "district_type": "",
                    "state": "",
                    "year": 0,
                    "format": "GeoJSON",
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                }
            }

        try:
            with open(input_path, "r") as f:
                geojson = json.load(f)

            features = geojson.get("features", [])
            filtered = [
                f for f in features
                if f.get("properties", {}).get(attribute) == value
            ]

            # Generate output path
            input_p = Path(input_path)
            output_path = str(input_p.with_stem(f"{input_p.stem}_{attribute}_{value}"))

            output_geojson = {
                "type": "FeatureCollection",
                "features": filtered,
            }

            with open(output_path, "w") as f:
                json.dump(output_geojson, f)

            return {
                "result": {
                    "output_path": output_path,
                    "feature_count": len(filtered),
                    "district_type": f"filtered ({attribute}={value})",
                    "state": "",
                    "year": 0,
                    "format": "GeoJSON",
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                }
            }
        except Exception as e:
            log.error("Failed to filter districts: %s", e)
            return {
                "result": {
                    "output_path": "",
                    "feature_count": 0,
                    "district_type": "",
                    "state": "",
                    "year": 0,
                    "format": "GeoJSON",
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                }
            }

    return handler


# Event facet definitions for handler registration
TIGER_FACETS = [
    # District download facets
    (NAMESPACE_DISTRICTS, "CongressionalDistricts", _make_congressional_handler),
    (NAMESPACE_DISTRICTS, "StateSenateDistricts", _make_state_senate_handler),
    (NAMESPACE_DISTRICTS, "StateHouseDistricts", _make_state_house_handler),
    (NAMESPACE_DISTRICTS, "VotingPrecincts", _make_voting_precincts_handler),
    # Processing facets
    (NAMESPACE_PROCESSING, "ShapefileToGeoJSON", _make_shapefile_to_geojson_handler),
    (NAMESPACE_PROCESSING, "FilterDistricts", _make_filter_districts_handler),
    # Workflow helper facets
    (NAMESPACE_WORKFLOWS, "StateFIPS", _make_state_fips_handler),
]


def register_tiger_handlers(poller) -> None:
    """Register all TIGER event facet handlers with the poller."""
    for namespace, facet_name, handler_factory in TIGER_FACETS:
        qualified_name = f"{namespace}.{facet_name}"
        poller.register(qualified_name, handler_factory(facet_name))
        log.debug("Registered TIGER handler: %s", qualified_name)


# RegistryRunner dispatch adapter
_DISPATCH: dict[str, callable] = {}


def _build_dispatch() -> None:
    for namespace, facet_name, handler_factory in TIGER_FACETS:
        _DISPATCH[f"{namespace}.{facet_name}"] = handler_factory(facet_name)


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
