"""Core math utilities for Monte Carlo risk analysis.

Provides Geometric Brownian Motion simulation, Cholesky decomposition,
Value-at-Risk / Conditional VaR calculations, and finite-difference Greeks.

Uses only the Python standard library (math, random) so no external
dependencies are required.
"""

from __future__ import annotations

import math
import random
from typing import Any


def _mat_mul_vec(matrix: list[list[float]], vec: list[float]) -> list[float]:
    """Multiply a square matrix by a column vector."""
    return [sum(row[j] * vec[j] for j in range(len(vec))) for row in matrix]


def generate_correlated_gbm_paths(
    positions: list[dict[str, Any]],
    cholesky: list[list[float]],
    num_paths: int,
    horizon_days: int,
    seed: int,
) -> list[float]:
    """Geometric Brownian Motion with Cholesky-correlated random walks.

    Returns a list of per-path portfolio PnL values.
    """
    rng = random.Random(seed)
    n_assets = len(positions)
    dt = 1.0 / 252  # daily time step

    pnl_paths: list[float] = []
    for _ in range(num_paths):
        portfolio_pnl = 0.0
        z_uncorr = [rng.gauss(0.0, 1.0) for _ in range(n_assets)]
        z_corr = _mat_mul_vec(cholesky, z_uncorr)

        for i, pos in enumerate(positions):
            mu = pos.get("expected_return", 0.08)
            sigma = pos.get("volatility", 0.20)
            value = pos.get("value", 0.0)

            total_drift = (mu - 0.5 * sigma**2) * dt * horizon_days
            total_diffusion = sigma * math.sqrt(dt * horizon_days) * z_corr[i]
            price_ratio = math.exp(total_drift + total_diffusion)
            portfolio_pnl += value * (price_ratio - 1.0)

        pnl_paths.append(portfolio_pnl)

    return pnl_paths


def compute_cholesky(correlation_matrix: list[list[float]]) -> list[list[float]]:
    """Cholesky decomposition of correlation matrix (Cholesky-Banachiewicz)."""
    n = len(correlation_matrix)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(correlation_matrix[i][i] - s, 0.0))
            else:
                L[i][j] = (correlation_matrix[i][j] - s) / L[j][j] if L[j][j] else 0.0
    return L


def calculate_var(pnl_distribution: list[float], confidence: float) -> float:
    """Value-at-Risk at given confidence level.

    Returns the loss threshold (negative = loss) at the given confidence.
    """
    sorted_pnl = sorted(pnl_distribution)
    index = int((1 - confidence) * len(sorted_pnl))
    index = max(0, min(index, len(sorted_pnl) - 1))
    return sorted_pnl[index]


def calculate_cvar(pnl_distribution: list[float], confidence: float) -> float:
    """Conditional VaR (Expected Shortfall).

    Mean of losses beyond the VaR threshold.
    """
    var = calculate_var(pnl_distribution, confidence)
    tail = [x for x in pnl_distribution if x <= var]
    if not tail:
        return var
    return sum(tail) / len(tail)


def compute_finite_difference_greeks(
    positions: list[dict[str, Any]],
    cholesky: list[list[float]],
    bump: float = 0.01,
) -> dict[str, Any]:
    """Delta, Gamma, Vega via finite differences.

    Computes per-asset sensitivities by bumping price and volatility.
    """
    deltas: list[float] = []
    gammas: list[float] = []
    vegas: list[float] = []
    portfolio_delta = 0.0
    portfolio_vega = 0.0

    for pos in positions:
        value = pos.get("value", 0.0)
        sigma = pos.get("volatility", 0.20)

        # Delta: dV/dS ≈ (V(S+h) - V(S-h)) / (2h)
        up_value = value * (1 + bump)
        down_value = value * (1 - bump)
        delta = (up_value - down_value) / (2 * bump * value) if value else 0.0
        deltas.append(round(delta, 6))
        portfolio_delta += delta * value

        # Gamma: d²V/dS² ≈ (V(S+h) - 2V(S) + V(S-h)) / h²
        gamma = (up_value - 2 * value + down_value) / (bump * value) ** 2 if value else 0.0
        gammas.append(round(gamma, 6))

        # Vega: dV/dσ ≈ value * sqrt(T) * sigma
        vega = value * math.sqrt(10.0 / 252) * sigma
        vegas.append(round(vega, 2))
        portfolio_vega += vega

    return {
        "delta": deltas,
        "gamma": gammas,
        "vega": vegas,
        "portfolio_delta": round(portfolio_delta, 2),
        "portfolio_vega": round(portfolio_vega, 2),
    }
