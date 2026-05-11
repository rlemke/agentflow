"""Analysis parser handlers — ParseAnalysis, ParseGaps."""

from __future__ import annotations

import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_analysis,
    coerce_gaps_and_recs,
    extract_json_payload,
    synthetic_analysis,
    synthetic_gaps_and_recs,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Analysis"


def _step_log(params: dict[str, Any], message: str, level: str = "success") -> None:
    sl = params.get("_step_log")
    if sl is None:
        return
    try:
        sl.append({"message": message, "level": level})
    except AttributeError:
        sl(message)


def handle_parse_analysis(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "") or ""
    topic_name = str(params.get("topic_name", "unknown"))

    try:
        parsed = extract_json_payload(text)
        analysis = coerce_analysis(parsed, topic_name)
        _step_log(
            params,
            f"ParseAnalysis: parsed analysis for '{topic_name}' "
            f"({len(analysis['themes'])} themes)",
        )
    except ValueError as e:
        log.warning("ParseAnalysis falling back to synthetic for %r: %s", topic_name, e)
        analysis = synthetic_analysis(topic_name)
        _step_log(params, f"ParseAnalysis: synthetic fallback for '{topic_name}'", level="warning")
    return {"analysis": analysis}


def handle_parse_gaps(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "") or ""
    topic_name = str(params.get("topic_name", "unknown"))

    try:
        parsed = extract_json_payload(text)
        result = coerce_gaps_and_recs(parsed, topic_name)
        _step_log(
            params,
            f"ParseGaps: parsed {len(result['gaps'])} gaps for '{topic_name}'",
        )
    except ValueError as e:
        log.warning("ParseGaps falling back to synthetic for %r: %s", topic_name, e)
        result = synthetic_gaps_and_recs(topic_name)
        _step_log(params, f"ParseGaps: synthetic fallback for '{topic_name}'", level="warning")
    return {"result": result}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.ParseAnalysis": handle_parse_analysis,
    f"{NAMESPACE}.ParseGaps": handle_parse_gaps,
}


def handle(payload: dict) -> dict:
    facet = payload["_facet_name"]
    return _DISPATCH[facet](payload)


def register_handlers(runner) -> None:
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_analysis_handlers(poller) -> None:
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
