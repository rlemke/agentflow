"""Standalone HTTP downloader with filesystem caching for OSM data.

Downloads .osm.pbf files from Geofabrik and caches them locally.
Also provides a generic download_url() for fetching any URL to any path
(local or HDFS).  No AgentFlow dependencies — can be used independently.

Concurrent access is safe: per-path locks prevent duplicate downloads when
multiple threads request the same file, and atomic temp-file renames ensure
the cache file is always either absent or complete (never partial).
"""

import os
import tempfile
import threading
from datetime import UTC, datetime

import requests

from afl.runtime.storage import get_storage_backend

CACHE_DIR = os.environ.get("AFL_CACHE_DIR", os.path.join(tempfile.gettempdir(), "osm-cache"))
_storage = get_storage_backend(CACHE_DIR)
GEOFABRIK_BASE = "https://download.geofabrik.de"
USER_AGENT = "AgentFlow-OSM-Example/1.0"

FORMAT_EXTENSIONS = {
    "pbf": "osm.pbf",
    "shp": "free.shp.zip",
}

_path_locks: dict[str, threading.Lock] = {}
_path_locks_guard = threading.Lock()


def _get_path_lock(path: str) -> threading.Lock:
    """Return a per-path lock, creating one if needed."""
    if path not in _path_locks:
        with _path_locks_guard:
            if path not in _path_locks:
                _path_locks[path] = threading.Lock()
    return _path_locks[path]


def _cache_hit(url: str, path: str, storage=None) -> dict:
    """Build result dict for a cache hit."""
    if storage is None:
        storage = _storage
    return {
        "url": url,
        "path": path,
        "date": datetime.now(UTC).isoformat(),
        "size": storage.getsize(path),
        "wasInCache": True,
    }


def _cache_miss(url: str, path: str, storage=None) -> dict:
    """Build result dict for a cache miss (freshly downloaded)."""
    if storage is None:
        storage = _storage
    return {
        "url": url,
        "path": path,
        "date": datetime.now(UTC).isoformat(),
        "size": storage.getsize(path),
        "wasInCache": False,
    }


def _stream_to_file(url: str, path: str, storage) -> None:
    """Download URL content and stream it to path via storage backend."""
    response = requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=300)
    response.raise_for_status()
    with storage.open(path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def geofabrik_url(region_path: str, fmt: str = "pbf") -> str:
    """Build the full Geofabrik download URL for a region path."""
    ext = FORMAT_EXTENSIONS[fmt]
    return f"{GEOFABRIK_BASE}/{region_path}-latest.{ext}"


def cache_path(region_path: str, fmt: str = "pbf") -> str:
    """Build the cache file path for a region path."""
    ext = FORMAT_EXTENSIONS[fmt]
    return _storage.join(CACHE_DIR, f"{region_path}-latest.{ext}")


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

    # Fast path — already cached, no lock needed
    if _storage.exists(local_path):
        return _cache_hit(url, local_path)

    with _get_path_lock(local_path):
        # Re-check after acquiring lock
        if _storage.exists(local_path):
            return _cache_hit(url, local_path)

        # Download to temp file, then atomic rename
        _storage.makedirs(_storage.dirname(local_path), exist_ok=True)
        tmp_path = local_path + f".tmp.{os.getpid()}.{threading.get_ident()}"
        try:
            _stream_to_file(url, tmp_path, _storage)
            os.replace(tmp_path, local_path)
        except BaseException:
            try:
                _storage.remove(tmp_path)
            except OSError:
                pass
            raise

    return _cache_miss(url, local_path)


def download_url(url: str, path: str, force: bool = False) -> dict:
    """Download any URL to a local or HDFS file path.

    Args:
        url: The URL to download from.
        path: Destination file path (local filesystem or ``hdfs://`` URI).
        force: If True, re-download even when the file already exists.

    Returns:
        OSMCache-compatible dict with url, path, date, size, and wasInCache fields.

    Raises:
        requests.HTTPError: If the download fails.
    """
    storage = get_storage_backend(path)
    is_local = not path.startswith("hdfs://")

    # Fast path — already cached, no lock needed
    if not force and storage.exists(path):
        return _cache_hit(url, path, storage)

    with _get_path_lock(path):
        # Re-check after acquiring lock
        if not force and storage.exists(path):
            return _cache_hit(url, path, storage)

        storage.makedirs(storage.dirname(path), exist_ok=True)

        if is_local:
            tmp_path = path + f".tmp.{os.getpid()}.{threading.get_ident()}"
            try:
                _stream_to_file(url, tmp_path, storage)
                os.replace(tmp_path, path)
            except BaseException:
                try:
                    storage.remove(tmp_path)
                except OSError:
                    pass
                raise
        else:
            _stream_to_file(url, path, storage)

    return _cache_miss(url, path, storage)
