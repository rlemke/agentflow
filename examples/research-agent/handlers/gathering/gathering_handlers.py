"""Gathering handlers — GatherSources, ExtractFindings."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_findings,
    coerce_sources,
    run_step_or_fallback,
    synthetic_findings,
    synthetic_sources,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Gathering"


def _ensure(value: Any, expect: type) -> Any:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return expect()
    return value if isinstance(value, expect) else expect()


def handle_gather_sources(params: dict[str, Any]) -> dict[str, Any]:
    subtopic = _ensure(params.get("subtopic", {}), dict)
    name = str(subtopic.get("name", "unknown"))
    description = str(subtopic.get("description", ""))
    max_sources = int(params.get("max_sources", 5))

    sources = run_step_or_fallback(
        system=(
            "You are a research librarian. Reply with one JSON array of "
            "source objects, no prose. Each: "
            '{"title": string, "url": string, "relevance_score": number, '
            '"source_type": string}.'
        ),
        prompt=(
            f"Find up to {max_sources} authoritative sources for subtopic "
            f"'{name}' ({description}). Prefer peer-reviewed. Return JSON only."
        ),
        coerce=lambda parsed: coerce_sources(parsed, name, max_sources),
        fallback=lambda: synthetic_sources(name, max_sources),
        step_log=params.get("_step_log"),
        label=f"GatherSources[{name}]",
    )
    return {"sources": sources}


def handle_extract_findings(params: dict[str, Any]) -> dict[str, Any]:
    subtopic = _ensure(params.get("subtopic", {}), dict)
    name = str(subtopic.get("name", "unknown"))
    sources = _ensure(params.get("sources", []), list)

    findings = run_step_or_fallback(
        system=(
            "You are a research analyst. Reply with one JSON array of "
            "finding objects, no prose. Each: "
            '{"claim": string, "evidence": string, "confidence": '
            'number (0-1), "source_title": string}.'
        ),
        prompt=(
            f"Extract key findings about '{name}' from these sources: "
            f"{json.dumps(sources)[:1500]}. Return JSON only."
        ),
        coerce=lambda parsed: coerce_findings(parsed, name),
        fallback=lambda: synthetic_findings(name, sources_count=len(sources) or 3),
        step_log=params.get("_step_log"),
        label=f"ExtractFindings[{name}]",
    )
    return {"findings": findings}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.GatherSources": handle_gather_sources,
    f"{NAMESPACE}.ExtractFindings": handle_extract_findings,
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
