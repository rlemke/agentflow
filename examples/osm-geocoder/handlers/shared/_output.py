"""Shared output helpers for OSM extractor handlers.

Provides HDFS-aware output directory resolution and file writing.
When AFL_OSM_OUTPUT_BASE is set (e.g. hdfs://namenode:8020/osm-output),
extractors write output there. Otherwise they use local /tmp/.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO

from afl.runtime.storage import get_storage_backend

_OUTPUT_BASE = os.environ.get("AFL_OSM_OUTPUT_BASE", "")


def resolve_output_dir(category: str, default_local: str = "/tmp") -> str:
    """Return output directory for a handler category.

    When AFL_OSM_OUTPUT_BASE is set (e.g. hdfs://namenode:8020/osm-output),
    returns '{base}/{category}'. Otherwise returns '{default_local}/{category}'.
    """
    if _OUTPUT_BASE:
        return f"{_OUTPUT_BASE.rstrip('/')}/{category}"
    return f"{default_local}/{category}"


def open_output(path: str, mode: str = "w") -> IO:
    """Open a file for writing using the correct storage backend."""
    backend = get_storage_backend(path)
    return backend.open(path, mode)


def ensure_dir(path: str) -> None:
    """Create parent directory for output paths.

    For local paths, creates parent directories via Path.mkdir().
    For HDFS paths, calls makedirs() on the HDFS backend.
    """
    if path.startswith("hdfs://"):
        parent = path.rsplit("/", 1)[0]
        backend = get_storage_backend(path)
        backend.makedirs(parent)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
