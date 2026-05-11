"""Analysis handlers — SynthesizeFindings, IdentifyGaps."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_analysis,
    coerce_gaps_and_recs,
    run_step_or_fallback,
    synthetic_analysis,
    synthetic_gaps_and_recs,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Analysis"


def _ensure(value: Any, expect: type) -> Any:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return expect()
    return value if isinstance(value, expect) else expect()


def handle_synthesize_findings(params: dict[str, Any]) -> dict[str, Any]:
    topic = _ensure(params.get("topic", {}), dict)
    name = str(topic.get("name", "unknown"))
    all_findings = _ensure(params.get("all_findings", []), list)
    finding_count = sum(
        len(g) if isinstance(g, list) else 1 for g in all_findings
    )

    analysis = run_step_or_fallback(
        system=(
            "You are a research synthesizer. Reply with one JSON object: "
            '{"themes": [string], "contradictions": [string], "gaps": '
            '[string], "summary": string, "confidence_score": number (0-1)}.'
        ),
        prompt=(
            f"Synthesize findings for '{name}'. Identify themes, "
            "contradictions across sources, and remaining gaps. "
            f"Findings: {json.dumps(all_findings)[:1500]}. Return JSON only."
        ),
        coerce=lambda parsed: coerce_analysis(parsed, name),
        fallback=lambda: synthetic_analysis(name, finding_count=finding_count),
        step_log=params.get("_step_log"),
        label=f"SynthesizeFindings[{name}]",
    )
    return {"analysis": analysis}


def handle_identify_gaps(params: dict[str, Any]) -> dict[str, Any]:
    analysis = _ensure(params.get("analysis", {}), dict)
    topic = _ensure(params.get("topic", {}), dict)
    topic_name = str(topic.get("name", "unknown"))
    confidence = float(analysis.get("confidence_score", 0.5) or 0.0)

    parsed = run_step_or_fallback(
        system=(
            "You are a research quality reviewer. Reply with one JSON "
            "object: "
            '{"gaps": [{"description": string, "severity": '
            '"high"|"medium"|"low", "area": string}], '
            '"recommendations": [{"action": string, "priority": string, '
            '"estimated_effort": string}]}.'
        ),
        prompt=(
            f"Review the analysis of '{topic_name}' (confidence "
            f"{confidence:.2f}). Suggest concrete next steps. Return JSON only."
        ),
        coerce=lambda p: coerce_gaps_and_recs(p, topic_name),
        fallback=lambda: synthetic_gaps_and_recs(topic_name),
        step_log=params.get("_step_log"),
        label=f"IdentifyGaps[{topic_name}]",
    )
    gaps, recommendations = parsed
    return {"gaps": gaps, "recommendations": recommendations}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.SynthesizeFindings": handle_synthesize_findings,
    f"{NAMESPACE}.IdentifyGaps": handle_identify_gaps,
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
