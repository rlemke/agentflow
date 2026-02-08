"""Derived aligner index cache handlers.

Handles event facets from genomics.cache.index.bwa, genomics.cache.index.star,
and genomics.cache.index.bowtie2 namespaces. Each handler returns an IndexCache
dict simulating a pre-built aligner index.
"""

import logging
from typing import Any, Callable

log = logging.getLogger(__name__)

# Per-reference contig metadata: (contig_count, total_bases)
REFERENCE_CONTIGS: dict[str, tuple[int, int]] = {
    "GRCh38": (195, 3_088_286_401),
    "GRCh37": (84, 3_101_804_739),
    "T2TCHM13": (24, 3_117_292_070),
    "Hg19": (93, 3_137_161_264),
    "GRCm39": (61, 2_728_222_451),
}

# Aligner versions
ALIGNER_VERSIONS: dict[str, str] = {
    "bwa": "bwa-mem2-2.2.1",
    "star": "STAR-2.7.11b",
    "bowtie2": "bowtie2-2.5.3",
}

# Index size multipliers (relative to reference size ~3GB)
ALIGNER_SIZE_MULTIPLIERS: dict[str, float] = {
    "bwa": 1.5,
    "star": 10.0,
    "bowtie2": 1.2,
}

# Registry: namespace -> list of facet names
INDEX_REGISTRY: dict[str, list[str]] = {
    "genomics.cache.index.bwa": ["GRCh38", "GRCh37", "T2TCHM13", "Hg19", "GRCm39"],
    "genomics.cache.index.star": ["GRCh38", "GRCh37", "T2TCHM13"],
    "genomics.cache.index.bowtie2": ["GRCh38", "GRCh37"],
}


def _make_index_handler(aligner: str, reference: str) -> Callable:
    """Factory: create an index handler returning an IndexCache dict."""
    contigs, bases = REFERENCE_CONTIGS.get(reference, (0, 0))
    version = ALIGNER_VERSIONS.get(aligner, aligner)
    multiplier = ALIGNER_SIZE_MULTIPLIERS.get(aligner, 1.0)

    def handler(payload: dict) -> dict[str, Any]:
        source_path = ""
        if isinstance(payload.get("cache"), dict):
            source_path = payload["cache"].get("path", "")
        if not source_path:
            source_path = f"/cache/reference/{reference}/{reference}.fa.gz"

        index_size = int(3_000_000_000 * multiplier)

        return {
            "index": {
                "source_path": source_path,
                "index_dir": f"/cache/index/{aligner}/{reference}/",
                "aligner": aligner,
                "date": "2026-02-08",
                "size": index_size,
                "wasInCache": True,
                "version": version,
                "contig_count": contigs,
                "total_bases": bases,
            },
        }
    return handler


def register_index_handlers(poller) -> None:
    """Register all derived aligner index handlers."""
    count = 0
    for namespace, facets in INDEX_REGISTRY.items():
        aligner = namespace.rsplit(".", 1)[-1]
        for facet_name in facets:
            fqn = f"{namespace}.{facet_name}"
            poller.register(fqn, _make_index_handler(aligner, facet_name))
            count += 1
            log.debug("Registered index handler: %s", fqn)
    log.debug("Registered %d index handlers", count)
