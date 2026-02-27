"""Core tool utilities -- deterministic stubs for testing.

Uses only hashlib and json from stdlib.  8 functions that produce
consistent, reproducible output from the same inputs.

Designed for real LLM dispatch when an Anthropic client is available;
these stubs provide synthetic fallback for testing.
"""

from __future__ import annotations

import hashlib
import json


# ---------------------------------------------------------------------------
# Helpers
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


_TOOLS = ["search", "calculate", "execute"]


# ---------------------------------------------------------------------------
# Public API (one per event facet)
# ---------------------------------------------------------------------------

def plan_tool_use(
    query: str,
    available_tools: list | None = None,
) -> dict:
    """Create a ToolPlan with search_queries, calculation, code_snippet, strategy."""
    if available_tools is None:
        available_tools = _TOOLS[:]
    seed = f"plan:{query}"
    n_queries = _hash_int(seed, 1, 3)
    return {
        "strategy": f"multi-tool approach for '{query}'",
        "search_queries": [f"{query} aspect_{i}" for i in range(n_queries)],
        "calculation": f"relevance({query})",
        "code_snippet": f"analyze('{query}')",
        "tool_order": available_tools,
    }


def select_next_tool(
    plan: dict,
    completed_tools: list | None = None,
    results_so_far: list | None = None,
) -> dict:
    """Select next tool via len(completed) % len(tools)."""
    if completed_tools is None:
        completed_tools = []
    if results_so_far is None:
        results_so_far = []
    tools = plan.get("tool_order", _TOOLS[:])
    if not tools:
        tools = _TOOLS[:]
    idx = len(completed_tools) % len(tools)
    next_tool = tools[idx]
    return {
        "next_tool": next_tool,
        "tool_params": {"tool": next_tool, "step": len(completed_tools) + 1},
    }


def web_search(
    query: str,
    max_results: int = 5,
) -> dict:
    """Hash-based search results, capped at max_results."""
    seed = f"search:{query}"
    n_results = min(_hash_int(seed, 2, 5), max_results)
    results = []
    for i in range(n_results):
        r_seed = f"{seed}:{i}"
        relevance = _hash_float(r_seed, 0.5, 1.0)
        results.append({
            "title": f"Result {i} for '{query}'",
            "snippet": f"Information about {query} (source {i})",
            "relevance": round(relevance, 4),
        })
    return {
        "query": query,
        "results": results,
        "relevance": round(sum(r["relevance"] for r in results) / max(len(results), 1), 4),
        "source_count": len(results),
    }


def deep_search(
    query: str,
    initial_results: list | None = None,
    depth: int = 2,
) -> tuple[dict, dict]:
    """Expanded results with higher relevance; returns (search_result, knowledge)."""
    if initial_results is None:
        initial_results = []
    seed = f"deep:{query}:{depth}"
    n_results = _hash_int(seed, 3, 7)
    results = []
    for i in range(n_results):
        r_seed = f"{seed}:{i}"
        relevance = _hash_float(r_seed, 0.7, 1.0)
        results.append({
            "title": f"Deep result {i} for '{query}'",
            "snippet": f"Detailed information about {query} (depth {depth}, source {i})",
            "relevance": round(relevance, 4),
        })
    search_result = {
        "query": query,
        "results": results,
        "relevance": round(sum(r["relevance"] for r in results) / max(len(results), 1), 4),
        "source_count": len(results),
    }
    knowledge = {
        "topic": query,
        "summary": f"Deep analysis of '{query}' at depth {depth}",
        "confidence": round(_hash_float(f"knowledge:{query}", 0.7, 0.95), 4),
        "sources": [r["title"] for r in results[:3]],
    }
    return search_result, knowledge


def calculate(
    expression: str,
    precision: int = 2,
) -> dict:
    """Safe eval (digits+ops only), step breakdown, / for normalization."""
    seed = f"calc:{expression}"
    # Deterministic result from expression hash
    result_val = _hash_float(seed, 0.0, 100.0)
    result_val = round(result_val, precision)
    steps = [
        f"Parse: {expression}",
        f"Evaluate: {result_val}",
        f"Round to {precision} decimals",
    ]
    return {
        "expression": expression,
        "result": result_val,
        "steps": steps,
        "precision": precision,
    }


def execute_code(
    code: str,
    language: str = "python",
) -> dict:
    """Deterministic output from hash, exit_code 0."""
    seed = f"exec:{code}:{language}"
    runtime = _hash_int(seed, 10, 500)
    output_hash = hashlib.md5(seed.encode()).hexdigest()[:16]
    return {
        "code": code,
        "output": f"output_{output_hash}",
        "exit_code": 0,
        "runtime_ms": runtime,
    }


def synthesize_results(
    search_results: list | None = None,
    calculations: list | None = None,
    code_results: list | None = None,
    query: str = "",
) -> tuple[str, float, list]:
    """Synthesize tool outputs; returns (synthesis, confidence, key_findings)."""
    if search_results is None:
        search_results = []
    if calculations is None:
        calculations = []
    if code_results is None:
        code_results = []
    n_sources = len(search_results) + len(calculations) + len(code_results)
    seed = f"synthesize:{query}:{n_sources}"
    confidence = _hash_float(seed, 0.6, 0.95)
    synthesis = f"Synthesis for '{query}': {n_sources} sources analyzed"
    key_findings = [f"finding_{i}" for i in range(min(n_sources, 5))]
    return synthesis, round(confidence, 4), key_findings


def format_answer(
    synthesis: str,
    key_findings: list,
    confidence: float,
    query: str,
) -> dict:
    """FormattedAnswer with citations, confidence, tool_usage."""
    citations = [{"finding": f, "index": i} for i, f in enumerate(key_findings)]
    return {
        "answer": f"Answer for '{query}': {synthesis}",
        "citations": citations,
        "confidence": confidence,
        "tool_usage": {
            "findings_count": len(key_findings),
            "query": query,
        },
    }
