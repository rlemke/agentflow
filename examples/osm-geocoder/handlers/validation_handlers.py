"""Validation event facet handlers for OSM cache quality checks.

Handles ValidateCache, ValidateGeometry, ValidateTags, ValidateBounds, and
ValidationSummary event facets defined in osmvalidation.afl under the
osm.geo.Operations.Validation namespace.

Delegates to the OSMOSE verifier for actual PBF analysis.
"""

import logging
from datetime import datetime, timezone

from .osmose_verifier import VerifyResult, VerifySummaryData, compute_verify_summary, verify_pbf

log = logging.getLogger(__name__)

NAMESPACE = "osm.geo.Operations.Validation"


def _stats_dict(summary: VerifySummaryData) -> dict:
    """Build a ValidationStats dict from verify summary data."""
    return {
        "total_entries": summary.total_issues,
        "valid_entries": max(0, summary.total_issues - summary.geometry_issues - summary.tag_issues),
        "invalid_entries": summary.geometry_issues + summary.tag_issues,
        "missing_tags": summary.tag_issues,
        "invalid_geometry": summary.geometry_issues,
        "out_of_bounds": 0,
        "duplicate_entries": summary.reference_issues,
        "validation_date": datetime.now(timezone.utc).isoformat(),
    }


def _result_dict(result: VerifyResult) -> dict:
    """Build a ValidationResult dict from verify result."""
    return {
        "output_path": result.output_path,
        "feature_count": result.issue_count,
        "format": "GeoJSON",
        "validation_date": datetime.now(timezone.utc).isoformat(),
    }


def _empty_stats() -> dict:
    return {
        "total_entries": 0,
        "valid_entries": 0,
        "invalid_entries": 0,
        "missing_tags": 0,
        "invalid_geometry": 0,
        "out_of_bounds": 0,
        "duplicate_entries": 0,
        "validation_date": datetime.now(timezone.utc).isoformat(),
    }


def _empty_result() -> dict:
    return {
        "output_path": "",
        "feature_count": 0,
        "format": "GeoJSON",
        "validation_date": datetime.now(timezone.utc).isoformat(),
    }


def handle_validate_cache(payload: dict) -> dict:
    """Full validation of an OSM cache file."""
    cache = payload.get("cache", {})
    pbf_path = cache.get("path", "") if isinstance(cache, dict) else ""
    output_dir = payload.get("output_dir", "/tmp")

    if not pbf_path:
        log.warning("No PBF path in cache; returning empty validation")
        return {"stats": _empty_stats(), "result": _empty_result()}

    log.info("ValidateCache: validating %s", pbf_path)
    result, summary = verify_pbf(pbf_path, output_dir)
    return {"stats": _stats_dict(summary), "result": _result_dict(result)}


def handle_validate_geometry(payload: dict) -> dict:
    """Geometry-only validation."""
    cache = payload.get("cache", {})
    pbf_path = cache.get("path", "") if isinstance(cache, dict) else ""

    if not pbf_path:
        return {"stats": _empty_stats(), "result": _empty_result()}

    result, summary = verify_pbf(
        pbf_path, check_geometry=True, check_tags=False,
        check_references=False, check_coordinates=False, check_duplicates=False,
    )
    return {"stats": _stats_dict(summary), "result": _result_dict(result)}


def handle_validate_tags(payload: dict) -> dict:
    """Tag-only validation."""
    cache = payload.get("cache", {})
    pbf_path = cache.get("path", "") if isinstance(cache, dict) else ""

    if not pbf_path:
        return {"stats": _empty_stats(), "result": _empty_result()}

    result, summary = verify_pbf(
        pbf_path, check_geometry=False, check_tags=True,
        check_references=False, check_coordinates=False, check_duplicates=False,
    )
    return {"stats": _stats_dict(summary), "result": _result_dict(result)}


def handle_validate_bounds(payload: dict) -> dict:
    """Coordinate bounds validation."""
    cache = payload.get("cache", {})
    pbf_path = cache.get("path", "") if isinstance(cache, dict) else ""

    if not pbf_path:
        return {"stats": _empty_stats(), "result": _empty_result()}

    result, summary = verify_pbf(
        pbf_path, check_geometry=False, check_tags=False,
        check_references=False, check_coordinates=True, check_duplicates=False,
    )
    return {"stats": _stats_dict(summary), "result": _result_dict(result)}


def handle_validation_summary(payload: dict) -> dict:
    """Compute summary from a validation result file."""
    input_path = payload.get("input_path", "")

    if not input_path:
        return {"stats": _empty_stats()}

    summary = compute_verify_summary(input_path)
    return {"stats": _stats_dict(summary)}


def register_validation_handlers(poller) -> None:
    """Register all validation event facet handlers with the poller."""
    poller.register(f"{NAMESPACE}.ValidateCache", handle_validate_cache)
    poller.register(f"{NAMESPACE}.ValidateGeometry", handle_validate_geometry)
    poller.register(f"{NAMESPACE}.ValidateTags", handle_validate_tags)
    poller.register(f"{NAMESPACE}.ValidateBounds", handle_validate_bounds)
    poller.register(f"{NAMESPACE}.ValidationSummary", handle_validation_summary)
    log.debug("Registered validation handlers: %s.*", NAMESPACE)
