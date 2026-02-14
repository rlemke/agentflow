"""Name-based resource resolution handlers.

Handles event facets from the genomics.cache.Resolve namespace:
  ResolveReference — alias lookup for reference genomes
  ResolveAnnotation — alias lookup for annotation databases
  ResolveSample — SRA accession lookup
  ListResources — catalog listing
"""

import logging
import os
from typing import Any

from .cache_handlers import RESOURCE_REGISTRY

log = logging.getLogger(__name__)

NAMESPACE = "genomics.cache.Resolve"

# Alias maps: lowered alias -> (namespace, facet_name)
REFERENCE_ALIASES: dict[str, tuple[str, str]] = {
    "hg38": ("genomics.cache.reference", "GRCh38"),
    "grch38": ("genomics.cache.reference", "GRCh38"),
    "hg37": ("genomics.cache.reference", "GRCh37"),
    "grch37": ("genomics.cache.reference", "GRCh37"),
    "t2t": ("genomics.cache.reference", "T2TCHM13"),
    "t2t-chm13": ("genomics.cache.reference", "T2TCHM13"),
    "chm13": ("genomics.cache.reference", "T2TCHM13"),
    "t2tchm13": ("genomics.cache.reference", "T2TCHM13"),
    "hg19": ("genomics.cache.reference", "Hg19"),
    "grcm39": ("genomics.cache.reference", "GRCm39"),
    "mm39": ("genomics.cache.reference", "GRCm39"),
}

ANNOTATION_ALIASES: dict[str, tuple[str, str]] = {
    "dbsnp": ("genomics.cache.annotation", "DbSNP156"),
    "dbsnp156": ("genomics.cache.annotation", "DbSNP156"),
    "dbsnp155": ("genomics.cache.annotation", "DbSNP155"),
    "clinvar": ("genomics.cache.annotation", "ClinVar"),
    "gnomad": ("genomics.cache.annotation", "GnomAD4"),
    "gnomad4": ("genomics.cache.annotation", "GnomAD4"),
    "gnomad3": ("genomics.cache.annotation", "GnomAD3"),
    "vep": ("genomics.cache.annotation", "VepCache112"),
    "vep112": ("genomics.cache.annotation", "VepCache112"),
    "gencode": ("genomics.cache.annotation", "Gencode46"),
    "gencode46": ("genomics.cache.annotation", "Gencode46"),
}


def _resolve_to_cache(namespace: str, facet_name: str) -> dict[str, Any]:
    """Look up a resource in the registry and return its cache entry."""
    facets = RESOURCE_REGISTRY.get(namespace, {})
    entry = facets.get(facet_name)
    if not entry:
        return {
            "url": "",
            "path": "",
            "date": "",
            "size": 0,
            "wasInCache": False,
            "checksum": "",
            "resource_type": "unknown",
        }
    url, path, size, rtype = entry
    return {
        "url": url,
        "path": path,
        "date": "2026-02-08",
        "size": size,
        "wasInCache": True,
        "checksum": f"sha256:{hash(path) & 0xFFFFFFFF:08x}",
        "resource_type": rtype,
    }


def resolve_reference(payload: dict) -> dict[str, Any]:
    """Resolve a reference genome name to its cache entry."""
    name = payload.get("name", "").lower().strip()
    prefer_source = payload.get("prefer_source", "")

    entry = REFERENCE_ALIASES.get(name)
    if entry:
        ns, facet = entry
        cache = _resolve_to_cache(ns, facet)
        return {
            "cache": cache,
            "resolution": {
                "query": name,
                "matched_name": facet,
                "resource_namespace": ns,
                "category": "reference",
                "source_url": cache["url"],
                "is_ambiguous": False,
                "disambiguation": "",
            },
        }

    # Try exact match against facet names
    ref_ns = "genomics.cache.reference"
    for facet_name in RESOURCE_REGISTRY.get(ref_ns, {}):
        if facet_name.lower() == name:
            cache = _resolve_to_cache(ref_ns, facet_name)
            return {
                "cache": cache,
                "resolution": {
                    "query": name,
                    "matched_name": facet_name,
                    "resource_namespace": ref_ns,
                    "category": "reference",
                    "source_url": cache["url"],
                    "is_ambiguous": False,
                    "disambiguation": "",
                },
            }

    return {
        "cache": _resolve_to_cache("", ""),
        "resolution": {
            "query": name,
            "matched_name": "",
            "resource_namespace": "",
            "category": "reference",
            "source_url": "",
            "is_ambiguous": True,
            "disambiguation": f"Unknown reference: '{name}'. Known: "
                + ", ".join(sorted(REFERENCE_ALIASES.keys())),
        },
    }


