"""Planning handlers — PlanResearch, DecomposeIntoSubtopics.

Each handler asks Claude for one JSON object/array via fwh_anthropic's
``create_message``, then coerces the response into the workflow's
schema shape. Malformed responses fall back to a deterministic stub
so the workflow keeps running.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_subtopics,
    coerce_topic,
    run_step_or_fallback,
    synthetic_subtopics,
    synthetic_topic,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Planning"


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def handle_plan_research(params: dict[str, Any]) -> dict[str, Any]:
    topic_name = str(params.get("topic", "unknown"))
    depth = int(params.get("depth", 3))
    max_subtopics = int(params.get("max_subtopics", 5))

    plan = run_step_or_fallback(
        system=(
            "You are a research planning assistant. Reply with one JSON "
            "object only, no prose. Schema: "
            '{"name": string, "depth": int, "keywords": [string], '
            '"summary": string, "max_subtopics": int}.'
        ),
        prompt=(
            f"Plan a research investigation on '{topic_name}' at depth {depth}. "
            f"Identify up to {max_subtopics} key subtopics. Return JSON only."
        ),
        coerce=lambda parsed: coerce_topic(parsed, topic_name, depth, max_subtopics),
        fallback=lambda: synthetic_topic(topic_name, depth, max_subtopics),
        step_log=params.get("_step_log"),
        label=f"PlanResearch[{topic_name}]",
    )
    return {"plan": plan}


def handle_decompose_into_subtopics(params: dict[str, Any]) -> dict[str, Any]:
    topic = _ensure_dict(params.get("topic", {}))
    parent_topic = str(topic.get("name", "unknown"))
    keywords = topic.get("keywords") or []
    max_subtopics = int(params.get("max_subtopics", 5))

    subtopics = run_step_or_fallback(
        system=(
            "You are a research decomposition expert. Reply with one JSON "
            "array of subtopic objects, no prose. Each: "
            '{"name": string, "parent_topic": string, "description": string, '
            '"priority": int}.'
        ),
        prompt=(
            f"Decompose '{parent_topic}' into at most {max_subtopics} subtopics. "
            f"Keywords: {keywords}. Return JSON only."
        ),
        coerce=lambda parsed: coerce_subtopics(parsed, parent_topic, max_subtopics),
        fallback=lambda: synthetic_subtopics(parent_topic, max_subtopics),
        step_log=params.get("_step_log"),
        label=f"DecomposeIntoSubtopics[{parent_topic}]",
    )
    return {"subtopics": subtopics}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.PlanResearch": handle_plan_research,
    f"{NAMESPACE}.DecomposeIntoSubtopics": handle_decompose_into_subtopics,
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


def register_planning_handlers(poller) -> None:
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
