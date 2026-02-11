"""OSMOSE QA event facet handlers.

Handles the QueryIssues, QueryGeometryIssues, QueryTagIssues, and IssueSummary
event facets defined in osmosmose.afl under osm.geo.Operations.OSMOSE namespace.

Fetches data quality issues from the OSMOSE public REST API
(osmose.openstreetmap.fr) for a given bounding box, converts them to GeoJSON,
and computes aggregate statistics by category and severity level.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

NAMESPACE = "osm.geo.Operations.OSMOSE"
OSMOSE_API_URL = "https://osmose.openstreetmap.fr/api/0.3"

# OSMOSE item ranges for geometry issues (1xxx)
GEOMETRY_ITEMS = (
    "1000,1010,1020,1040,1050,1060,1070,1080,1090,"
    "1100,1110,1120,1130,1140,1150,1160,1170,1180,1190,"
    "1200,1210,1220,1230,1240,1250,1260,1270,1280,1290"
)

# OSMOSE item ranges for tagging issues (2xxx-4xxx)
TAG_ITEMS = (
    "2010,2020,2030,2040,2060,2080,2090,2100,"
    "3010,3020,3030,3031,3032,3033,3040,3050,3060,3070,3080,3090,"
    "3110,3120,3150,3160,3170,3180,3190,3200,3210,3220,3230,3240,3250,"
    "4010,4020,4030,4040,4060,4070,4080,4090,4100,4130"
)


def handle_query_issues(payload: dict) -> dict:
    """Query OSMOSE issues for a bounding box and write GeoJSON output.

    Params:
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        item: Comma-separated OSMOSE item codes to filter (empty = all)
        level: Comma-separated severity levels (default "1,2,3")
        limit: Maximum number of issues to return (default 500)
        status: Issue status filter (default "open")

    Returns:
        result: OsmoseResult dict
    """
    bbox = payload.get("bbox", "")
    item = payload.get("item", "")
    level = payload.get("level", "1,2,3")
    limit = payload.get("limit", 500)
    status = payload.get("status", "open")

    if not HAS_REQUESTS:
        log.warning("requests library not available; returning empty result")
        return {"result": _empty_result()}

    if not bbox:
        log.warning("No bbox provided; returning empty result")
        return {"result": _empty_result()}

    try:
        params: dict[str, Any] = {
            "bbox": bbox,
            "full": "true",
            "limit": limit,
        }
        if item:
            params["item"] = item
        if level:
            params["level"] = level
        if status:
            params["status"] = status

        url = f"{OSMOSE_API_URL}/issues"
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            log.error("OSMOSE API returned %d: %s", resp.status_code, resp.text[:200])
            return {"result": _empty_result()}

        data = resp.json()
        issues = data.get("issues", [])

        # Convert to GeoJSON
        features = []
        for issue in issues:
            lat = issue.get("lat")
            lon = issue.get("lon")
            if lat is None or lon is None:
                continue

            elems = issue.get("elems", [])
            osm_elements = json.dumps(elems) if elems else "[]"

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "issue_id": str(issue.get("id", "")),
                    "item": issue.get("item", 0),
                    "item_class": issue.get("class", 0),
                    "level": issue.get("level", 0),
                    "title": issue.get("title", {}).get("auto", ""),
                    "subtitle": issue.get("subtitle", {}).get("auto", ""),
                    "osm_elements": osm_elements,
                    "date": issue.get("update", ""),
                },
            })

        # Write GeoJSON
        output_dir = os.path.join(tempfile.gettempdir(), "osm-osmose")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "osmose-issues.geojson")

        geojson = {"type": "FeatureCollection", "features": features}
        with open(output_path, "w") as f:
            json.dump(geojson, f)

        query_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return {"result": {
            "output_path": output_path,
            "issue_count": len(features),
            "format": "GeoJSON",
            "query_date": query_date,
        }}

    except Exception as e:
        log.error("Failed to fetch OSMOSE data: %s", e)
        return {"result": _empty_result()}


def handle_query_geometry_issues(payload: dict) -> dict:
    """Query OSMOSE geometry issues (item 1xxx) for a bounding box.

    Params:
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        level: Comma-separated severity levels (default "1,2,3")
        limit: Maximum number of issues to return (default 500)

    Returns:
        result: OsmoseResult dict
    """
    payload = dict(payload)
    payload["item"] = GEOMETRY_ITEMS
    return handle_query_issues(payload)


def handle_query_tag_issues(payload: dict) -> dict:
    """Query OSMOSE tagging issues (item 2xxx-4xxx) for a bounding box.

    Params:
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        level: Comma-separated severity levels (default "1,2,3")
        limit: Maximum number of issues to return (default 500)

    Returns:
        result: OsmoseResult dict
    """
    payload = dict(payload)
    payload["item"] = TAG_ITEMS
    return handle_query_issues(payload)


def handle_issue_summary(payload: dict) -> dict:
    """Compute aggregate statistics from OSMOSE GeoJSON output.

    Reads a GeoJSON file produced by the query handlers and tallies
    issues by category (geometry vs tagging) and severity level.

    Params:
        input_path: Path to OSMOSE issues GeoJSON file

    Returns:
        summary: OsmoseSummary dict
    """
    input_path = payload.get("input_path", "")

    if not input_path:
        return {"summary": _empty_summary()}

    try:
        with open(input_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.error("Failed to load OSMOSE data: %s", e)
        return {"summary": _empty_summary()}

    features = data.get("features", [])
    if not features:
        return {"summary": _empty_summary()}

    geometry_issues = 0
    tag_issues = 0
    level_1 = 0
    level_2 = 0
    level_3 = 0

    for feat in features:
        props = feat.get("properties", {})
        item = props.get("item", 0)
        level = props.get("level", 0)

        # Classify by item range
        if item < 2000:
            geometry_issues += 1
        elif item < 5000:
            tag_issues += 1

        # Tally by severity level
        if level == 1:
            level_1 += 1
        elif level == 2:
            level_2 += 1
        elif level == 3:
            level_3 += 1

    query_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {"summary": {
        "total_issues": len(features),
        "geometry_issues": geometry_issues,
        "tag_issues": tag_issues,
        "level_1": level_1,
        "level_2": level_2,
        "level_3": level_3,
        "query_date": query_date,
    }}


def _empty_result() -> dict:
    """Return an empty OsmoseResult."""
    return {
        "output_path": "",
        "issue_count": 0,
        "format": "GeoJSON",
        "query_date": "",
    }


def _empty_summary() -> dict:
    """Return an empty OsmoseSummary."""
    return {
        "total_issues": 0,
        "geometry_issues": 0,
        "tag_issues": 0,
        "level_1": 0,
        "level_2": 0,
        "level_3": 0,
        "query_date": "",
    }


def register_osmose_handlers(poller) -> None:
    """Register OSMOSE QA handlers with the poller."""
    poller.register(f"{NAMESPACE}.QueryIssues", handle_query_issues)
    poller.register(f"{NAMESPACE}.QueryGeometryIssues", handle_query_geometry_issues)
    poller.register(f"{NAMESPACE}.QueryTagIssues", handle_query_tag_issues)
    poller.register(f"{NAMESPACE}.IssueSummary", handle_issue_summary)
    log.debug("Registered OSMOSE handlers: %s.*", NAMESPACE)
