"""Transform handlers for the event-driven ETL example."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.etl_utils import transform_records

NAMESPACE = "etl.Transform"


def handle_transform_records(params: dict[str, Any]) -> dict[str, Any]:
    """Handle TransformRecords event facet."""
    records = params.get("records", [])
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except (json.JSONDecodeError, ValueError):
            records = []

    # Accept either a config dict or individual params
    config = params.get("config", {})
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (json.JSONDecodeError, ValueError):
            config = {}

    filter_expr = params.get("filter_expr", config.get("filter_expr", "true"))
    rename_map = config.get("rename_map", {})
    deduplicate = params.get("deduplicate", config.get("deduplicate", False))

    transformed, transform_count, dropped_count = transform_records(
        records, filter_expr, rename_map, deduplicate
    )

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Transformed {transform_count} records, dropped {dropped_count}"
        if callable(step_log):
            step_log(msg, "success")
        else:
            step_log.append({"message": msg, "level": "success"})

    return {
        "transformed": transformed,
        "transform_count": transform_count,
        "dropped_count": dropped_count,
    }


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.TransformRecords": handle_transform_records,
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


def register_transform_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
