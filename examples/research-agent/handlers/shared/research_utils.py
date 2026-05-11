"""JSON parsing utilities for the research-agent parser handlers.

The agent's FFL is composed against ``anthropic.messages.CreateMessage`` —
each domain step asks Claude for one JSON object/array, then hands the
``text`` to a ``Parse<X>`` event facet. The functions here turn that
text into the schema-shaped dicts the workflow expects.

Goals:

- **Tolerant input** — Claude often wraps JSON in ``` ```json fences,
  prefatory prose ("Here is the JSON: ..."), or trailing apologies.
  ``extract_json_payload`` strips all of that.
- **Deterministic fallbacks** — when the response can't be coerced
  into the target schema, we return a placeholder that keeps the
  workflow alive so callers get a clear failure mode + an
  ``input_text`` field they can audit. The synthetic stubs used by
  the original deterministic example live here under
  ``synthetic_*`` names; they double as test fixtures.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_payload(text: str) -> Any:
    """Pull a JSON object/array out of arbitrary model text.

    Tries, in order:
      1. ``json.loads(text)`` directly.
      2. The first ```` ```json ... ``` ```` (or unlabelled) code fence.
      3. The first ``{...}`` or ``[...]`` substring that parses.

    Raises ``ValueError`` if nothing parses — the caller decides whether
    to fall back to a synthetic placeholder or to re-raise.
    """
    if text is None:
        raise ValueError("empty text from model")

    s = text.strip()
    if not s:
        raise ValueError("empty text from model")

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    fence = _FENCE_RE.search(s)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Greedy fallback: scan for the first balanced { or [.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = s.find(opener)
        if start < 0:
            continue
        depth = 0
        for i, ch in enumerate(s[start:], start):
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = s[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"could not parse JSON from model response: {s[:120]!r}")


# ---------------------------------------------------------------------------
# Deterministic synthetic fallbacks (also used by tests)
# ---------------------------------------------------------------------------


def _hash_int(seed: str, low: int = 0, high: int = 100) -> int:
    """Deterministic integer from seed string."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return low + (h % (high - low + 1))


def _hash_float(seed: str, low: float = 0.0, high: float = 1.0) -> float:
    """Deterministic float from seed string."""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    ratio = h / 0xFFFFFFFF
    return low + ratio * (high - low)


def synthetic_topic(topic: str, depth: int = 3, max_subtopics: int = 5) -> dict[str, Any]:
    """Deterministic Topic dict for tests / offline fallback."""
    h = hashlib.md5(topic.encode()).hexdigest()
    keywords = [f"kw_{h[i : i + 4]}" for i in range(0, min(depth * 4, 16), 4)]
    return {
        "name": topic,
        "depth": depth,
        "keywords": keywords,
        "summary": f"Research plan for '{topic}' at depth {depth}",
        "max_subtopics": max_subtopics,
    }


def synthetic_subtopics(parent_topic: str, max_subtopics: int = 5) -> list[dict[str, Any]]:
    """Deterministic Subtopic list for tests / offline fallback."""
    subtopics = []
    for i in range(max_subtopics):
        h = hashlib.md5(f"{parent_topic}_sub_{i}".encode()).hexdigest()
        subtopics.append(
            {
                "name": f"{parent_topic}_subtopic_{i}",
                "parent_topic": parent_topic,
                "description": f"Investigation of aspect {i} of {parent_topic} (hash: {h[:6]})",
                "priority": max_subtopics - i,
            }
        )
    return subtopics


def synthetic_sources(subtopic_name: str, max_sources: int = 5) -> list[dict[str, Any]]:
    """Deterministic Source list, capped at 5."""
    count = min(max_sources, 5)
    sources = []
    for i in range(count):
        seed = f"{subtopic_name}_source_{i}"
        sources.append(
            {
                "title": f"Source {i}: {subtopic_name}",
                "url": f"https://example.com/research/{hashlib.md5(seed.encode()).hexdigest()[:8]}",
                "relevance_score": round(_hash_float(seed, 0.5, 1.0), 4),
                "source_type": ["journal", "conference", "book", "report", "website"][i % 5],
            }
        )
    return sources


