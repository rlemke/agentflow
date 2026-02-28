"""Load handlers for the event-driven ETL example."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.etl_utils import generate_report, load_to_store

NAMESPACE = "etl.Load"


def handle_load_to_store(params: dict[str, Any]) -> dict[str, Any]:
    """Handle LoadToStore event facet."""
    records = params.get("records", [])
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except (json.JSONDecodeError, ValueError):
            records = []

    target = params.get("target", "")
    mode = params.get("mode", "append")

    result = load_to_store(records, target, mode)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Loaded {result['rows_written']} rows to {target} ({mode})"
        if callable(step_log):
            step_log(msg, "success")
        else:
            step_log.append({"message": msg, "level": "success"})

    return {"result": result}


def handle_generate_report(params: dict[str, Any]) -> dict[str, Any]:
    """Handle GenerateReport event facet."""
    source = params.get("source", "")
    target = params.get("target", "")
    row_count = int(params.get("row_count", 0))
    error_count = int(params.get("error_count", 0))

    load_result = params.get("load_result", {})
    if isinstance(load_result, str):
        try:
            load_result = json.loads(load_result)
        except (json.JSONDecodeError, ValueError):
            load_result = {}

    report, success = generate_report(source, target, row_count, error_count, load_result)

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Report generated: {'SUCCESS' if success else 'PARTIAL'}"
        if callable(step_log):
            step_log(msg, "success" if success else "warning")
        else:
            step_log.append({"message": msg, "level": "success" if success else "warning"})

    return {"report": report, "success": success}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.LoadToStore": handle_load_to_store,
    f"{NAMESPACE}.GenerateReport": handle_generate_report,
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


def register_load_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
