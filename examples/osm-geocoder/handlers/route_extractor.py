"""OSM route extraction for various transport modes.

Extracts routes and related infrastructure from OSM PBF files for:
- bicycle: Cycle routes, cycleways, bike infrastructure
- hiking: Hiking/walking trails, footpaths
- train: Railway lines, stations
- bus: Bus routes, stops
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Check for pyosmium availability
try:
    import osmium

    HAS_OSMIUM = True
except ImportError:
    HAS_OSMIUM = False


class RouteType(Enum):
    """Supported route types."""

    BICYCLE = "bicycle"
    HIKING = "hiking"
    TRAIN = "train"
    BUS = "bus"
    PUBLIC_TRANSPORT = "public_transport"

    @classmethod
    def from_string(cls, value: str) -> "RouteType":
        """Parse a route type string (case-insensitive)."""
        normalized = value.lower().strip()
        aliases = {
            "bicycle": cls.BICYCLE,
            "bike": cls.BICYCLE,
            "cycling": cls.BICYCLE,
            "cycle": cls.BICYCLE,
            "hiking": cls.HIKING,
            "hike": cls.HIKING,
            "walking": cls.HIKING,
            "foot": cls.HIKING,
            "trail": cls.HIKING,
            "train": cls.TRAIN,
            "rail": cls.TRAIN,
            "railway": cls.TRAIN,
            "bus": cls.BUS,
            "public_transport": cls.PUBLIC_TRANSPORT,
            "transit": cls.PUBLIC_TRANSPORT,
            "pt": cls.PUBLIC_TRANSPORT,
        }
        if normalized in aliases:
            return aliases[normalized]
        raise ValueError(f"Unknown route type: {value}")


# OSM tag configurations for each route type
ROUTE_TAGS = {
    RouteType.BICYCLE: {
        "routes": {
            "route": ["bicycle", "mtb"],
        },
        "ways": {
            "highway": ["cycleway"],
            "cycleway": ["lane", "track", "opposite", "opposite_lane", "opposite_track", "shared_lane"],
            "bicycle": ["designated", "yes"],
        },
        "infrastructure": {
            "amenity": ["bicycle_parking", "bicycle_rental", "bicycle_repair_station"],
            "shop": ["bicycle"],
        },
        "network_key": "network",
        "network_values": ["icn", "ncn", "rcn", "lcn"],  # International/National/Regional/Local
    },
    RouteType.HIKING: {
        "routes": {
            "route": ["hiking", "foot", "walking"],
        },
        "ways": {
            "highway": ["path", "footway", "pedestrian", "track"],
            "foot": ["designated", "yes"],
            "sac_scale": ["hiking", "mountain_hiking", "demanding_mountain_hiking",
                         "alpine_hiking", "demanding_alpine_hiking", "difficult_alpine_hiking"],
        },
        "infrastructure": {
            "amenity": ["shelter", "drinking_water"],
            "tourism": ["alpine_hut", "wilderness_hut", "viewpoint", "picnic_site", "camp_site"],
            "information": ["guidepost", "map", "board"],
        },
        "network_key": "network",
        "network_values": ["iwn", "nwn", "rwn", "lwn"],  # International/National/Regional/Local Walking
    },
    RouteType.TRAIN: {
        "routes": {
            "route": ["train", "railway", "light_rail", "subway", "tram"],
        },
        "ways": {
            "railway": ["rail", "light_rail", "subway", "tram", "narrow_gauge"],
        },
        "infrastructure": {
            "railway": ["station", "halt", "tram_stop", "subway_entrance"],
            "public_transport": ["station", "stop_position", "platform"],
        },
        "network_key": "network",
        "network_values": [],
    },
    RouteType.BUS: {
        "routes": {
            "route": ["bus", "trolleybus"],
        },
        "ways": {
            "highway": ["bus_guideway"],
            "bus": ["designated"],
        },
        "infrastructure": {
            "amenity": ["bus_station"],
            "highway": ["bus_stop"],
            "public_transport": ["stop_position", "platform", "station"],
        },
        "network_key": "network",
        "network_values": [],
    },
    RouteType.PUBLIC_TRANSPORT: {
        "routes": {
            "route": ["train", "railway", "light_rail", "subway", "tram", "bus", "trolleybus", "ferry"],
        },
        "ways": {
            "railway": ["rail", "light_rail", "subway", "tram"],
            "highway": ["bus_guideway"],
        },
        "infrastructure": {
            "railway": ["station", "halt", "tram_stop"],
            "amenity": ["bus_station", "ferry_terminal"],
            "highway": ["bus_stop"],
            "public_transport": ["station", "stop_position", "platform"],
        },
        "network_key": "network",
        "network_values": [],
    },
}


@dataclass
class RouteResult:
    """Result of a route extraction operation."""

    output_path: str
    feature_count: int
    route_type: str
    network_level: str
    include_infrastructure: bool
    format: str = "GeoJSON"
    extraction_date: str = ""


@dataclass
class RouteStats:
    """Statistics for extracted routes."""

    route_count: int
    total_length_km: float
    infrastructure_count: int
    route_type: str


class RouteHandler(osmium.SimpleHandler if HAS_OSMIUM else object):
    """Handler for extracting routes from OSM data."""

    def __init__(
        self,
        route_type: RouteType,
        network_filter: str | None = None,
        include_infrastructure: bool = True,
    ):
        if HAS_OSMIUM:
            super().__init__()
        self.route_type = route_type
        self.network_filter = network_filter if network_filter != "*" else None
        self.include_infrastructure = include_infrastructure

        self.config = ROUTE_TAGS[route_type]
        self.features: list[dict] = []
        self.needed_node_ids: set[int] = set()
        self.node_coords: dict[int, tuple[float, float]] = {}

        # Statistics
        self.route_count = 0
        self.way_count = 0
        self.infra_count = 0

    def _matches_tags(self, tags: dict[str, str], tag_config: dict[str, list[str]]) -> bool:
        """Check if element tags match any of the configured tag patterns."""
        for key, values in tag_config.items():
            if key in tags:
                if tags[key] in values or not values:
                    return True
        return False

    def _matches_network(self, tags: dict[str, str]) -> bool:
        """Check if element matches the network filter."""
        if self.network_filter is None:
            return True
        network_key = self.config["network_key"]
        if network_key in tags:
            return tags[network_key].lower() == self.network_filter.lower()
        return False

    def _tags_to_dict(self, tags) -> dict[str, str]:
        """Convert osmium tags to a dictionary."""
        return {t.k: t.v for t in tags}

    def node(self, n):
        """Process a node."""
        # Store coordinates for way geometry reconstruction
        if n.id in self.needed_node_ids:
            self.node_coords[n.id] = (n.location.lon, n.location.lat)

        # Check for infrastructure POIs
        if self.include_infrastructure:
            tags = self._tags_to_dict(n.tags)
            if self._matches_tags(tags, self.config.get("infrastructure", {})):
                self.features.append({
                    "type": "Feature",
                    "properties": {
                        "osm_id": n.id,
                        "osm_type": "node",
                        "feature_type": "infrastructure",
                        "route_type": self.route_type.value,
                        **tags,
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [n.location.lon, n.location.lat],
                    },
                })
                self.infra_count += 1

    def way(self, w):
        """Process a way."""
        tags = self._tags_to_dict(w.tags)

        # Check if this is a route way
        if self._matches_tags(tags, self.config.get("ways", {})):
            if self._matches_network(tags):
                node_refs = [n.ref for n in w.nodes]
                self.needed_node_ids.update(node_refs)
                self.features.append({
                    "type": "Feature",
                    "properties": {
                        "osm_id": w.id,
                        "osm_type": "way",
                        "feature_type": "way",
                        "route_type": self.route_type.value,
                        "_node_refs": node_refs,  # Temporary, for geometry reconstruction
                        **tags,
                    },
                    "geometry": None,  # Will be filled in second pass
                })
                self.way_count += 1

    def relation(self, r):
        """Process a relation."""
        tags = self._tags_to_dict(r.tags)

        # Check if this is a route relation
        if self._matches_tags(tags, self.config.get("routes", {})):
            if self._matches_network(tags):
                members = [
                    {"type": m.type, "ref": m.ref, "role": m.role}
                    for m in r.members
                ]
                self.features.append({
                    "type": "Feature",
                    "properties": {
                        "osm_id": r.id,
                        "osm_type": "relation",
                        "feature_type": "route",
                        "route_type": self.route_type.value,
                        "member_count": len(members),
                        **tags,
                    },
                    "geometry": None,  # Relations need special handling
                })
                self.route_count += 1

    def finalize_geometries(self):
        """Fill in way geometries using collected node coordinates."""
        for feature in self.features:
            if feature["properties"].get("osm_type") == "way":
                node_refs = feature["properties"].pop("_node_refs", [])
                coords = []
                for ref in node_refs:
                    if ref in self.node_coords:
                        coords.append(list(self.node_coords[ref]))
                if len(coords) >= 2:
                    feature["geometry"] = {
                        "type": "LineString",
                        "coordinates": coords,
                    }


def extract_routes(
    pbf_path: str | Path,
    route_type: str | RouteType,
    network: str = "*",
    include_infrastructure: bool = True,
    output_path: str | Path | None = None,
) -> RouteResult:
    """Extract routes from a PBF file.

    Args:
        pbf_path: Path to input PBF file
        route_type: Type of route (bicycle, hiking, train, bus)
        network: Network level filter (e.g., "ncn" for national cycle network)
        include_infrastructure: Whether to include related POIs
        output_path: Path to output GeoJSON file

    Returns:
        RouteResult with output path and statistics
    """
    if not HAS_OSMIUM:
        raise RuntimeError("pyosmium is required for route extraction")

    pbf_path = Path(pbf_path)
    if output_path is None:
        suffix = f"_{route_type}" if isinstance(route_type, str) else f"_{route_type.value}"
        output_path = pbf_path.with_suffix(f"{suffix}_routes.geojson")
    output_path = Path(output_path)

    # Parse route type
    if isinstance(route_type, str):
        route_type = RouteType.from_string(route_type)

    # First pass: collect features and identify needed nodes
    handler = RouteHandler(
        route_type=route_type,
        network_filter=network,
        include_infrastructure=include_infrastructure,
    )
    handler.apply_file(str(pbf_path), locations=True)

    # Second pass: collect node coordinates for way geometries
    if handler.needed_node_ids:
        class NodeCollector(osmium.SimpleHandler):
            def __init__(self, needed_ids: set[int]):
                super().__init__()
                self.needed_ids = needed_ids
                self.coords: dict[int, tuple[float, float]] = {}

            def node(self, n):
                if n.id in self.needed_ids:
                    self.coords[n.id] = (n.location.lon, n.location.lat)

        collector = NodeCollector(handler.needed_node_ids)
        collector.apply_file(str(pbf_path), locations=True)
        handler.node_coords = collector.coords

    # Finalize geometries
    handler.finalize_geometries()

    # Filter out features without geometry (except relations)
    features = [
        f for f in handler.features
        if f["geometry"] is not None or f["properties"].get("osm_type") == "relation"
    ]

    # Build output GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    return RouteResult(
        output_path=str(output_path),
        feature_count=len(features),
        route_type=route_type.value,
        network_level=network,
        include_infrastructure=include_infrastructure,
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )


def filter_routes_by_type(
    input_path: str | Path,
    route_type: str | RouteType,
    network: str = "*",
    output_path: str | Path | None = None,
) -> RouteResult:
    """Filter already-extracted GeoJSON by route type.

    Args:
        input_path: Path to input GeoJSON file
        route_type: Type of route to filter for
        network: Network level filter
        output_path: Path to output GeoJSON file

    Returns:
        RouteResult with output path and statistics
    """
    input_path = Path(input_path)
    if output_path is None:
        suffix = f"_{route_type}" if isinstance(route_type, str) else f"_{route_type.value}"
        output_path = input_path.with_stem(f"{input_path.stem}{suffix}")
    output_path = Path(output_path)

    # Parse route type
    if isinstance(route_type, str):
        route_type = RouteType.from_string(route_type)

    # Load input
    with open(input_path, encoding="utf-8") as f:
        geojson = json.load(f)

    # Filter features
    network_filter = network if network != "*" else None
    filtered = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})

        # Check route type
        if props.get("route_type") != route_type.value:
            # Also check OSM route tag
            route_tag = props.get("route", "")
            config = ROUTE_TAGS.get(route_type, {})
            route_values = config.get("routes", {}).get("route", [])
            if route_tag not in route_values:
                continue

        # Check network
        if network_filter:
            if props.get("network", "").lower() != network_filter.lower():
                continue

        filtered.append(feature)

    # Build output
    output_geojson = {
        "type": "FeatureCollection",
        "features": filtered,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_geojson, f, indent=2)

    return RouteResult(
        output_path=str(output_path),
        feature_count=len(filtered),
        route_type=route_type.value,
        network_level=network,
        include_infrastructure=False,
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )


def calculate_route_stats(input_path: str | Path) -> RouteStats:
    """Calculate statistics for extracted routes.

    Args:
        input_path: Path to GeoJSON file with routes

    Returns:
        RouteStats with counts and total length
    """
    with open(input_path, encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    route_count = 0
    infra_count = 0
    total_length = 0.0
    route_type = ""

    for feature in features:
        props = feature.get("properties", {})
        feature_type = props.get("feature_type", "")

        if not route_type:
            route_type = props.get("route_type", "")

        if feature_type == "route":
            route_count += 1
        elif feature_type == "infrastructure":
            infra_count += 1
        elif feature_type == "way":
            # Calculate length for LineString geometries
            geometry = feature.get("geometry")
            if geometry and geometry.get("type") == "LineString":
                coords = geometry.get("coordinates", [])
                for i in range(len(coords) - 1):
                    total_length += _haversine_distance(
                        coords[i][1], coords[i][0],
                        coords[i + 1][1], coords[i + 1][0]
                    )

    return RouteStats(
        route_count=route_count,
        total_length_km=total_length,
        infrastructure_count=infra_count,
        route_type=route_type,
    )


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula."""
    import math

    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
