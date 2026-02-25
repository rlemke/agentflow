"""HTTP download utilities for US Census Bureau data.

Downloads ACS summary files and TIGER/Line shapefiles with per-path
locking and filesystem caching.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

_CACHE_DIR = os.environ.get("AFL_CENSUS_CACHE_DIR", "/tmp/census-cache")

# Per-path locks to prevent duplicate concurrent downloads
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()

ACS_BASE = "https://www2.census.gov/programs-surveys/acs/summary_file"
TIGER_BASE = "https://www2.census.gov/geo/tiger"

# TIGER geo_level → directory and file suffix mapping
_TIGER_GEO = {
    "COUNTY": ("COUNTY", "county"),
    "TRACT": ("TRACT", "tract"),
    "BG": ("BG", "bg"),
    "PLACE": ("PLACE", "place"),
}


def _get_lock(path: str) -> threading.Lock:
    """Get or create a per-path lock."""
    with _locks_lock:
        if path not in _locks:
            _locks[path] = threading.Lock()
        return _locks[path]


def _download_file(url: str, dest: str) -> int:
    """Download a URL to a local path, returning file size in bytes."""
    if not HAS_REQUESTS:
        raise RuntimeError("requests library required for downloads")

    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s → %s", url, dest)
    start = time.monotonic()

    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    size = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            size += len(chunk)

    elapsed = time.monotonic() - start
    logger.info("Downloaded %s (%d bytes, %.1fs)", dest, size, elapsed)
    return size


def download_acs(year: str = "2023", period: str = "5-Year",
                 state_fips: str = "01") -> dict[str, Any]:
    """Download ACS summary file for a state.

    Returns a CensusFile dict with url, path, date, size, wasInCache.
    """
    filename = f"acsst{period.replace('-', '').lower()}_{year}_{state_fips}.zip"
    url = f"{ACS_BASE}/{year}/table-based-SF/data/{period}/{filename}"
    dest = os.path.join(_CACHE_DIR, "acs", year, filename)

    lock = _get_lock(dest)
    with lock:
        was_cached = os.path.exists(dest)
        if was_cached:
            size = os.path.getsize(dest)
            logger.info("ACS cache hit: %s (%d bytes)", dest, size)
        else:
            size = _download_file(url, dest)

    return {
        "url": url,
        "path": dest,
        "date": datetime.now(timezone.utc).isoformat(),
        "size": size,
        "wasInCache": was_cached,
    }


def download_tiger(year: str = "2024", geo_level: str = "COUNTY",
                   state_fips: str = "01") -> dict[str, Any]:
    """Download TIGER/Line shapefile for a state and geography level.

    Returns a CensusFile dict with url, path, date, size, wasInCache.
    """
    geo_upper = geo_level.upper()
    if geo_upper not in _TIGER_GEO:
        raise ValueError(f"Unsupported geo_level: {geo_level}. "
                         f"Supported: {list(_TIGER_GEO.keys())}")

    tiger_dir, tiger_suffix = _TIGER_GEO[geo_upper]
    filename = f"tl_{year}_{state_fips}_{tiger_suffix}.zip"
    url = f"{TIGER_BASE}/TIGER{year}/{tiger_dir}/{filename}"
    dest = os.path.join(_CACHE_DIR, "tiger", year, filename)

    lock = _get_lock(dest)
    with lock:
        was_cached = os.path.exists(dest)
        if was_cached:
            size = os.path.getsize(dest)
            logger.info("TIGER cache hit: %s (%d bytes)", dest, size)
        else:
            size = _download_file(url, dest)

    return {
        "url": url,
        "path": dest,
        "date": datetime.now(timezone.utc).isoformat(),
        "size": size,
        "wasInCache": was_cached,
    }
