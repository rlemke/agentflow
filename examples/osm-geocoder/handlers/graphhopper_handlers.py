# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""GraphHopper routing graph handlers.

This module provides handlers for building and managing GraphHopper routing
graphs from OSM cache data. It supports multiple routing profiles and caches
built graphs to avoid unnecessary rebuilds.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime
from typing import Any

from afl.runtime.storage import get_storage_backend

# GraphHopper version used for builds
GRAPHHOPPER_VERSION = "8.0"

# Supported routing profiles
PROFILES = ["car", "bike", "foot", "motorcycle", "truck", "hike", "mtb", "racingbike"]

# Default GraphHopper JAR location (can be overridden via environment)
GRAPHHOPPER_JAR = os.environ.get(
    "GRAPHHOPPER_JAR",
    os.path.expanduser("~/.graphhopper/graphhopper-web.jar")
)

# Base directory for storing routing graphs
GRAPH_BASE_DIR = os.environ.get(
    "GRAPHHOPPER_GRAPH_DIR",
    os.path.expanduser("~/.graphhopper/graphs")
)
_storage = get_storage_backend(GRAPH_BASE_DIR)


def _get_graph_dir(osm_path: str, profile: str) -> str:
    """Generate the graph directory path for an OSM file and profile."""
    # Use the OSM filename (without extension) plus profile
    osm_basename = os.path.splitext(_storage.basename(osm_path))[0]
    return _storage.join(GRAPH_BASE_DIR, f"{osm_basename}-{profile}")


def _get_dir_size(path: str) -> int:
    """Get the total size of a directory in bytes."""
    total = 0
    if _storage.exists(path):
        for dirpath, _dirnames, filenames in _storage.walk(path):
            for f in filenames:
                fp = _storage.join(dirpath, f)
                if _storage.isfile(fp):
                    total += _storage.getsize(fp)
    return total


def _get_modification_date(path: str) -> str:
    """Get the modification date of a file or directory."""
    if _storage.exists(path):
        mtime = _storage.getmtime(path)
        return datetime.fromtimestamp(mtime).isoformat()
    return datetime.now().isoformat()


def _graph_exists(graph_dir: str) -> bool:
    """Check if a valid GraphHopper graph exists."""
    if not _storage.isdir(graph_dir):
        return False
    existing_files = _storage.listdir(graph_dir)
    # Check if at least some graph files exist
    return any(f.startswith("nodes") or f.startswith("edges") for f in existing_files)


def _get_graph_stats(graph_dir: str) -> dict[str, Any]:
    """Get statistics from a GraphHopper graph directory."""
    stats = {
        "valid": False,
        "nodes": 0,
        "edges": 0,
    }

    if not _graph_exists(graph_dir):
        return stats

    # Try to read properties file for stats
    properties_file = _storage.join(graph_dir, "properties")
    if _storage.exists(properties_file):
        try:
            with _storage.open(properties_file, "r") as f:
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        if key == "graph.nodes.count":
                            stats["nodes"] = int(value)
                        elif key == "graph.edges.count":
                            stats["edges"] = int(value)
            stats["valid"] = stats["nodes"] > 0
        except Exception:
            pass
    else:
        # If properties file doesn't exist but graph dir does, assume valid
        stats["valid"] = True

    return stats


_MOTORIZED_PROFILES = {"car", "motorcycle", "truck"}
_NON_MOTORIZED_PROFILES = {"bike", "mtb", "racingbike"}


def _build_config_yaml(osm_path: str, graph_dir: str, profile: str) -> str:
    """Build a GraphHopper 8.0 config YAML string."""
    # Choose ignored highways based on profile type
    if profile in _MOTORIZED_PROFILES:
        ignored = "footway,cycleway,path,pedestrian,steps"
    elif profile in _NON_MOTORIZED_PROFILES:
        ignored = "motorway,trunk"
    else:
        ignored = ""

    lines = [
        "graphhopper:",
        f"  datareader.file: {osm_path}",
        f"  graph.location: {graph_dir}",
        f"  import.osm.ignored_highways: {ignored}",
        "  profiles:",
        f"    - name: {profile}",
        f"      vehicle: {profile}",
        "      custom_model_files: []",
    ]
    return "\n".join(lines) + "\n"


