"""Event facet handlers for market data loading.

Handles LoadPortfolio and FetchHistoricalData event facets.
"""

from __future__ import annotations

import os
from typing import Any

from handlers.shared.math_utils import compute_cholesky

NAMESPACE = "risk.MarketData"

# Synthetic portfolio with 5 positions
_DEFAULT_PORTFOLIO = {
    "name": "default",
    "positions": [
        {
            "asset_id": "SPY",
            "quantity": 500,
            "price": 450.0,
            "value": 225000.0,
            "volatility": 0.18,
            "expected_return": 0.10,
            "asset_class": "equity_index",
        },
        {
            "asset_id": "AAPL",
            "quantity": 200,
            "price": 175.0,
            "value": 35000.0,
            "volatility": 0.28,
            "expected_return": 0.12,
            "asset_class": "equity",
        },
        {
            "asset_id": "GOOGL",
            "quantity": 100,
            "price": 140.0,
            "value": 14000.0,
            "volatility": 0.30,
            "expected_return": 0.11,
            "asset_class": "equity",
        },
        {
            "asset_id": "TLT",
            "quantity": 300,
            "price": 100.0,
            "value": 30000.0,
            "volatility": 0.15,
            "expected_return": 0.04,
            "asset_class": "bond",
        },
        {
            "asset_id": "GLD",
            "quantity": 150,
            "price": 185.0,
            "value": 27750.0,
            "volatility": 0.16,
            "expected_return": 0.06,
            "asset_class": "commodity",
        },
    ],
    "base_currency": "USD",
    "valuation_date": "2026-02-26",
    "total_value": 331750,
}

# Realistic correlation structure: equities correlated, bonds inverse, gold low
_DEFAULT_CORRELATION = [
    [1.00, 0.75, 0.72, -0.30, 0.05],  # SPY
    [0.75, 1.00, 0.65, -0.20, 0.08],  # AAPL
    [0.72, 0.65, 1.00, -0.25, 0.03],  # GOOGL
    [-0.30, -0.20, -0.25, 1.00, 0.15],  # TLT
    [0.05, 0.08, 0.03, 0.15, 1.00],  # GLD
]


def handle_load_portfolio(params: dict[str, Any]) -> dict[str, Any]:
    """Load portfolio by name. Returns synthetic default portfolio."""
    portfolio_name = params.get("portfolio_name", "default")
    step_log = params.get("_step_log")

    portfolio = dict(_DEFAULT_PORTFOLIO)
    portfolio["name"] = portfolio_name

    if step_log:
        step_log(
            f"LoadPortfolio: {portfolio_name} — "
            f"{len(portfolio['positions'])} positions, "
            f"total_value={portfolio['total_value']:,}",
            level="success",
        )

    return {"portfolio": portfolio}


def handle_fetch_historical_data(params: dict[str, Any]) -> dict[str, Any]:
    """Generate synthetic correlation matrix and Cholesky decomposition."""
    asset_ids = params.get("asset_ids", [])
    lookback_days = params.get("lookback_days", 252)
    step_log = params.get("_step_log")

    n = len(asset_ids) if isinstance(asset_ids, list) else 5
    # Use default correlation for 5 assets, truncate/pad as needed
    corr = _DEFAULT_CORRELATION
    if n < 5:
        corr = [row[:n] for row in corr[:n]]
    elif n > 5:
        # Extend with identity for extra assets
        corr = [row + [0.0] * (n - 5) for row in corr]
        for i in range(5, n):
            corr.append([0.0] * i + [1.0] + [0.0] * (n - i - 1))

    chol = compute_cholesky(corr)
    ids = (
        [
            p.get("asset_id", f"asset_{i}") if isinstance(p, dict) else str(p)
            for i, p in enumerate(asset_ids)
        ]
        if isinstance(asset_ids, list)
        else []
    )

    if step_log:
        step_log(f"FetchHistoricalData: {n} assets, lookback={lookback_days} days", level="success")

    return {
        "correlation": {
            "matrix": corr,
            "asset_ids": ids,
            "cholesky": chol,
        }
    }


# ---------------------------------------------------------------------------
# RegistryRunner dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.LoadPortfolio": handle_load_portfolio,
    f"{NAMESPACE}.FetchHistoricalData": handle_fetch_historical_data,
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


def register_market_data_handlers(poller) -> None:
    """Register all market data handlers with the poller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