def synthetic_findings(subtopic_name: str, sources_count: int = 3) -> list[dict[str, Any]]:
    """Deterministic Finding list."""
    findings = []
    for i in range(sources_count):
        seed = f"{subtopic_name}_finding_{i}"
        findings.append(
            {
                "claim": f"Finding {i} from {subtopic_name}: evidence suggests correlation",
                "evidence": f"Based on source {i}",
                "confidence": round(_hash_float(seed, 0.4, 0.95), 2),
                "source_title": f"Source {i}: {subtopic_name}",
            }
        )
    return findings


def synthetic_analysis(topic_name: str, finding_count: int = 0) -> dict[str, Any]:
    """Deterministic Analysis dict."""
    n = max(finding_count, 1)
    seed = f"{topic_name}_synth_{n}"
    themes = [f"Theme {i}: Pattern in {topic_name}" for i in range(min(n, 3))]
    contradictions = [f"Contradiction {i}: Conflicting evidence" for i in range(min(n // 3, 2))]
    gaps = [f"Gap {i}: Insufficient data" for i in range(min(n // 2, 3))]
    return {
        "themes": themes,
        "contradictions": contradictions,
        "gaps": gaps,
        "summary": f"Synthesis of {n} findings for '{topic_name}': {len(themes)} themes identified",
        "confidence_score": round(_hash_float(seed, 0.5, 0.9), 2),
    }


def synthetic_gaps_and_recs(topic_name: str, gap_count: int = 1) -> dict[str, Any]:
    """Deterministic (gaps, recommendations) pair."""
    gaps = []
    recs = []
    for i in range(max(gap_count, 1)):
        seed = f"{topic_name}_gap_{i}"
        gaps.append(
            {
                "description": f"Gap {i} in {topic_name}",
                "severity": ["high", "medium", "low"][i % 3],
                "area": f"area_{_hash_int(seed, 0, 5)}",
            }
        )
        recs.append(
            {
                "action": f"Investigate gap {i}",
                "priority": ["high", "medium", "low"][i % 3],
                "estimated_effort": ["low", "medium", "high"][i % 3],
            }
        )
    return {"gaps": gaps, "recommendations": recs}


def synthetic_draft(topic_name: str, theme_count: int = 3) -> dict[str, Any]:
    """Deterministic Draft dict."""
    sections = [
        {"title": "Introduction", "content": f"This report examines {topic_name}."},
        {"title": "Methodology", "content": f"Analysis covered {theme_count} themes."},
        {"title": "Findings", "content": f"Summary of findings on {topic_name}."},
        {"title": "Discussion", "content": "Gaps identified."},
        {"title": "Conclusion", "content": f"Research on {topic_name} reveals insights."},
    ]
    word_count = sum(len(s["content"].split()) for s in sections)
    return {
        "title": f"Research Report: {topic_name}",
        "sections": sections,
        "word_count": word_count,
        "citations": [f"[{i + 1}] Theme {i + 1}" for i in range(min(theme_count, 5))],
    }


def synthetic_review(topic_name: str, draft_title: str = "Untitled") -> dict[str, Any]:
    """Deterministic ReviewResult dict (score range 55–94, approved if >= 70)."""
    seed = f"{topic_name}_{draft_title}_review"
    score = _hash_int(seed, 55, 94)
    feedback = []
    if score < 70:
        feedback.append("Needs significant revision: strengthen evidence")
    else:
        feedback.append("Well-structured analysis")
        if score >= 85:
            feedback.append("Excellent synthesis of findings")
    suggested_edits = []
    if score < 80:
        suggested_edits.append({"section": "Methodology", "suggestion": "Add sample size details"})
    return {
        "score": score,
        "approved": score >= 70,
        "feedback": feedback,
        "suggested_edits": suggested_edits,
    }


# ---------------------------------------------------------------------------
# Coercion helpers — turn parsed JSON into the right shape
# ---------------------------------------------------------------------------


def coerce_topic(parsed: Any, topic_name: str, depth: int, max_subtopics: int) -> dict[str, Any]:
    """Force a parsed value into the Topic schema shape."""
    if not isinstance(parsed, dict):
        return synthetic_topic(topic_name, depth, max_subtopics)
    return {
        "name": str(parsed.get("name", topic_name)),
        "depth": int(parsed.get("depth", depth)),
        "keywords": parsed.get("keywords") or [],
        "summary": str(parsed.get("summary", "")),
        "max_subtopics": int(parsed.get("max_subtopics", max_subtopics)),
    }


def coerce_subtopics(
    parsed: Any, parent_topic: str, max_subtopics: int
) -> list[dict[str, Any]]:
    """Force a parsed value into a list of Subtopic dicts (capped)."""
    if not isinstance(parsed, list):
        return synthetic_subtopics(parent_topic, max_subtopics)
    out: list[dict[str, Any]] = []
    for i, item in enumerate(parsed[:max_subtopics]):
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": str(item.get("name", f"{parent_topic}_subtopic_{i}")),
                "parent_topic": str(item.get("parent_topic", parent_topic)),
                "description": str(item.get("description", "")),
                "priority": int(item.get("priority", max_subtopics - i)),
            }
        )
    return out or synthetic_subtopics(parent_topic, max_subtopics)


def coerce_sources(parsed: Any, subtopic_name: str, max_sources: int) -> list[dict[str, Any]]:
    if not isinstance(parsed, list):
        return synthetic_sources(subtopic_name, max_sources)
    out: list[dict[str, Any]] = []
    for item in parsed[:max_sources]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title", "Untitled")),
                "url": str(item.get("url", "")),
                "relevance_score": float(item.get("relevance_score", 0.0) or 0.0),
                "source_type": str(item.get("source_type", "website")),
            }
        )
    return out or synthetic_sources(subtopic_name, max_sources)


def coerce_findings(parsed: Any, subtopic_name: str) -> list[dict[str, Any]]:
    if not isinstance(parsed, list):
        return synthetic_findings(subtopic_name)
    out: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "claim": str(item.get("claim", "")),
                "evidence": str(item.get("evidence", "")),
                "confidence": float(item.get("confidence", 0.5) or 0.0),
                "source_title": str(item.get("source_title", "")),
            }
        )
    return out


