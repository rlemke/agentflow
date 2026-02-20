"""Low-level cache operation handlers.

Handles event facets from the genomics.cache.Operations namespace:
  Download, Index, Validate, Status, Checksum
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "genomics.cache.Operations"


def download(payload: dict) -> dict[str, Any]:
    """Simulate downloading a cached resource (pass-through)."""
    step_log = payload.get("_step_log")
    if step_log:
        step_log(f"Download: {payload.get('cache', {}).get('path', '')}")
    cache = payload.get("cache", {})
    return {"cache": cache}


def index(payload: dict) -> dict[str, Any]:
    """Simulate building an aligner index from a cached reference."""
    step_log = payload.get("_step_log")
    cache = payload.get("cache", {})
    aligner = payload.get("aligner", "bwa")
    if step_log:
        step_log(f"Index: {aligner} from {cache.get('path', '')}")
    source_path = cache.get("path", "")
    return {
        "cache": {
            "source_path": source_path,
            "index_dir": f"/cache/index/{aligner}/",
            "aligner": aligner,
            "date": "2026-02-08",
            "size": 4_500_000_000,
            "wasInCache": True,
            "version": f"{aligner}-latest",
            "contig_count": 195,
            "total_bases": 3_088_286_401,
        },
    }


def validate(payload: dict) -> dict[str, Any]:
    """Simulate validating a cached resource."""
    step_log = payload.get("_step_log")
    if step_log:
        step_log("Validate: verifying checksum")
    return {"valid": True, "message": "Checksum verified"}


def status(payload: dict) -> dict[str, Any]:
    """Return status information for a cached resource."""
    step_log = payload.get("_step_log")
    if step_log:
        step_log("Status: checking cache")
    cache = payload.get("cache", {})
    return {
        "status": "cached",
        "size": cache.get("size", 0),
        "date": cache.get("date", ""),
    }


def checksum(payload: dict) -> dict[str, Any]:
    """Compute or verify the checksum of a cached resource."""
    step_log = payload.get("_step_log")
    if step_log:
        step_log("Checksum: computing hash")
    cache = payload.get("cache", {})
    return {
        "checksum": cache.get("checksum", "sha256:00000000"),
        "algorithm": "sha256",
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.Download": download,
    f"{NAMESPACE}.Index": index,
    f"{NAMESPACE}.Validate": validate,
    f"{NAMESPACE}.Status": status,
    f"{NAMESPACE}.Checksum": checksum,
}


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_operations_handlers(poller) -> None:
    """Register all cache operations handlers."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered operations handler: %s", fqn)
