"""Reporting handlers — GenerateSweepReport."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.ml_utils import generate_report_text

NAMESPACE = "ml.Reporting"


def handle_generate_sweep_report(params: dict[str, Any]) -> dict[str, Any]:
    """Handle GenerateSweepReport event facet (synthetic fallback)."""
    dataset_name = params.get("dataset_name", "synthetic")

    comparison = params.get("comparison", {})
    if isinstance(comparison, str):
        comparison = json.loads(comparison)

    sweep_config = params.get("sweep_config", {})
    if isinstance(sweep_config, str):
        sweep_config = json.loads(sweep_config)

    report = generate_report_text(
        comparison=comparison,
        dataset_name=dataset_name,
        sweep_config=sweep_config,
    )

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {"message": f"Generated sweep report for '{dataset_name}'", "level": "success"}
        )

    return {"report": report}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.GenerateSweepReport": handle_generate_sweep_report,
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


def register_reporting_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
