"""Writing parser handlers — ParseDraft, ParseReview."""

from __future__ import annotations

import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_draft,
    coerce_review,
    extract_json_payload,
    synthetic_draft,
    synthetic_review,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Writing"


def _step_log(params: dict[str, Any], message: str, level: str = "success") -> None:
    sl = params.get("_step_log")
    if sl is None:
        return
    try:
        sl.append({"message": message, "level": level})
    except AttributeError:
        sl(message)


def handle_parse_draft(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "") or ""
    topic_name = str(params.get("topic_name", "unknown"))

    try:
        parsed = extract_json_payload(text)
        draft = coerce_draft(parsed, topic_name)
        _step_log(
            params,
            f"ParseDraft: parsed '{draft['title']}' ({draft['word_count']} words)",
        )
    except ValueError as e:
        log.warning("ParseDraft falling back to synthetic for %r: %s", topic_name, e)
        draft = synthetic_draft(topic_name)
        _step_log(params, f"ParseDraft: synthetic fallback for '{topic_name}'", level="warning")
    return {"draft": draft}


def handle_parse_review(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "") or ""
    topic_name = str(params.get("topic_name", "unknown"))

    try:
        parsed = extract_json_payload(text)
        review = coerce_review(parsed, topic_name)
        status = "approved" if review["approved"] else "needs revision"
        _step_log(params, f"ParseReview: score {review['score']}/100 ({status})")
    except ValueError as e:
        log.warning("ParseReview falling back to synthetic for %r: %s", topic_name, e)
        review = synthetic_review(topic_name)
        _step_log(params, f"ParseReview: synthetic fallback for '{topic_name}'", level="warning")
    return {"review": review}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.ParseDraft": handle_parse_draft,
    f"{NAMESPACE}.ParseReview": handle_parse_review,
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


def register_writing_handlers(poller) -> None:
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
