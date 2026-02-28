"""Output handlers -- SynthesizeResults, FormatAnswer."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.tool_utils import format_answer, synthesize_results

NAMESPACE = "tools.Output"


def handle_synthesize_results(params: dict[str, Any]) -> dict[str, Any]:
    """Handle SynthesizeResults event facet."""
    search_results = params.get("search_results", [])
    if isinstance(search_results, str):
        search_results = json.loads(search_results)
    calculations = params.get("calculations", [])
    if isinstance(calculations, str):
        calculations = json.loads(calculations)
    code_results = params.get("code_results", [])
    if isinstance(code_results, str):
        code_results = json.loads(code_results)
    query = params.get("query", "")

    synthesis, confidence, key_findings = synthesize_results(
        search_results,
        calculations,
        code_results,
        query,
    )

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {
                "message": f"Synthesized results for '{query}' (confidence={confidence})",
                "level": "success",
            }
        )

    return {
        "synthesis": synthesis,
        "confidence": confidence,
        "key_findings": key_findings,
    }


def handle_format_answer(params: dict[str, Any]) -> dict[str, Any]:
    """Handle FormatAnswer event facet."""
    synthesis = params.get("synthesis", "")
    key_findings = params.get("key_findings", [])
    if isinstance(key_findings, str):
        key_findings = json.loads(key_findings)
    confidence = float(params.get("confidence", 0.0))
    query = params.get("query", "")

    result = format_answer(synthesis, key_findings, confidence, query)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append({"message": f"Formatted answer for '{query}'", "level": "success"})

    return {"answer": result}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.SynthesizeResults": handle_synthesize_results,
    f"{NAMESPACE}.FormatAnswer": handle_format_answer,
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


def register_output_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
