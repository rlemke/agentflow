"""Writing handlers — DraftReport, ReviewDraft."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from handlers.shared.research_utils import (
    coerce_draft,
    coerce_review,
    run_step_or_fallback,
    synthetic_draft,
    synthetic_review,
)

log = logging.getLogger(__name__)

NAMESPACE = "research.Writing"


def _ensure(value: Any, expect: type) -> Any:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return expect()
    return value if isinstance(value, expect) else expect()


def handle_draft_report(params: dict[str, Any]) -> dict[str, Any]:
    topic = _ensure(params.get("topic", {}), dict)
    analysis = _ensure(params.get("analysis", {}), dict)
    gaps = _ensure(params.get("gaps", []), list)
    name = str(topic.get("name", "unknown"))
    themes = analysis.get("themes") or []

    draft = run_step_or_fallback(
        system=(
            "You are a technical writer. Reply with one JSON object: "
            '{"title": string, "sections": [{"title": string, "content": '
            'string}], "word_count": int, "citations": [string]}.'
        ),
        prompt=(
            f"Draft a research report on '{name}'. Themes: {themes}. "
            f"Gaps: {json.dumps(gaps)[:800]}. Be concise. Return JSON only."
        ),
        coerce=lambda parsed: coerce_draft(parsed, name),
        fallback=lambda: synthetic_draft(name, theme_count=len(themes) or 3),
        step_log=params.get("_step_log"),
        label=f"DraftReport[{name}]",
        max_tokens=2048,
    )
    return {"draft": draft}


def handle_review_draft(params: dict[str, Any]) -> dict[str, Any]:
    draft = _ensure(params.get("draft", {}), dict)
    topic = _ensure(params.get("topic", {}), dict)
    name = str(topic.get("name", "unknown"))
    title = str(draft.get("title", "Untitled"))
    word_count = int(draft.get("word_count", 0))

    review = run_step_or_fallback(
        system=(
            "You are a peer reviewer. Reply with one JSON object: "
            '{"score": int 0-100, "approved": bool, "feedback": [string], '
            '"suggested_edits": [{"section": string, "suggestion": string}]}.'
        ),
        prompt=(
            f"Review '{title}' ({word_count} words) on '{name}'. Score 0-100. Return JSON only."
        ),
        coerce=lambda parsed: coerce_review(parsed, name),
        fallback=lambda: synthetic_review(name, draft_title=title),
        step_log=params.get("_step_log"),
        label=f"ReviewDraft[{name}]",
    )
    return {"review": review}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.DraftReport": handle_draft_report,
    f"{NAMESPACE}.ReviewDraft": handle_review_draft,
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
