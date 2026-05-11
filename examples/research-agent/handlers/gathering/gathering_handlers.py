"""Gathering parser handlers — ParseSources, ParseFindings."""

from __future__ import annotations

import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_findings,
    coerce_sources,
    extract_json_payload,
    synthetic_findings,
    synthetic_sources,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Gathering"


def _step_log(params: dict[str, Any], message: str, level: str = "success") -> None:
    sl = params.get("_step_log")
    if sl is None:
        return
    try:
        sl.append({"message": message, "level": level})
    except AttributeError:
        sl(message)


def handle_parse_sources(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "") or ""
    subtopic_name = str(params.get("subtopic_name", "unknown"))
    max_sources = int(params.get("max_sources", 5))

    try:
        parsed = extract_json_payload(text)
        sources = coerce_sources(parsed, subtopic_name, max_sources)
        _step_log(params, f"ParseSources: parsed {len(sources)} sources for '{subtopic_name}'")
    except ValueError as e:
        log.warning("ParseSources falling back to synthetic for %r: %s", subtopic_name, e)
        sources = synthetic_sources(subtopic_name, max_sources)
        _step_log(params, f"ParseSources: synthetic fallback for '{subtopic_name}'", level="warning")
    return {"sources": sources}


def handle_parse_findings(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "") or ""
    subtopic_name = str(params.get("subtopic_name", "unknown"))

    try:
        parsed = extract_json_payload(text)
        findings = coerce_findings(parsed, subtopic_name)
        _step_log(params, f"ParseFindings: parsed {len(findings)} findings for '{subtopic_name}'")
    except ValueError as e:
        log.warning("ParseFindings falling back to synthetic for %r: %s", subtopic_name, e)
        findings = synthetic_findings(subtopic_name)
        _step_log(
            params, f"ParseFindings: synthetic fallback for '{subtopic_name}'", level="warning"
        )
    return {"findings": findings}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.ParseSources": handle_parse_sources,
    f"{NAMESPACE}.ParseFindings": handle_parse_findings,
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


def register_gathering_handlers(poller) -> None:
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
