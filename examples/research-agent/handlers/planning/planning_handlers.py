"""Planning parser handlers — ParseTopic, ParseSubtopics.

These are pure JSON-to-schema converters. The Messages-API call lives
upstream in the FFL composed facets (`PlanResearch`,
`DecomposeIntoSubtopics`), which run via `anthropic.messages.CreateMessage`
and hand the response text to these parsers.

When Claude returns malformed JSON, the parsers fall back to the
deterministic stubs in ``handlers.shared.research_utils`` so the
workflow still produces a schema-shaped result (with a clear log
entry) rather than failing the run.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_subtopics,
    coerce_topic,
    extract_json_payload,
    synthetic_subtopics,
    synthetic_topic,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Planning"


def _step_log(params: dict[str, Any], message: str, level: str = "success") -> None:
    sl = params.get("_step_log")
    if sl is None:
        return
    # Accept either a list-append step log (original style) or a callable.
    try:
        sl.append({"message": message, "level": level})
    except AttributeError:
        sl(message)


def handle_parse_topic(params: dict[str, Any]) -> dict[str, Any]:
    """Parse Claude's planning response text into a Topic."""
    text = params.get("text", "") or ""
    topic_name = str(params.get("topic_name", "unknown"))
    depth = int(params.get("depth", 3))
    max_subtopics = int(params.get("max_subtopics", 5))

    try:
        parsed = extract_json_payload(text)
        plan = coerce_topic(parsed, topic_name, depth, max_subtopics)
        _step_log(params, f"ParseTopic: parsed plan for '{topic_name}'")
    except ValueError as e:
        log.warning("ParseTopic falling back to synthetic for %r: %s", topic_name, e)
        plan = synthetic_topic(topic_name, depth, max_subtopics)
        _step_log(params, f"ParseTopic: synthetic fallback for '{topic_name}'", level="warning")
    return {"plan": plan}


def handle_parse_subtopics(params: dict[str, Any]) -> dict[str, Any]:
    """Parse Claude's decomposition response text into a Subtopic list."""
    text = params.get("text", "") or ""
    parent_topic = str(params.get("parent_topic", "unknown"))
    max_subtopics = int(params.get("max_subtopics", 5))

    try:
        parsed = extract_json_payload(text)
        subtopics = coerce_subtopics(parsed, parent_topic, max_subtopics)
        _step_log(params, f"ParseSubtopics: parsed {len(subtopics)} subtopics for '{parent_topic}'")
    except ValueError as e:
        log.warning("ParseSubtopics falling back to synthetic for %r: %s", parent_topic, e)
        subtopics = synthetic_subtopics(parent_topic, max_subtopics)
        _step_log(
            params,
            f"ParseSubtopics: synthetic fallback for '{parent_topic}'",
            level="warning",
        )
    return {"subtopics": subtopics}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.ParseTopic": handle_parse_topic,
    f"{NAMESPACE}.ParseSubtopics": handle_parse_subtopics,
}


def handle(payload: dict) -> dict:
    facet = payload["_facet_name"]
    return _DISPATCH[facet](payload)


def register_handlers(runner) -> None:
    """Register with RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_planning_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