def _run_graphhopper_import(osm_path: str, graph_dir: str, profile: str) -> bool:
    """Run GraphHopper import to build a routing graph.

    GraphHopper 8.0 requires a YAML config file passed as a positional
    argument to the ``import`` subcommand.

    Returns True if successful, False otherwise.
    """
    # Ensure graph directory exists
    _storage.makedirs(graph_dir, exist_ok=True)

    # Write a temporary config file for this build
    config_yaml = _build_config_yaml(osm_path, graph_dir, profile)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", prefix="gh-config-", delete=False
        ) as tmp:
            tmp.write(config_yaml)
            config_path = tmp.name

        cmd = [
            "java", "-Xmx4g", "-jar", GRAPHHOPPER_JAR,
            "import", config_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout for large regions
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        # java or GraphHopper JAR not found
        return False
    finally:
        try:
            os.unlink(config_path)
        except (OSError, UnboundLocalError):
            pass


def _make_graph_result(
    osm_path: str,
    graph_dir: str,
    profile: str,
    was_in_cache: bool,
) -> dict[str, Any]:
    """Create a GraphHopperCache result dictionary."""
    stats = _get_graph_stats(graph_dir)
    return {
        "osmSource": osm_path,
        "graphDir": graph_dir,
        "profile": profile,
        "date": _get_modification_date(graph_dir),
        "size": _get_dir_size(graph_dir),
        "wasInCache": was_in_cache,
        "version": GRAPHHOPPER_VERSION,
        "nodeCount": stats["nodes"],
        "edgeCount": stats["edges"],
    }


def build_graph_handler(payload: dict) -> dict:
    """Build a GraphHopper routing graph from an OSM cache.

    If the graph already exists and recreate=False, returns the cached graph.
    """
    cache = payload.get("cache", {})
    profile = payload.get("profile", "car")
    recreate = payload.get("recreate", False)

    osm_path = cache.get("path", "")
    if not osm_path:
        raise ValueError("No OSM path provided in cache")

    graph_dir = _get_graph_dir(osm_path, profile)

    # Check if graph already exists
    if _graph_exists(graph_dir) and not recreate:
        return {"graph": _make_graph_result(osm_path, graph_dir, profile, True)}

    # Remove existing graph if recreating
    if recreate and _storage.exists(graph_dir):
        _storage.rmtree(graph_dir)

    # Build the graph
    success = _run_graphhopper_import(osm_path, graph_dir, profile)
    if not success:
        raise RuntimeError(f"Failed to build GraphHopper graph for {osm_path}")

    return {"graph": _make_graph_result(osm_path, graph_dir, profile, False)}


def build_multi_profile_handler(payload: dict) -> dict:
    """Build GraphHopper routing graphs for multiple profiles."""
    cache = payload.get("cache", {})
    profiles = payload.get("profiles", ["car"])
    recreate = payload.get("recreate", False)

    graphs = []
    for profile in profiles:
        result = build_graph_handler({
            "cache": cache,
            "profile": profile,
            "recreate": recreate,
        })
        graphs.append(result["graph"])

    return {"graphs": graphs}


def import_graph_handler(payload: dict) -> dict:
    """Import/load an existing graph, building if not found."""
    # Same as build_graph_handler - builds if not found
    return build_graph_handler(payload)


def validate_graph_handler(payload: dict) -> dict:
    """Validate a GraphHopper routing graph and return statistics."""
    graph = payload.get("graph", {})
    graph_dir = graph.get("graphDir", "")

    if not graph_dir:
        return {"valid": False, "nodeCount": 0, "edgeCount": 0}

    stats = _get_graph_stats(graph_dir)
    return {
        "valid": stats["valid"],
        "nodeCount": stats["nodes"],
        "edgeCount": stats["edges"],
    }


def clean_graph_handler(payload: dict) -> dict:
    """Clean up a routing graph directory."""
    graph = payload.get("graph", {})
    graph_dir = graph.get("graphDir", "")

    if graph_dir and _storage.exists(graph_dir):
        _storage.rmtree(graph_dir)
        return {"deleted": True}

    return {"deleted": False}


# -----------------------------------------------------------------------------
# Cache Facet Handlers
# -----------------------------------------------------------------------------

def _make_cache_handler(region_name: str):
    """Factory function to create a GraphHopper cache handler for a region."""
    def handler(payload: dict) -> dict:
        return build_graph_handler(payload)
    return handler


# Registry of all GraphHopper cache namespaces and their facets
GRAPHHOPPER_CACHE_REGISTRY: dict[str, list[str]] = {
    "osm.geo.cache.GraphHopper.Africa": [
        "AllAfrica", "Africa", "Algeria", "Angola", "Benin", "Botswana",
        "BurkinaFaso", "Burundi", "CapeVerde", "Cameroon", "CentralAfricanRepublic",
        "Chad", "Comores", "Congo_Brazzaville", "Congo_Kinshasa", "Djibouti",
        "Egypt", "EquatorialGuinea", "Eritrea", "Eswatini", "Ethiopia", "Gabon",
        "Gambia", "Ghana", "Guinea", "GuineaBissau", "Kenya", "Lesotho",
        "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania",
        "Mauritius", "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria",
        "Rwanda", "SaoTomeAndPrincipe", "Senegal", "Seychelles", "SierraLeone",
        "Somalia", "SouthAfrica", "SouthSudan", "Sudan", "Tanzania", "Togo",
        "Tunisia", "Uganda", "Zambia", "Zimbabwe",
    ],
    "osm.geo.cache.GraphHopper.Asia": [
        "AllAsia", "Asia", "Afghanistan", "Armenia", "Azerbaijan", "Bangladesh",
        "Bhutan", "Brunei", "Cambodia", "China", "EastTimor", "GCCStates",
        "India", "Indonesia", "Iran", "Iraq", "Japan", "Jordan", "Kazakhstan",
        "Kyrgyzstan", "Laos", "Lebanon", "Malaysia", "Maldives", "Mongolia",
        "Myanmar", "Nepal", "NorthKorea", "Pakistan", "IsraelAndPalestine",
        "Philippines", "SaudiArabia", "Singapore", "SouthKorea", "SriLanka",
        "Syria", "Tajikistan", "Taiwan", "Thailand", "Turkmenistan",
        "Uzbekistan", "Vietnam", "Yemen",
    ],
    "osm.geo.cache.GraphHopper.Australia": [
        "AllAustralia", "Australia", "Fiji", "Kiribati", "MarshallIslands",
        "Micronesia", "Nauru", "NewCaledonia", "NewZealand", "Palau",
        "PapuaNewGuinea", "Samoa", "SolomonIslands", "Tonga", "Tuvalu", "Vanuatu",
    ],
    "osm.geo.cache.GraphHopper.Europe": [
        "AllEurope", "Europe", "Albania", "Andorra", "Austria", "Belarus",
        "Belgium", "BosniaHerzegovina", "Bulgaria", "Croatia", "Cyprus",
        "CzechRepublic", "Denmark", "Estonia", "FaroeIslands", "Finland",
        "France", "Georgia", "Germany", "Greece", "Hungary", "Iceland",
        "Ireland", "IsleOfMan", "Italy", "Kosovo", "Latvia", "Liechtenstein",
        "Lithuania", "Luxembourg", "Malta", "Moldova", "Monaco", "Montenegro",
        "Netherlands", "NorthMacedonia", "Norway", "Poland", "Portugal",
        "Romania", "Russia", "Serbia", "Slovakia", "Slovenia", "Spain",
        "Sweden", "Switzerland", "Turkey", "Ukraine", "UnitedKingdom",
    ],
    "osm.geo.cache.GraphHopper.NorthAmerica": [
        "AllNorthAmerica", "NorthAmerica", "Canada", "Greenland", "Mexico",
        "UnitedStates",
    ],
    "osm.geo.cache.GraphHopper.SouthAmerica": [
        "AllSouthAmerica", "SouthAmerica", "Argentina", "Bolivia", "Brazil",
        "Chile", "Colombia", "Ecuador", "Guyana", "Paraguay", "Peru",
        "Suriname", "Uruguay", "Venezuela",
    ],
    "osm.geo.cache.GraphHopper.CentralAmerica": [
        "AllCentralAmerica", "CentralAmerica", "Belize", "CostaRica", "Cuba",
        "ElSalvador", "Guatemala", "Haiti", "Honduras", "Jamaica", "Nicaragua",
        "Panama",
    ],
    "osm.geo.cache.GraphHopper.UnitedStates": [
        "AllUnitedStates", "Alabama", "Alaska", "Arizona", "Arkansas",
        "California", "Colorado", "Connecticut", "Delaware", "DistrictOfColumbia",
        "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
        "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts",
        "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
        "Nevada", "NewHampshire", "NewJersey", "NewMexico", "NewYork",
        "NorthCarolina", "NorthDakota", "Ohio", "Oklahoma", "Oregon",
        "Pennsylvania", "RhodeIsland", "SouthCarolina", "SouthDakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
        "WestVirginia", "Wisconsin", "Wyoming",
    ],
    "osm.geo.cache.GraphHopper.Canada": [
        "AllCanada", "Alberta", "BritishColumbia", "Manitoba", "NewBrunswick",
        "NewfoundlandAndLabrador", "NorthwestTerritories", "NovaScotia",
        "Nunavut", "Ontario", "PrinceEdwardIsland", "Quebec", "Saskatchewan",
        "Yukon",
    ],
}


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

# Operations handlers
GRAPHHOPPER_OPERATIONS_HANDLERS = {
    "osm.geo.Operations.GraphHopper.BuildGraph": build_graph_handler,
    "osm.geo.Operations.GraphHopper.BuildMultiProfile": build_multi_profile_handler,
    "osm.geo.Operations.GraphHopper.BuildGraphAll": build_graph_handler,
    "osm.geo.Operations.GraphHopper.ImportGraph": import_graph_handler,
    "osm.geo.Operations.GraphHopper.ValidateGraph": validate_graph_handler,
    "osm.geo.Operations.GraphHopper.CleanGraph": clean_graph_handler,
}


def register_graphhopper_handlers(poller) -> int:
    """Register all GraphHopper handlers with the poller.

    Returns the number of handlers registered.
    """
    count = 0

    # Register operations handlers
    for name, handler in GRAPHHOPPER_OPERATIONS_HANDLERS.items():
        poller.register(name, handler)
        count += 1

    # Register cache facet handlers
    for namespace, facets in GRAPHHOPPER_CACHE_REGISTRY.items():
        for facet_name in facets:
            qualified_name = f"{namespace}.{facet_name}"
            poller.register(qualified_name, _make_cache_handler(facet_name))
            count += 1

    return count


# RegistryRunner dispatch adapter
_DISPATCH: dict[str, callable] = {}


def _build_dispatch() -> None:
    # Operations handlers (direct functions)
    for name, handler in GRAPHHOPPER_OPERATIONS_HANDLERS.items():
        _DISPATCH[name] = handler
    # Cache facet handlers
    for namespace, facets in GRAPHHOPPER_CACHE_REGISTRY.items():
        for facet_name in facets:
            _DISPATCH[f"{namespace}.{facet_name}"] = _make_cache_handler(facet_name)


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
