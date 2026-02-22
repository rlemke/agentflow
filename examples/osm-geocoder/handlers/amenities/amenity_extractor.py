"""Amenity extraction from OSM data.

Extracts amenities by category: food, shopping, services, healthcare, education, entertainment.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from afl.runtime.storage import get_storage_backend, localize

from ..shared._output import ensure_dir, open_output, resolve_output_dir

_storage = get_storage_backend()

log = logging.getLogger(__name__)

try:
    import osmium
    HAS_OSMIUM = True
except ImportError:
    HAS_OSMIUM = False


class AmenityCategory(Enum):
    """Amenity categories."""

    FOOD = "food"
    SHOPPING = "shopping"
    SERVICES = "services"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    TRANSPORT = "transport"
    ALL = "all"

    @classmethod
    def from_string(cls, value: str) -> "AmenityCategory":
        normalized = value.lower().strip()
        aliases = {
            "food": cls.FOOD, "food_and_drink": cls.FOOD, "restaurant": cls.FOOD,
            "shopping": cls.SHOPPING, "shop": cls.SHOPPING, "retail": cls.SHOPPING,
            "services": cls.SERVICES, "service": cls.SERVICES,
            "healthcare": cls.HEALTHCARE, "health": cls.HEALTHCARE, "medical": cls.HEALTHCARE,
            "education": cls.EDUCATION, "school": cls.EDUCATION,
            "entertainment": cls.ENTERTAINMENT, "leisure": cls.ENTERTAINMENT,
            "transport": cls.TRANSPORT, "transportation": cls.TRANSPORT,
            "all": cls.ALL, "*": cls.ALL,
        }
        if normalized in aliases:
            return aliases[normalized]
        raise ValueError(f"Unknown amenity category: {value}")


# Amenity tag to category mapping
AMENITY_CATEGORIES = {
    # Food & Drink
    "restaurant": AmenityCategory.FOOD,
    "cafe": AmenityCategory.FOOD,
    "bar": AmenityCategory.FOOD,
    "pub": AmenityCategory.FOOD,
    "fast_food": AmenityCategory.FOOD,
    "food_court": AmenityCategory.FOOD,
    "ice_cream": AmenityCategory.FOOD,
    "biergarten": AmenityCategory.FOOD,
    # Services
    "bank": AmenityCategory.SERVICES,
    "atm": AmenityCategory.SERVICES,
    "post_office": AmenityCategory.SERVICES,
    "fuel": AmenityCategory.SERVICES,
    "car_wash": AmenityCategory.SERVICES,
    "car_rental": AmenityCategory.SERVICES,
    "charging_station": AmenityCategory.SERVICES,
    "parking": AmenityCategory.SERVICES,
    # Healthcare
    "hospital": AmenityCategory.HEALTHCARE,
    "clinic": AmenityCategory.HEALTHCARE,
    "doctors": AmenityCategory.HEALTHCARE,
    "dentist": AmenityCategory.HEALTHCARE,
    "pharmacy": AmenityCategory.HEALTHCARE,
    "veterinary": AmenityCategory.HEALTHCARE,
    # Education
    "school": AmenityCategory.EDUCATION,
    "university": AmenityCategory.EDUCATION,
    "college": AmenityCategory.EDUCATION,
    "library": AmenityCategory.EDUCATION,
    "kindergarten": AmenityCategory.EDUCATION,
    # Entertainment
    "cinema": AmenityCategory.ENTERTAINMENT,
    "theatre": AmenityCategory.ENTERTAINMENT,
    "nightclub": AmenityCategory.ENTERTAINMENT,
    "casino": AmenityCategory.ENTERTAINMENT,
    "arts_centre": AmenityCategory.ENTERTAINMENT,
    # Transport
    "bus_station": AmenityCategory.TRANSPORT,
    "ferry_terminal": AmenityCategory.TRANSPORT,
    "taxi": AmenityCategory.TRANSPORT,
}

# Specific amenity types for typed handlers
FOOD_AMENITIES = {"restaurant", "cafe", "bar", "pub", "fast_food", "food_court", "ice_cream", "biergarten"}
SHOPPING_TAGS = {"supermarket", "convenience", "mall", "department_store", "clothes", "shoes", "electronics"}
HEALTHCARE_AMENITIES = {"hospital", "clinic", "doctors", "dentist", "pharmacy", "veterinary"}
EDUCATION_AMENITIES = {"school", "university", "college", "library", "kindergarten"}
ENTERTAINMENT_AMENITIES = {"cinema", "theatre", "nightclub", "casino", "arts_centre"}


@dataclass
class AmenityResult:
    """Result of an amenity extraction."""

    output_path: str
    feature_count: int
    amenity_category: str
    amenity_types: str
    format: str = "GeoJSON"
    extraction_date: str = ""


@dataclass
class AmenityStats:
    """Statistics for extracted amenities."""

    total_amenities: int
    food: int
    shopping: int
    services: int
    healthcare: int
    education: int
    entertainment: int
    transport: int
    other: int
    with_name: int
    with_opening_hours: int


def classify_amenity(tags: dict[str, str]) -> str:
    """Classify an amenity based on its tags."""
    amenity = tags.get("amenity", "")
    if amenity in AMENITY_CATEGORIES:
        return AMENITY_CATEGORIES[amenity].value

    # Check shop tag
    if "shop" in tags:
        return AmenityCategory.SHOPPING.value

    # Check tourism tag
    tourism = tags.get("tourism", "")
    if tourism in ("hotel", "motel", "hostel", "guest_house"):
        return AmenityCategory.SERVICES.value
    if tourism in ("museum", "gallery", "zoo", "theme_park"):
        return AmenityCategory.ENTERTAINMENT.value

    return "other"


class AmenityHandler(osmium.SimpleHandler if HAS_OSMIUM else object):
    """Handler for extracting amenities from OSM data."""

    def __init__(
        self,
        category: AmenityCategory = AmenityCategory.ALL,
        amenity_types: set[str] | None = None,
    ):
        if HAS_OSMIUM:
            super().__init__()
        self.category = category
        self.amenity_types = amenity_types
        self.features: list[dict] = []

    def _tags_to_dict(self, tags) -> dict[str, str]:
        return {t.k: t.v for t in tags}

    def _matches(self, tags: dict[str, str]) -> bool:
        """Check if tags match the filter criteria."""
        amenity = tags.get("amenity", "")
        shop = tags.get("shop", "")

        # Must have amenity or shop tag
        if not amenity and not shop:
            return False

        # Check specific amenity types
        if self.amenity_types:
            return amenity in self.amenity_types or shop in self.amenity_types

        # Check category
        if self.category != AmenityCategory.ALL:
            classification = classify_amenity(tags)
            return classification == self.category.value

        return True

    def node(self, n):
        """Process a node (most amenities are nodes)."""
        tags = self._tags_to_dict(n.tags)
        if not self._matches(tags):
            return

        self.features.append({
            "type": "Feature",
            "properties": {
                "osm_id": n.id,
                "osm_type": "node",
                "amenity": tags.get("amenity", ""),
                "shop": tags.get("shop", ""),
                "category": classify_amenity(tags),
                "name": tags.get("name", ""),
                "opening_hours": tags.get("opening_hours", ""),
                "phone": tags.get("phone", ""),
                "website": tags.get("website", ""),
                "cuisine": tags.get("cuisine", ""),
                "brand": tags.get("brand", ""),
                **{k: v for k, v in tags.items()
                   if k not in ("amenity", "shop", "name", "opening_hours", "phone", "website", "cuisine", "brand")},
            },
            "geometry": {
                "type": "Point",
                "coordinates": [n.location.lon, n.location.lat],
            },
        })


def extract_amenities(
    pbf_path: str | Path,
    category: str | AmenityCategory = AmenityCategory.ALL,
    amenity_types: set[str] | None = None,
    output_path: str | Path | None = None,
) -> AmenityResult:
    """Extract amenities from a PBF file."""
    if not HAS_OSMIUM:
        raise RuntimeError("pyosmium is required for amenity extraction")

    pbf_path = Path(localize(str(pbf_path)))

    if isinstance(category, str):
        category = AmenityCategory.from_string(category)

    if output_path is None:
        out_dir = resolve_output_dir("osm-amenities")
        output_path_str = f"{out_dir}/{pbf_path.stem}_{category.value}_amenities.geojson"
    else:
        output_path_str = str(output_path)
    ensure_dir(output_path_str)

    handler = AmenityHandler(category=category, amenity_types=amenity_types)
    handler.apply_file(str(pbf_path), locations=True)

    geojson = {"type": "FeatureCollection", "features": handler.features}

    with open_output(output_path_str) as f:
        json.dump(geojson, f, indent=2)

    types_str = ",".join(sorted(amenity_types)) if amenity_types else category.value

    return AmenityResult(
        output_path=output_path_str,
        feature_count=len(handler.features),
        amenity_category=category.value,
        amenity_types=types_str,
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )


def calculate_amenity_stats(input_path: str | Path) -> AmenityStats:
    """Calculate statistics for extracted amenities."""
    with _storage.open(str(input_path), "r") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])

    food = shopping = services = healthcare = education = entertainment = transport = other = 0
    with_name = with_hours = 0

    for feature in features:
        props = feature.get("properties", {})
        category = props.get("category", "other")

        if category == "food":
            food += 1
        elif category == "shopping":
            shopping += 1
        elif category == "services":
            services += 1
        elif category == "healthcare":
            healthcare += 1
        elif category == "education":
            education += 1
        elif category == "entertainment":
            entertainment += 1
        elif category == "transport":
            transport += 1
        else:
            other += 1

        if props.get("name"):
            with_name += 1
        if props.get("opening_hours"):
            with_hours += 1

    return AmenityStats(
        total_amenities=len(features),
        food=food,
        shopping=shopping,
        services=services,
        healthcare=healthcare,
        education=education,
        entertainment=entertainment,
        transport=transport,
        other=other,
        with_name=with_name,
        with_opening_hours=with_hours,
    )


def search_amenities(input_path: str | Path, name_pattern: str,
                     output_path: str | Path | None = None) -> AmenityResult:
    """Search amenities by name pattern."""
    input_path = Path(input_path)

    with _storage.open(str(input_path), "r") as f:
        geojson = json.load(f)

    pattern = re.compile(name_pattern, re.IGNORECASE)
    filtered = []

    for feature in geojson.get("features", []):
        name = feature.get("properties", {}).get("name", "")
        if pattern.search(name):
            filtered.append(feature)

    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_search")
    output_path = Path(output_path)

    output_geojson = {"type": "FeatureCollection", "features": filtered}
    with _storage.open(str(output_path), "w") as f:
        json.dump(output_geojson, f, indent=2)

    return AmenityResult(
        output_path=str(output_path),
        feature_count=len(filtered),
        amenity_category="search",
        amenity_types=name_pattern,
        extraction_date=datetime.now(timezone.utc).isoformat(),
    )
