"""Planning handlers -- PlanToolUse, SelectNextTool."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.tool_utils import plan_tool_use, select_next_tool

NAMESPACE = "tools.Planning"


def handle_plan_tool_use(params: dict[str, Any]) -> dict[str, Any]:
    """Handle PlanToolUse event facet."""
    query = params.get("query", "unknown")
    available_tools = params.get("available_tools", ["search", "calculate", "execute"])
    if isinstance(available_tools, str):
        available_tools = json.loads(available_tools)

    result = plan_tool_use(query, available_tools)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append({"message": f"Planned tool use for '{query}'", "level": "success"})

    return {"plan": result}


def handle_select_next_tool(params: dict[str, Any]) -> dict[str, Any]:
    """Handle SelectNextTool event facet."""
    plan = params.get("plan", {})
    if isinstance(plan, str):
        plan = json.loads(plan)
    completed_tools = params.get("completed_tools", [])
    if isinstance(completed_tools, str):
        completed_tools = json.loads(completed_tools)
    results_so_far = params.get("results_so_far", [])
    if isinstance(results_so_far, str):
        results_so_far = json.loads(results_so_far)

    result = select_next_tool(plan, completed_tools, results_so_far)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append({"message": f"Selected next tool: {result['next_tool']}", "level": "success"})

    return {
        "next_tool": result["next_tool"],
        "tool_params": result["tool_params"],
    }


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.PlanToolUse": handle_plan_tool_use,
    f"{NAMESPACE}.SelectNextTool": handle_select_next_tool,
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


def register_planning_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
