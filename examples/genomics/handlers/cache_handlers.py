"""Per-entity genomics cache download handlers.

Handles event facets from genomics.cache.reference, genomics.cache.annotation,
and genomics.cache.sra namespaces. Each handler returns a GenomicsCache dict
simulating a cached download with realistic metadata.
"""

import logging
from datetime import datetime
from typing import Any, Callable

log = logging.getLogger(__name__)

# Registry: namespace -> {facet_name -> (url, path, size_bytes, resource_type)}
RESOURCE_REGISTRY: dict[str, dict[str, tuple[str, str, int, str]]] = {
    "genomics.cache.reference": {
        "GRCh38": (
            "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/GRCh38_major_release_seqs_for_alignment_pipelines/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz",
            "/cache/reference/GRCh38/GRCh38.fa.gz",
            3_200_000_000,
            "reference",
        ),
        "GRCh37": (
            "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.14_GRCh37.p13/GRCh37_major_release_seqs_for_alignment_pipelines/GCA_000001405.14_GRCh37_no_alt_analysis_set.fna.gz",
            "/cache/reference/GRCh37/GRCh37.fa.gz",
            3_100_000_000,
            "reference",
        ),
        "T2TCHM13": (
            "https://s3-us-west-2.amazonaws.com/human-pangenomics/T2T/CHM13/assemblies/analysis_set/chm13v2.0.fa.gz",
            "/cache/reference/T2TCHM13/chm13v2.0.fa.gz",
            3_050_000_000,
            "reference",
        ),
        "Hg19": (
            "https://hgdownload.cse.ucsc.edu/goldenpath/hg19/bigZips/hg19.fa.gz",
            "/cache/reference/hg19/hg19.fa.gz",
            3_000_000_000,
            "reference",
        ),
        "GRCm39": (
            "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/635/GCA_000001635.9_GRCm39/GRCm39_major_release_seqs_for_alignment_pipelines/GCA_000001635.9_GRCm39_no_alt_analysis_set.fna.gz",
            "/cache/reference/GRCm39/GRCm39.fa.gz",
            2_700_000_000,
            "reference",
        ),
    },
    "genomics.cache.annotation": {
        "DbSNP156": (
            "https://ftp.ncbi.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz",
            "/cache/annotation/dbsnp156/dbsnp156.vcf.gz",
            15_000_000_000,
            "annotation",
        ),
        "DbSNP155": (
            "https://ftp.ncbi.nih.gov/snp/archive/b155/VCF/GCF_000001405.39.gz",
            "/cache/annotation/dbsnp155/dbsnp155.vcf.gz",
            14_500_000_000,
            "annotation",
        ),
        "ClinVar": (
            "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz",
            "/cache/annotation/clinvar/clinvar.vcf.gz",
            300_000_000,
            "annotation",
        ),
        "GnomAD4": (
            "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.0/vcf/genomes/gnomad.genomes.v4.0.sites.vcf.bgz",
            "/cache/annotation/gnomad4/gnomad4.vcf.gz",
            450_000_000_000,
            "annotation",
        ),
        "GnomAD3": (
            "https://storage.googleapis.com/gcp-public-data--gnomad/release/3.1.2/vcf/genomes/gnomad.genomes.v3.1.2.sites.vcf.bgz",
            "/cache/annotation/gnomad3/gnomad3.vcf.gz",
            350_000_000_000,
            "annotation",
        ),
        "VepCache112": (
            "https://ftp.ensembl.org/pub/release-112/variation/vep/homo_sapiens_vep_112_GRCh38.tar.gz",
            "/cache/annotation/vep112/homo_sapiens_vep_112_GRCh38.tar.gz",
            20_000_000_000,
            "annotation",
        ),
        "Gencode46": (
            "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_46/gencode.v46.annotation.gtf.gz",
            "/cache/annotation/gencode46/gencode.v46.annotation.gtf.gz",
            50_000_000,
            "annotation",
        ),
    },
    "genomics.cache.sra": {
        "SRR622461": (
            "https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR622461/SRR622461",
            "/cache/sra/SRR622461/SRR622461.sra",
            25_000_000_000,
            "sra",
        ),
        "SRR622458": (
            "https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR622458/SRR622458",
            "/cache/sra/SRR622458/SRR622458.sra",
            22_000_000_000,
            "sra",
        ),
        "SRR622459": (
            "https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR622459/SRR622459",
            "/cache/sra/SRR622459/SRR622459.sra",
            23_000_000_000,
            "sra",
        ),
        "ERR009378": (
            "https://sra-pub-run-odp.s3.amazonaws.com/sra/ERR009378/ERR009378",
            "/cache/sra/ERR009378/ERR009378.sra",
            18_000_000_000,
            "sra",
        ),
        "SRR13604789": (
            "https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR13604789/SRR13604789",
            "/cache/sra/SRR13604789/SRR13604789.sra",
            30_000_000_000,
            "sra",
        ),
    },
}


def _make_handler(url: str, path: str, size: int, resource_type: str) -> Callable:
    """Factory: create a cache handler returning a GenomicsCache dict."""
    def handler(payload: dict) -> dict[str, Any]:
        return {
            "cache": {
                "url": url,
                "path": path,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "size": size,
                "wasInCache": True,
                "checksum": f"sha256:{hash(path) & 0xFFFFFFFF:08x}",
                "resource_type": resource_type,
            },
        }
    return handler


def register_cache_handlers(poller) -> None:
    """Register all per-entity genomics cache download handlers."""
    count = 0
    for namespace, facets in RESOURCE_REGISTRY.items():
        for facet_name, (url, path, size, rtype) in facets.items():
            fqn = f"{namespace}.{facet_name}"
            poller.register(fqn, _make_handler(url, path, size, rtype))
            count += 1
            log.debug("Registered cache handler: %s", fqn)
    log.debug("Registered %d genomics cache handlers", count)
