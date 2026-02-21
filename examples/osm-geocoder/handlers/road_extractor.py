"""Road network extraction from OSM data.

Extracts road network with attributes:
- Classification (motorway, primary, secondary, residential)
- Speed limits, surface type, lane count
- One-way status, access restrictions
"""

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from afl.runtime.storage import get_storage_backend, localize

from ._output import ensure_dir, open_output, resolve_output_dir

_storage = get_storage_backend()

log = logging.getLogger(__name__)

try:
    import osmium
    HAS_OSMIUM = True
except ImportError:
    HAS_OSMIUM = False

try:
    from shapely import wkb
    from shapely.geometry import mapping
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


class RoadClass(Enum):
    """Road classifications."""

    MOTORWAY = "motorway"
    TRUNK = "trunk"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    RESIDENTIAL = "residential"
    SERVICE = "service"
    UNCLASSIFIED = "unclassified"
    TRACK = "track"
    PATH = "path"
    ALL = "all"

    @classmethod
    def from_string(cls, value: str) -> "RoadClass":
        normalized = value.lower().strip()
        aliases = {
            "motorway": cls.MOTORWAY,
            "highway": cls.MOTORWAY,
            "trunk": cls.TRUNK,
            "primary": cls.PRIMARY,
            "secondary": cls.SECONDARY,
            "tertiary": cls.TERTIARY,
            "residential": cls.RESIDENTIAL,
            "service": cls.SERVICE,
            "unclassified": cls.UNCLASSIFIED,
            "track": cls.TRACK,
            "path": cls.PATH,
            "all": cls.ALL,
            "*": cls.ALL,
        }
        if normalized in aliases:
            return aliases[normalized]
        raise ValueError(f"Unknown road class: {value}")


# OSM highway values by road class
ROAD_CLASS_MAP = {
    "motorway": RoadClass.MOTORWAY,
    "motorway_link": RoadClass.MOTORWAY,
    "trunk": RoadClass.TRUNK,
    "trunk_link": RoadClass.TRUNK,
    "primary": RoadClass.PRIMARY,
    "primary_link": RoadClass.PRIMARY,
    "secondary": RoadClass.SECONDARY,
    "secondary_link": RoadClass.SECONDARY,
    "tertiary": RoadClass.TERTIARY,
    "tertiary_link": RoadClass.TERTIARY,
    "residential": RoadClass.RESIDENTIAL,
    "living_street": RoadClass.RESIDENTIAL,
    "service": RoadClass.SERVICE,
    "unclassified": RoadClass.UNCLASSIFIED,
    "track": RoadClass.TRACK,
    "path": RoadClass.PATH,
    "footway": RoadClass.PATH,
    "cycleway": RoadClass.PATH,
    "bridleway": RoadClass.PATH,
}

MAJOR_ROAD_CLASSES = {RoadClass.MOTORWAY, RoadClass.TRUNK, RoadClass.PRIMARY, RoadClass.SECONDARY}

PAVED_SURFACES = {"asphalt", "concrete", "paved", "concrete:plates", "concrete:lanes", "paving_stones", "sett", "cobblestone"}
UNPAVED_SURFACES = {"unpaved", "gravel", "dirt", "sand", "grass", "ground", "earth", "mud", "compacted", "fine_gravel"}


@dataclass
class RoadResult:
    """Result of a road extraction operation."""

    output_path: str
    feature_count: int
    road_class: str
    total_length_km: float
    with_speed_limit: int
    format: str = "GeoJSON"
    extraction_date: str = ""


@dataclass
class RoadStats:
    """Statistics for extracted roads."""

    total_roads: int
    total_length_km: float
    motorway_km: float
    primary_km: float
    secondary_km: float
    tertiary_km: float
    residential_km: float
    other_km: float
    with_speed_limit: int
    with_surface: int
    with_lanes: int
    one_way_count: int


def classify_road(tags: dict[str, str]) -> str:
    """Classify a road based on its highway tag."""
    highway = tags.get("highway", "")
    if highway in ROAD_CLASS_MAP:
        return ROAD_CLASS_MAP[highway].value
    return "other"


def parse_speed_limit(value: str | None) -> int | None:
    """Parse speed limit from OSM maxspeed tag."""
    if not value:
        return None
    try:
        # Handle mph conversion
        if "mph" in value.lower():
            cleaned = value.lower().replace("mph", "").strip()
            return int(float(cleaned) * 1.60934)
        # Remove km/h suffix if present
        cleaned = value.replace("km/h", "").replace("kmh", "").strip()
        return int(float(cleaned))
    except ValueError:
        return None