def resolve_annotation(payload: dict) -> dict[str, Any]:
    """Resolve an annotation database name to its cache entry."""
    name = payload.get("name", "").lower().strip()

    entry = ANNOTATION_ALIASES.get(name)
    if entry:
        ns, facet = entry
        cache = _resolve_to_cache(ns, facet)
        return {
            "cache": cache,
            "resolution": {
                "query": name,
                "matched_name": facet,
                "resource_namespace": ns,
                "category": "annotation",
                "source_url": cache["url"],
                "is_ambiguous": False,
                "disambiguation": "",
            },
        }

    return {
        "cache": _resolve_to_cache("", ""),
        "resolution": {
            "query": name,
            "matched_name": "",
            "resource_namespace": "",
            "category": "annotation",
            "source_url": "",
            "is_ambiguous": True,
            "disambiguation": f"Unknown annotation: '{name}'. Known: "
                + ", ".join(sorted(ANNOTATION_ALIASES.keys())),
        },
    }


def resolve_sample(payload: dict) -> dict[str, Any]:
    """Resolve an SRA accession to its cache entry."""
    accession = payload.get("accession", "").strip()
    sra_ns = "genomics.cache.sra"

    facets = RESOURCE_REGISTRY.get(sra_ns, {})
    if accession in facets:
        cache = _resolve_to_cache(sra_ns, accession)
        return {
            "cache": cache,
            "resolution": {
                "query": accession,
                "matched_name": accession,
                "resource_namespace": sra_ns,
                "category": "sra",
                "source_url": cache["url"],
                "is_ambiguous": False,
                "disambiguation": "",
            },
        }

    return {
        "cache": _resolve_to_cache("", ""),
        "resolution": {
            "query": accession,
            "matched_name": "",
            "resource_namespace": "",
            "category": "sra",
            "source_url": "",
            "is_ambiguous": True,
            "disambiguation": f"Unknown SRA accession: '{accession}'. Known: "
                + ", ".join(sorted(facets.keys())),
        },
    }


def list_resources(payload: dict) -> dict[str, Any]:
    """List all available cached resources, optionally filtered by category."""
    category = payload.get("category", "").lower().strip()

    resources = []
    categories: dict[str, int] = {}

    for namespace, facets in RESOURCE_REGISTRY.items():
        for facet_name, (url, path, size, rtype) in facets.items():
            if category and rtype != category:
                continue
            resources.append({
                "name": facet_name,
                "namespace": namespace,
                "url": url,
                "path": path,
                "size": size,
                "resource_type": rtype,
            })
            categories[rtype] = categories.get(rtype, 0) + 1

    return {
        "result": {
            "resource_count": len(resources),
            "resources": resources,
            "category_count": len(categories),
            "categories": categories,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.ResolveReference": resolve_reference,
    f"{NAMESPACE}.ResolveAnnotation": resolve_annotation,
    f"{NAMESPACE}.ResolveSample": resolve_sample,
    f"{NAMESPACE}.ListResources": list_resources,
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


def register_resolve_handlers(poller) -> None:
    """Register all resource resolution handlers."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered resolve handler: %s", fqn)
