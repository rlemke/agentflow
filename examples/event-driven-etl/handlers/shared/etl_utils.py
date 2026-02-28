"""Shared utility functions for the event-driven ETL example.

All functions are pure and deterministic — they use hashlib for reproducible
test outputs rather than random data or real I/O.
"""

from __future__ import annotations

import hashlib


def _hash_int(seed: str, lo: int, hi: int) -> int:
    """Deterministic integer from a seed string."""
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return lo + (h % (hi - lo))


def extract_csv(
    source: str,
    delimiter: str = ",",
    has_header: bool = True,
) -> tuple[list[dict], int]:
    """Simulate CSV extraction.

    Returns (records, row_count).
    """
    n = _hash_int(f"csv:{source}", 3, 15)
    records = []
    for i in range(n):
        records.append(
            {
                "id": str(i + 1),
                "name": f"item_{i + 1}",
                "value": str(_hash_int(f"val:{source}:{i}", 10, 1000)),
            }
        )
    return records, len(records)


def extract_json(
    source: str,
    json_path: str = "$",
) -> tuple[list[dict], int]:
    """Simulate JSON extraction.

    Returns (records, row_count).
    """
    n = _hash_int(f"json:{source}", 2, 10)
    records = []
    for i in range(n):
        records.append(
            {
                "id": str(i + 1),
                "name": f"entry_{i + 1}",
                "value": str(_hash_int(f"jval:{source}:{i}", 100, 9999)),
            }
        )
    return records, len(records)


def validate_schema(
    records: list[dict],
    expected_fields: list[str],
) -> tuple[list[dict], int, list[dict]]:
    """Validate records against expected fields.

    Returns (valid_records, error_count, errors).
    """
    valid = []
    errors = []
    for i, rec in enumerate(records):
        missing = [f for f in expected_fields if f not in rec]
        if missing:
            errors.append(
                {
                    "row": i,
                    "missing_fields": missing,
                    "record": rec,
                }
            )
        else:
            valid.append(rec)
    return valid, len(errors), errors


def transform_records(
    records: list[dict],
    filter_expr: str = "true",
    rename_map: dict | None = None,
    deduplicate: bool = False,
) -> tuple[list[dict], int, int]:
    """Transform records with optional filter, rename, and dedup.

    Returns (transformed, transform_count, dropped_count).
    """
    rename_map = rename_map or {}
    result = []
    seen_ids: set[str] = set()
    dropped = 0

    for rec in records:
        # Simple filter: skip records with empty id
        if filter_expr != "true" and not rec.get("id"):
            dropped += 1
            continue

        # Deduplicate by id
        if deduplicate:
            rec_id = rec.get("id", "")
            if rec_id in seen_ids:
                dropped += 1
                continue
            seen_ids.add(rec_id)

        # Apply rename map
        transformed = {}
        for k, v in rec.items():
            new_key = rename_map.get(k, k)
            transformed[new_key] = v
        result.append(transformed)

    return result, len(result), dropped


def load_to_store(
    records: list[dict],
    target: str,
    mode: str = "append",
) -> dict:
    """Simulate loading records to a store.

    Returns a LoadResult dict.
    """
    duration = _hash_int(f"load:{target}:{len(records)}", 50, 500)
    return {
        "target": target,
        "rows_written": len(records),
        "duration_ms": duration,
        "status": "success" if records else "empty",
    }


def generate_report(
    source: str,
    target: str,
    row_count: int,
    error_count: int,
    load_result: dict,
) -> tuple[str, bool]:
    """Generate a summary report for the ETL run.

    Returns (report, success).
    """
    status = load_result.get("status", "unknown")
    rows_written = load_result.get("rows_written", 0)
    duration = load_result.get("duration_ms", 0)
    success = status == "success" and error_count == 0

    report = (
        f"ETL Report: {source} -> {target}\n"
        f"  Rows extracted: {row_count}\n"
        f"  Validation errors: {error_count}\n"
        f"  Rows loaded: {rows_written}\n"
        f"  Duration: {duration}ms\n"
        f"  Status: {'SUCCESS' if success else 'PARTIAL'}"
    )
    return report, success
