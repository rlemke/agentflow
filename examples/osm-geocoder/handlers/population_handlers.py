"""Population filter event facet handlers.

Handles population filtering events defined in osmfilters_population.afl
under osm.geo.Population namespace.
"""

import logging
from datetime import datetime, timezone

from .population_filter import (
    HAS_OSMIUM,
    Operator,
    PlaceType,
    PopulationFilterResult,
    PopulationStats,
    calculate_population_stats,
    extract_places_with_population,
    filter_geojson_by_population,
)

log = logging.getLogger(__name__)

NAMESPACE = "osm.geo.Population"


def _make_filter_by_population_handler(facet_name: str):
    """Create handler for FilterByPopulation event facet."""

    def handler(payload: dict) -> dict:
        input_path = payload.get("input_path", "")
        min_population = payload.get("min_population", 0)
        place_type = payload.get("place_type", "all")
        operator = payload.get("operator", "gte")

        log.info(
            "%s filtering %s for %s with population %s %d",
            facet_name, input_path, place_type, operator, min_population
        )

        if not input_path:
            return {"result": _empty_result(place_type, min_population, 0)}

        try:
            result = filter_geojson_by_population(
                input_path,
                min_population=min_population,
                place_type=place_type,
                operator=operator,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to filter by population: %s", e)
            return {"result": _empty_result(place_type, min_population, 0)}

    return handler


def _make_filter_by_population_range_handler(facet_name: str):
    """Create handler for FilterByPopulationRange event facet."""

    def handler(payload: dict) -> dict:
        input_path = payload.get("input_path", "")
        min_population = payload.get("min_population", 0)
        max_population = payload.get("max_population", 0)
        place_type = payload.get("place_type", "all")

        log.info(
            "%s filtering %s for %s with population %d-%d",
            facet_name, input_path, place_type, min_population, max_population
        )

        if not input_path:
            return {"result": _empty_result(place_type, min_population, max_population)}

        try:
            result = filter_geojson_by_population(
                input_path,
                min_population=min_population,
                max_population=max_population,
                place_type=place_type,
                operator=Operator.BETWEEN,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to filter by population range: %s", e)
            return {"result": _empty_result(place_type, min_population, max_population)}

    return handler


def _make_extract_places_handler(facet_name: str):
    """Create handler for ExtractPlacesWithPopulation event facet."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        pbf_path = cache.get("path", "")
        place_type = payload.get("place_type", "all")
        min_population = payload.get("min_population", 0)

        log.info(
            "%s extracting %s from %s (min_pop=%d)",
            facet_name, place_type, pbf_path, min_population
        )

        if not HAS_OSMIUM or not pbf_path:
            return {"result": _empty_result(place_type, min_population, 0)}

        try:
            result = extract_places_with_population(
                pbf_path,
                place_type=place_type,
                min_population=min_population,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to extract places with population: %s", e)
            return {"result": _empty_result(place_type, min_population, 0)}

    return handler


def _make_typed_place_handler(facet_name: str, place_type: str):
    """Create handler for a specific place type (Cities, Towns, etc.)."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        pbf_path = cache.get("path", "")
        min_population = payload.get("min_population", 0)

        log.info(
            "%s extracting from %s (min_pop=%d)",
            facet_name, pbf_path, min_population
        )

        if not HAS_OSMIUM or not pbf_path:
            return {"result": _empty_result(place_type, min_population, 0)}

        try:
            result = extract_places_with_population(
                pbf_path,
                place_type=place_type,
                min_population=min_population,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to extract %s: %s", place_type, e)
            return {"result": _empty_result(place_type, min_population, 0)}

    return handler


def _make_admin_handler(facet_name: str, place_type: str):
    """Create handler for administrative boundaries (Countries, States, Counties)."""

    def handler(payload: dict) -> dict:
        cache = payload.get("cache", {})
        pbf_path = cache.get("path", "")

        log.info("%s extracting from %s", facet_name, pbf_path)

        if not HAS_OSMIUM or not pbf_path:
            return {"result": _empty_result(place_type, 0, 0)}

        try:
            result = extract_places_with_population(
                pbf_path,
                place_type=place_type,
                min_population=0,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to extract %s: %s", place_type, e)
            return {"result": _empty_result(place_type, 0, 0)}

    return handler


def _make_population_stats_handler(facet_name: str):
    """Create handler for PopulationStatistics event facet."""

    def handler(payload: dict) -> dict:
        input_path = payload.get("input_path", "")
        place_type = payload.get("place_type", "all")

        log.info("%s calculating stats for %s (%s)", facet_name, input_path, place_type)

        if not input_path:
            return {"stats": _empty_stats()}

        try:
            stats = calculate_population_stats(input_path, place_type=place_type)
            return {"stats": _stats_to_dict(stats)}
        except Exception as e:
            log.error("Failed to calculate population stats: %s", e)
            return {"stats": _empty_stats()}

    return handler


def _result_to_dict(result: PopulationFilterResult) -> dict:
    """Convert a PopulationFilterResult to a dictionary."""
    return {
        "output_path": result.output_path,
        "feature_count": result.feature_count,
        "original_count": result.original_count,
        "place_type": result.place_type,
        "min_population": result.min_population,
        "max_population": result.max_population,
        "filter_applied": result.filter_applied,
        "format": result.format,
        "extraction_date": result.extraction_date,
    }


def _stats_to_dict(stats: PopulationStats) -> dict:
    """Convert PopulationStats to a dictionary."""
    return {
        "total_places": stats.total_places,
        "total_population": stats.total_population,
        "min_population": stats.min_population,
        "max_population": stats.max_population,
        "avg_population": stats.avg_population,
        "place_type": stats.place_type,
    }


def _empty_result(place_type: str, min_pop: int, max_pop: int) -> dict:
    """Return an empty result dict."""
    return {
        "output_path": "",
        "feature_count": 0,
        "original_count": 0,
        "place_type": place_type,
        "min_population": min_pop,
        "max_population": max_pop,
        "filter_applied": "",
        "format": "GeoJSON",
        "extraction_date": datetime.now(timezone.utc).isoformat(),
    }


def _empty_stats() -> dict:
    """Return empty stats dict."""
    return {
        "total_places": 0,
        "total_population": 0,
        "min_population": 0,
        "max_population": 0,
        "avg_population": 0,
        "place_type": "",
    }


# Event facet definitions for handler registration
POPULATION_FACETS = [
    # Generic filters
    ("FilterByPopulation", _make_filter_by_population_handler),
    ("FilterByPopulationRange", _make_filter_by_population_range_handler),
    ("ExtractPlacesWithPopulation", _make_extract_places_handler),
    ("PopulationStatistics", _make_population_stats_handler),
    # Typed convenience facets
    ("Cities", lambda name: _make_typed_place_handler(name, "city")),
    ("Towns", lambda name: _make_typed_place_handler(name, "town")),
    ("Villages", lambda name: _make_typed_place_handler(name, "village")),
    ("Countries", lambda name: _make_admin_handler(name, "country")),
    ("States", lambda name: _make_admin_handler(name, "state")),
    ("Counties", lambda name: _make_admin_handler(name, "county")),
    ("AllPopulatedPlaces", lambda name: _make_typed_place_handler(name, "all")),
]


def register_population_handlers(poller) -> None:
    """Register all population event facet handlers with the poller."""
    for facet_name, handler_factory in POPULATION_FACETS:
        qualified_name = f"{NAMESPACE}.{facet_name}"
        poller.register(qualified_name, handler_factory(facet_name))
        log.debug("Registered population handler: %s", qualified_name)
