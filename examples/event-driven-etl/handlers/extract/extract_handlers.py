"""Extract handlers for the event-driven ETL example."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.etl_utils import extract_csv, extract_json, validate_schema

NAMESPACE = "etl.Extract"


def handle_extract_csv(params: dict[str, Any]) -> dict[str, Any]:
    """Handle ExtractCSV event facet."""
    source = params.get("source", "")
    delimiter = params.get("delimiter", ",")
    has_header = params.get("has_header", True)

    records, row_count = extract_csv(source, delimiter, has_header)

    step_log = params.get("_step_log")
    if step_log is not None:
        if callable(step_log):
            step_log(f"Extracted {row_count} records from {source}", "success")
        else:
            step_log.append(
                {"message": f"Extracted {row_count} records from {source}", "level": "success"}
            )

    return {"records": records, "row_count": row_count}


def handle_extract_json(params: dict[str, Any]) -> dict[str, Any]:
    """Handle ExtractJSON event facet."""
    source = params.get("source", "")
    json_path = params.get("json_path", "$")

    records, row_count = extract_json(source, json_path)

    step_log = params.get("_step_log")
    if step_log is not None:
        if callable(step_log):
            step_log(f"Extracted {row_count} JSON records from {source}", "success")
        else:
            step_log.append(
                {"message": f"Extracted {row_count} JSON records from {source}", "level": "success"}
            )

    return {"records": records, "row_count": row_count}


def handle_validate_schema(params: dict[str, Any]) -> dict[str, Any]:
    """Handle ValidateSchema event facet."""
    records = params.get("records", [])
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except (json.JSONDecodeError, ValueError):
            records = []

    expected_fields = params.get("expected_fields", [])
    if isinstance(expected_fields, str):
        try:
            expected_fields = json.loads(expected_fields)
        except (json.JSONDecodeError, ValueError):
            expected_fields = []

    valid_records, error_count, errors = validate_schema(records, expected_fields)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Validated: {len(valid_records)} valid, {error_count} errors"
        if callable(step_log):
            step_log(msg, "success" if error_count == 0 else "warning")
        else:
            step_log.append({"message": msg, "level": "success" if error_count == 0 else "warning"})

    return {"valid_records": valid_records, "error_count": error_count, "errors": errors}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.ExtractCSV": handle_extract_csv,
    f"{NAMESPACE}.ExtractJSON": handle_extract_json,
    f"{NAMESPACE}.ValidateSchema": handle_validate_schema,
}


def handle(payload: dict) -> dict:
    """RegistryRunner entrypoint."""
    facet = payload["_facet_name"]
    handler = _DISPATCH[facet]
    return handler(payload)


def register_handlers(runner) -> None:
    """Register with RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_extract_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
