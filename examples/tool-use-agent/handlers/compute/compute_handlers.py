"""Compute handlers -- Calculate, ExecuteCode."""

from __future__ import annotations

import os
from typing import Any

from handlers.shared.tool_utils import calculate, execute_code

NAMESPACE = "tools.Compute"


def handle_calculate(params: dict[str, Any]) -> dict[str, Any]:
    """Handle Calculate event facet."""
    expression = params.get("expression", "0")
    precision = int(params.get("precision", 2))

    result = calculate(expression, precision)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {"message": f"Calculated '{expression}' = {result['result']}", "level": "success"}
        )

    return {"calculation": result}


def handle_execute_code(params: dict[str, Any]) -> dict[str, Any]:
    """Handle ExecuteCode event facet."""
    code = params.get("code", "")
    language = params.get("language", "python")

    result = execute_code(code, language)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {
                "message": f"Executed {language} code (exit={result['exit_code']})",
                "level": "success",
            }
        )

    return {"code_result": result}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.Calculate": handle_calculate,
    f"{NAMESPACE}.ExecuteCode": handle_execute_code,
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


def register_compute_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
