"""Event facet handlers for risk analytics.

Handles ComputeVaR and ComputeGreeks event facets.
"""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.math_utils import (
    calculate_cvar,
    calculate_var,
    compute_finite_difference_greeks,
)

NAMESPACE = "risk.Analytics"


def handle_compute_var(params: dict[str, Any]) -> dict[str, Any]:
    """Compute Value-at-Risk and Conditional VaR."""
    pnl_distributions = params.get("pnl_distributions", [])
    confidence_levels = params.get("confidence_levels", [0.95, 0.99])
    step_log = params.get("_step_log")

    if isinstance(pnl_distributions, str):
        pnl_distributions = json.loads(pnl_distributions)
    if isinstance(confidence_levels, str):
        confidence_levels = json.loads(confidence_levels)

    var_95 = calculate_var(pnl_distributions, 0.95) if pnl_distributions else 0
    var_99 = calculate_var(pnl_distributions, 0.99) if pnl_distributions else 0
    cvar_95 = calculate_cvar(pnl_distributions, 0.95) if pnl_distributions else 0
    cvar_99 = calculate_cvar(pnl_distributions, 0.99) if pnl_distributions else 0

    sorted_pnl = sorted(pnl_distributions) if pnl_distributions else [0]
    max_drawdown = abs(sorted_pnl[0]) if sorted_pnl else 0
    mean_pnl = sum(pnl_distributions) / len(pnl_distributions) if pnl_distributions else 0
    std_pnl = (sum((x - mean_pnl) ** 2 for x in pnl_distributions) / max(len(pnl_distributions) - 1, 1)) ** 0.5 if pnl_distributions else 1
    sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0

    if step_log:
        step_log(f"ComputeVaR: VaR95={var_95:,.0f} VaR99={var_99:,.0f} "
                 f"CVaR95={cvar_95:,.0f}",
                 level="success")

    return {
        "metrics": {
            "var_95": round(var_95),
            "var_99": round(var_99),
            "cvar_95": round(cvar_95),
            "cvar_99": round(cvar_99),
            "expected_shortfall": round(cvar_99),
            "max_drawdown": round(max_drawdown),
            "sharpe_ratio": round(sharpe, 4),
        }
    }


def handle_compute_greeks(params: dict[str, Any]) -> dict[str, Any]:
    """Compute portfolio Greeks via finite differences."""
    positions = params.get("positions", [])
    cholesky = params.get("cholesky", [])
    step_log = params.get("_step_log")

    if isinstance(positions, str):
        positions = json.loads(positions)
    if isinstance(cholesky, str):
        cholesky = json.loads(cholesky)

    greeks = compute_finite_difference_greeks(positions, cholesky)

    if step_log:
        step_log(f"ComputeGreeks: portfolio_delta={greeks['portfolio_delta']:,.2f} "
                 f"portfolio_vega={greeks['portfolio_vega']:,.2f}",
                 level="success")

    return {"greeks": greeks}


# ---------------------------------------------------------------------------
# RegistryRunner dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.ComputeVaR": handle_compute_var,
    f"{NAMESPACE}.ComputeGreeks": handle_compute_greeks,
}


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_analytics_handlers(poller) -> None:
    """Register all analytics handlers with the poller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