def parse_lanes(value: str | None) -> int | None:
    """Parse lane count from OSM lanes tag."""
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def calculate_line_length(geometry: dict) -> float:
    """Calculate line length in kilometers."""
    if not geometry or geometry.get("type") not in ("LineString", "MultiLineString"):
        return 0.0

    try:
        coords = geometry.get("coordinates", [])
        if geometry["type"] == "MultiLineString":
            total = 0.0
            for line_coords in coords:
                total += _haversine_length(line_coords)
            return total
        return _haversine_length(coords)
    except Exception:
        return 0.0


def _haversine_length(coords: list) -> float:
    """Calculate length of a coordinate list using Haversine formula."""
    if len(coords) < 2:
        return 0.0

    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][:2]
        lon2, lat2 = coords[i + 1][:2]

        # Haversine formula
        R = 6371  # Earth radius in km
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        total += R * c

    return total


class RoadHandler(osmium.SimpleHandler if HAS_OSMIUM else object):
    """Handler for extracting roads from OSM data."""

    def __init__(
        self,
        road_class: RoadClass = RoadClass.ALL,
        surface_filter: str | None = None,
        require_speed_limit: bool = False,
    ):
        if HAS_OSMIUM:
            super().__init__()
        self.road_class = road_class
        self.surface_filter = surface_filter
        self.require_speed_limit = require_speed_limit
        self.features: list[dict] = []
        self._node_cache: dict[int, tuple[float, float]] = {}
        self._pending_ways: list[tuple[dict, list[int]]] = []

    def _tags_to_dict(self, tags) -> dict[str, str]:
        return {t.k: t.v for t in tags}

    def node(self, n):
        """Cache node locations for way geometry."""
        self._node_cache[n.id] = (n.location.lon, n.location.lat)

    def way(self, w):
        """Process a way (road segment)."""
        tags = self._tags_to_dict(w.tags)

        # Must have highway tag
        if "highway" not in tags:
            return

        classification = classify_road(tags)

        # Filter by road class
        if self.road_class != RoadClass.ALL:
            if self.road_class in MAJOR_ROAD_CLASSES:
                # Major roads filter includes all major classes
                if classification not in [rc.value for rc in MAJOR_ROAD_CLASSES]:
                    return
            elif classification != self.road_class.value:
                return

        # Filter by surface
        surface = tags.get("surface", "")
        if self.surface_filter == "paved" and surface and surface not in PAVED_SURFACES:
            return
        if self.surface_filter == "unpaved" and surface and surface not in UNPAVED_SURFACES:
            return

        # Check speed limit requirement
        speed_limit = parse_speed_limit(tags.get("maxspeed"))
        if self.require_speed_limit and speed_limit is None:
            return

        # Store way for later geometry construction
        node_refs = [n.ref for n in w.nodes]
        self._pending_ways.append((
            {
                "osm_id": w.id,
                "tags": tags,
                "classification": classification,
                "speed_limit": speed_limit,
            },
            node_refs
        ))

    def finalize(self):
        """Build geometries from cached nodes."""
        for way_data, node_refs in self._pending_ways:
            coords = []
            for ref in node_refs:
                if ref in self._node_cache:
                    coords.append(list(self._node_cache[ref]))

            if len(coords) < 2:
                continue

            geometry = {"type": "LineString", "coordinates": coords}
            length_km = calculate_line_length(geometry)

            tags = way_data["tags"]
            self.features.append({
                "type": "Feature",
                "properties": {
                    "osm_id": way_data["osm_id"],
                    "osm_type": "way",
                    "road_class": way_data["classification"],
                    "highway": tags.get("highway", ""),
                    "name": tags.get("name", ""),
                    "ref": tags.get("ref", ""),
                    "maxspeed": way_data["speed_limit"],
                    "lanes": parse_lanes(tags.get("lanes")),
                    "surface": tags.get("surface", ""),
                    "oneway": tags.get("oneway", "") == "yes",
                    "bridge": "bridge" in tags,
                    "tunnel": "tunnel" in tags,
                    "length_km": round(length_km, 3),
                },
                "geometry": geometry,
            })

        # Clear caches
        self._node_cache.clear()
        self._pending_ways.clear()


