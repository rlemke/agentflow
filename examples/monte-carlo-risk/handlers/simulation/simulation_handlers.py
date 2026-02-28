"""Event facet handlers for Monte Carlo simulation.

Handles SimulateBatch and SimulateStress event facets.
"""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.math_utils import generate_correlated_gbm_paths

NAMESPACE = "risk.Simulation"


def handle_simulate_batch(params: dict[str, Any]) -> dict[str, Any]:
    """Run a batch of correlated GBM simulations."""
    positions = params.get("positions", [])
    cholesky = params.get("cholesky", [])
    num_paths = int(params.get("num_paths", 1000))
    horizon_days = int(params.get("time_horizon_days", 10))
    batch_id = int(params.get("batch_id", 0))
    seed = int(params.get("random_seed", 42))
    step_log = params.get("_step_log")

    if isinstance(positions, str):
        positions = json.loads(positions)
    if isinstance(cholesky, str):
        cholesky = json.loads(cholesky)

    pnl = generate_correlated_gbm_paths(positions, cholesky, num_paths, horizon_days, seed)

    mean_pnl = sum(pnl) / len(pnl) if pnl else 0
    worst_pnl = min(pnl) if pnl else 0

    if step_log:
        step_log(
            f"SimulateBatch: batch={batch_id} paths={num_paths} "
            f"mean_pnl={mean_pnl:,.0f} worst={worst_pnl:,.0f}",
            level="success",
        )

    return {
        "result": {
            "batch_id": batch_id,
            "num_paths": num_paths,
            "pnl_distribution": pnl,
            "mean_pnl": round(mean_pnl),
            "worst_pnl": round(worst_pnl),
        }
    }


def handle_simulate_stress(params: dict[str, Any]) -> dict[str, Any]:
    """Apply shock factors to portfolio positions."""
    positions = params.get("positions", [])
    scenario_name = params.get("scenario_name", "unknown")
    shock_factors = params.get("shock_factors", [])
    step_log = params.get("_step_log")

    if isinstance(positions, str):
        positions = json.loads(positions)
    if isinstance(shock_factors, str):
        shock_factors = json.loads(shock_factors)

    total_pnl = 0.0
    worst_pos = {"name": "", "pnl": float("inf")}
    best_pos = {"name": "", "pnl": float("-inf")}

    for i, pos in enumerate(positions):
        shock = shock_factors[i] if i < len(shock_factors) else 0.0
        value = pos.get("value", 0.0)
        pos_pnl = value * shock
        total_pnl += pos_pnl

        asset_id = pos.get("asset_id", f"asset_{i}")
        if pos_pnl < worst_pos["pnl"]:
            worst_pos = {"name": asset_id, "pnl": pos_pnl}
        if pos_pnl > best_pos["pnl"]:
            best_pos = {"name": asset_id, "pnl": pos_pnl}

    if step_log:
        step_log(
            f"SimulateStress: scenario={scenario_name} portfolio_pnl={total_pnl:,.0f}",
            level="success",
        )

    return {
        "result": {
            "scenario_name": scenario_name,
            "portfolio_pnl": round(total_pnl),
            "worst_position": worst_pos["name"],
            "best_position": best_pos["name"],
        }
    }


# ---------------------------------------------------------------------------
# RegistryRunner dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.SimulateBatch": handle_simulate_batch,
    f"{NAMESPACE}.SimulateStress": handle_simulate_stress,
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


def register_simulation_handlers(poller) -> None:
    """Register all simulation handlers with the poller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
