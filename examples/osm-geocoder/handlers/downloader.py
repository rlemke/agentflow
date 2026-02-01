"""Standalone HTTP downloader with filesystem caching for OSM data.

Downloads .osm.pbf files from Geofabrik and caches them locally.
No AgentFlow dependencies — can be used independently.
"""

import os
import tempfile
from datetime import UTC, datetime

import requests

CACHE_DIR = os.path.join(tempfile.gettempdir(), "osm-cache")
GEOFABRIK_BASE = "https://download.geofabrik.de"
USER_AGENT = "AgentFlow-OSM-Example/1.0"

FORMAT_EXTENSIONS = {
    "pbf": "osm.pbf",
    "shp": "free.shp.zip",
}


def geofabrik_url(region_path: str, fmt: str = "pbf") -> str:
    """Build the full Geofabrik download URL for a region path."""
    ext = FORMAT_EXTENSIONS[fmt]
    return f"{GEOFABRIK_BASE}/{region_path}-latest.{ext}"


def cache_path(region_path: str, fmt: str = "pbf") -> str:
    """Build the local cache file path for a region path."""
    ext = FORMAT_EXTENSIONS[fmt]
    return os.path.join(CACHE_DIR, f"{region_path}-latest.{ext}")


def download(region_path: str, fmt: str = "pbf") -> dict:
    """Download an OSM region file, using the local cache if available.

    Args:
        region_path: Geofabrik region path (e.g. "africa/algeria").
        fmt: Download format — "pbf" (default) or "shp" for shapefiles.

    Returns:
        OSMCache dict with url, path, date, size, and wasInCache fields.

    Raises:
        requests.HTTPError: If the download fails.
    """
    url = geofabrik_url(region_path, fmt)
    local_path = cache_path(region_path, fmt)

    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        return {
            "url": url,
            "path": local_path,
            "date": datetime.now(UTC).isoformat(),
            "size": size,
            "wasInCache": True,
        }

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    response = requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=300)
    response.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size = os.path.getsize(local_path)
    return {
        "url": url,
        "path": local_path,
        "date": datetime.now(UTC).isoformat(),
        "size": size,
        "wasInCache": False,
    }