def extract_roads(
    pbf_path: str | Path,
    road_class: str | RoadClass = RoadClass.ALL,
    surface_filter: str | None = None,
    require_speed_limit: bool = False,
    output_path: str | Path | None = None,
) -> RoadResult:
    """Extract roads from a PBF file."""
    if not HAS_OSMIUM:
        raise RuntimeError("pyosmium is required for road extraction")

    pbf_path = Path(localize(str(pbf_path)))

    if isinstance(road_class, str):
        road_class = RoadClass.from_string(road_class)

    if output_path is None:
        out_dir = resolve_output_dir("osm-roads")
        output_path_str = f"{out_dir}/{pbf_path.stem}_{road_class.value}_roads.geojson"
    else:
        output_path_str = str(output_path)
    ensure_dir(output_path_str)

    handler = RoadHandler(
        road_class=road_class,
        surface_filter=surface_filter,
        require_speed_limit=require_speed_limit,
    )

    # Two-pass processing: first for nodes, then for ways
    handler.apply_file(str(pbf_path), locations=False)
    handler.finalize()

    # Calculate totals
    total_length = sum(f["properties"].get("length_km", 0) for f in handler.features)
    with_speed = sum(1 for f in handler.features if f["properties"].get("maxspeed"))

    geojson = {"type": "FeatureCollection", "features": handler.features}

    with open_output(output_path_str) as f:
        json.dump(geojson, f, indent=2)

    return RoadResult(
        output_path=output_path_str,
        feature_count=len(handler.features),
        road_class=road_class.value,
        total_length_km=round(total_length, 2),
        with_speed_limit=with_speed,
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )


def calculate_road_stats(input_path: str | Path) -> RoadStats:
    """Calculate statistics for extracted roads."""
    with _storage.open(str(input_path), "r") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])

    total_length = 0.0
    motorway_km = primary_km = secondary_km = tertiary_km = residential_km = other_km = 0.0
    with_speed = with_surface = with_lanes = one_way = 0

    for feature in features:
        props = feature.get("properties", {})
        length = props.get("length_km", 0)
        total_length += length

        road_class = props.get("road_class", "other")
        if road_class == "motorway":
            motorway_km += length
        elif road_class == "primary":
            primary_km += length
        elif road_class == "secondary":
            secondary_km += length
        elif road_class == "tertiary":
            tertiary_km += length
        elif road_class == "residential":
            residential_km += length
        else:
            other_km += length

        if props.get("maxspeed"):
            with_speed += 1
        if props.get("surface"):
            with_surface += 1
        if props.get("lanes"):
            with_lanes += 1
        if props.get("oneway"):
            one_way += 1

    return RoadStats(
        total_roads=len(features),
        total_length_km=round(total_length, 2),
        motorway_km=round(motorway_km, 2),
        primary_km=round(primary_km, 2),
        secondary_km=round(secondary_km, 2),
        tertiary_km=round(tertiary_km, 2),
        residential_km=round(residential_km, 2),
        other_km=round(other_km, 2),
        with_speed_limit=with_speed,
        with_surface=with_surface,
        with_lanes=with_lanes,
        one_way_count=one_way,
    )


def filter_roads_by_class(
    input_path: str | Path,
    road_class: str,
    output_path: str | Path | None = None,
) -> RoadResult:
    """Filter roads by classification."""
    input_path = Path(input_path)

    with _storage.open(str(input_path), "r") as f:
        geojson = json.load(f)

    filtered = [
        f for f in geojson.get("features", [])
        if f.get("properties", {}).get("road_class") == road_class
    ]

    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_{road_class}")
    output_path = Path(output_path)

    output_geojson = {"type": "FeatureCollection", "features": filtered}
    with _storage.open(str(output_path), "w") as f:
        json.dump(output_geojson, f, indent=2)

    total_length = sum(f["properties"].get("length_km", 0) for f in filtered)
    with_speed = sum(1 for f in filtered if f["properties"].get("maxspeed"))

    return RoadResult(
        output_path=str(output_path),
        feature_count=len(filtered),
        road_class=road_class,
        total_length_km=round(total_length, 2),
        with_speed_limit=with_speed,
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )


def filter_by_speed_limit(
    input_path: str | Path,
    min_speed: int,
    max_speed: int,
    output_path: str | Path | None = None,
) -> RoadResult:
    """Filter roads by speed limit range."""
    input_path = Path(input_path)

    with _storage.open(str(input_path), "r") as f:
        geojson = json.load(f)

    filtered = []
    for f in geojson.get("features", []):
        speed = f.get("properties", {}).get("maxspeed")
        if speed is not None and min_speed <= speed <= max_speed:
            filtered.append(f)

    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_speed_{min_speed}_{max_speed}")
    output_path = Path(output_path)

    output_geojson = {"type": "FeatureCollection", "features": filtered}
    with _storage.open(str(output_path), "w") as f:
        json.dump(output_geojson, f, indent=2)

    total_length = sum(f["properties"].get("length_km", 0) for f in filtered)

    return RoadResult(
        output_path=str(output_path),
        feature_count=len(filtered),
        road_class="filtered",
        total_length_km=round(total_length, 2),
        with_speed_limit=len(filtered),
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )
