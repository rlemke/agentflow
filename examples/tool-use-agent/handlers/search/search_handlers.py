"""Search handlers -- WebSearch, DeepSearch."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.tool_utils import deep_search, web_search

NAMESPACE = "tools.Search"


def handle_web_search(params: dict[str, Any]) -> dict[str, Any]:
    """Handle WebSearch event facet."""
    query = params.get("query", "unknown")
    max_results = int(params.get("max_results", 5))

    result = web_search(query, max_results)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {
                "message": f"Web search for '{query}': {result['source_count']} results",
                "level": "success",
            }
        )

    return {"search_result": result}


def handle_deep_search(params: dict[str, Any]) -> dict[str, Any]:
    """Handle DeepSearch event facet."""
    query = params.get("query", "unknown")
    initial_results = params.get("initial_results", [])
    if isinstance(initial_results, str):
        initial_results = json.loads(initial_results)
    depth = int(params.get("depth", 2))

    search_result, knowledge = deep_search(query, initial_results, depth)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {"message": f"Deep search for '{query}' at depth {depth}", "level": "success"}
        )

    return {
        "search_result": search_result,
        "knowledge": knowledge,
    }


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.WebSearch": handle_web_search,
    f"{NAMESPACE}.DeepSearch": handle_deep_search,
}


def handle(payload: dict) -> dict:
    """RegistryRunner entrypoint."""
    facet = payload["_facet_name"]
    handler = _DISPATCH[facet]
    return handler(payload)


def register_handlers(runner) -> None:
    """Register with RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_search_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