def coerce_analysis(parsed: Any, topic_name: str) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return synthetic_analysis(topic_name)
    return {
        "themes": parsed.get("themes") or [],
        "contradictions": parsed.get("contradictions") or [],
        "gaps": parsed.get("gaps") or [],
        "summary": str(parsed.get("summary", "")),
        "confidence_score": float(parsed.get("confidence_score", 0.5) or 0.0),
    }


def coerce_gaps_and_recs(parsed: Any, topic_name: str) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return synthetic_gaps_and_recs(topic_name)
    gaps_raw = parsed.get("gaps")
    recs_raw = parsed.get("recommendations")
    gaps = gaps_raw if isinstance(gaps_raw, list) else []
    recs = recs_raw if isinstance(recs_raw, list) else []
    if not gaps and not recs:
        return synthetic_gaps_and_recs(topic_name)
    return {"gaps": gaps, "recommendations": recs}


def coerce_draft(parsed: Any, topic_name: str) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return synthetic_draft(topic_name)
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        sections = []
    word_count = int(parsed.get("word_count") or sum(
        len(str(s.get("content", "")).split()) for s in sections if isinstance(s, dict)
    ))
    return {
        "title": str(parsed.get("title", f"Research Report: {topic_name}")),
        "sections": sections,
        "word_count": word_count,
        "citations": parsed.get("citations") or [],
    }


def coerce_review(parsed: Any, topic_name: str) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return synthetic_review(topic_name)
    score = int(parsed.get("score", 70))
    return {
        "score": score,
        "approved": bool(parsed.get("approved", score >= 70)),
        "feedback": parsed.get("feedback") or [],
        "suggested_edits": parsed.get("suggested_edits") or [],
    }
