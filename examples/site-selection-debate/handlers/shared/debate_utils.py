"""Site-selection debate utilities -- deterministic stubs for testing.

Uses only hashlib and json from stdlib.  12 functions that produce
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


_AGENT_ROLES = ["financial_analyst", "community_analyst", "competitive_strategist"]


# ---------------------------------------------------------------------------
# Spatial (3 functions)
# ---------------------------------------------------------------------------


def score_candidate(
    candidate_id: str,
    demographics: dict | None = None,
    competition: dict | None = None,
    weights: dict | None = None,
    penalty: float = 0.0,
) -> dict:
    """Score a candidate site; weighted scoring with penalty adjustment.

    Returns a SpatialScore dict.
    """
    if demographics is None:
        demographics = {}
    if competition is None:
        competition = {}
    if weights is None:
        weights = {"demographics": 0.4, "competition": 0.3, "accessibility": 0.3}
    seed = f"score:{candidate_id}"
    demo_score = _hash_float(f"{seed}:demo", 40.0, 95.0)
    comp_score = _hash_float(f"{seed}:comp", 30.0, 90.0)
    access_score = _hash_float(f"{seed}:access", 50.0, 98.0)
    w_demo = weights.get("demographics", 0.4)
    w_comp = weights.get("competition", 0.3)
    w_access = weights.get("accessibility", 0.3)
    overall = (demo_score * w_demo + comp_score * w_comp + access_score * w_access) + penalty
    return {
        "candidate_id": candidate_id,
        "demographics_score": round(demo_score, 2),
        "competition_score": round(comp_score, 2),
        "accessibility_score": round(access_score, 2),
        "overall_score": round(max(0.0, min(100.0, overall)), 2),
        "penalty_applied": round(penalty, 2),
    }


def rank_candidates(
    scores: list,
    top_n: int = 5,
    weights: dict | None = None,
) -> tuple[list, str]:
    """Rank candidates by overall_score; returns (ranked_list, top_candidate)."""
    if isinstance(scores, str):
        scores = json.loads(scores)
    ranked = sorted(
        scores, key=lambda s: s.get("overall_score", 0) if isinstance(s, dict) else 0, reverse=True
    )
    ranked = ranked[:top_n]
    top = ranked[0].get("candidate_id", "unknown") if ranked else "unknown"
    return ranked, top


def compute_accessibility(
    candidate_id: str,
    location: dict | None = None,
) -> dict:
    """Compute accessibility metrics; returns AccessibilityMetrics dict."""
    if location is None:
        location = {}
    seed = f"access:{candidate_id}"
    walk_score = _hash_int(seed, 20, 100)
    transit_coverage = _hash_float(f"{seed}:transit", 0.1, 0.95)
    highway_distance = _hash_float(f"{seed}:highway", 0.5, 25.0)
    return {
        "candidate_id": candidate_id,
        "walk_score": walk_score,
        "transit_coverage": round(transit_coverage, 4),
        "highway_distance_km": round(highway_distance, 2),
    }


# ---------------------------------------------------------------------------
# Research (3 functions)
# ---------------------------------------------------------------------------


def search_market_trends(
    candidate_id: str,
    market_area: str = "default",
) -> dict:
    """Search market trends; returns MarketResearch dict."""
    seed = f"market:{candidate_id}:{market_area}"
    growth_rate = _hash_float(seed, -0.05, 0.15)
    risk_factors = [f"risk_{i}_{market_area}" for i in range(_hash_int(f"{seed}:risks", 1, 4))]
    opportunity_score = _hash_float(f"{seed}:opp", 30.0, 95.0)
    return {
        "candidate_id": candidate_id,
        "growth_rate": round(growth_rate, 4),
        "risk_factors": risk_factors,
        "opportunity_score": round(opportunity_score, 2),
        "market_area": market_area,
    }


def gather_regulations(
    candidate_id: str,
    jurisdiction: str = "default",
) -> dict:
    """Gather regulations; returns RegulationSummary dict."""
    seed = f"regs:{candidate_id}:{jurisdiction}"
    permit_difficulty = _hash_int(seed, 1, 10)
    zoning_seed = f"{seed}:zone"
    zoning_compatible = _hash_int(zoning_seed, 0, 1) == 1
    regulatory_score = _hash_float(f"{seed}:reg", 20.0, 95.0)
    return {
        "candidate_id": candidate_id,
        "permit_difficulty": permit_difficulty,
        "zoning_compatible": zoning_compatible,
        "regulatory_score": round(regulatory_score, 2),
        "jurisdiction": jurisdiction,
    }


def analyze_competitors(
    candidate_id: str,
    radius_km: float = 5.0,
) -> tuple[list, str]:
    """Analyze competitors; returns (competitor_list, threat_level)."""
    seed = f"comp:{candidate_id}:{radius_km}"
    n_competitors = _hash_int(seed, 0, 8)
    competitors = [
        {
            "name": f"competitor_{i}",
            "distance_km": round(_hash_float(f"{seed}:d{i}", 0.2, radius_km), 2),
            "market_share": round(_hash_float(f"{seed}:ms{i}", 0.02, 0.25), 4),
        }
        for i in range(n_competitors)
    ]
    threat = "low" if n_competitors <= 2 else ("medium" if n_competitors <= 5 else "high")
    return competitors, threat


# ---------------------------------------------------------------------------
# Debate (3 functions)
# ---------------------------------------------------------------------------


def present_analysis(
    agent_role: str,
    candidate_id: str,
    spatial_score: dict | None = None,
    market_data: dict | None = None,
    round_num: int = 1,
) -> dict:
    """Present analysis; confidence = base + round_num * 0.05.

    Returns an AgentPosition dict.
    """
    if spatial_score is None:
        spatial_score = {}
    if market_data is None:
        market_data = {}
    seed = f"present:{agent_role}:{candidate_id}:{round_num}"
    base_confidence = _hash_float(seed, 0.5, 0.8)
    confidence = min(1.0, base_confidence + round_num * 0.05)
    return {
        "agent_role": agent_role,
        "candidate_id": candidate_id,
        "position": f"{agent_role} evaluates {candidate_id} (round {round_num})",
        "confidence": round(confidence, 4),
        "key_factors": [f"factor_{i}_{agent_role}" for i in range(3)],
    }


def challenge_position(
    agent_role: str,
    target_role: str,
    target_position: dict | str = "",
    round_num: int = 1,
) -> tuple[str, list]:
    """Challenge another agent's position; returns (rebuttal, weaknesses)."""
    seed = f"challenge:{agent_role}:{target_role}:{round_num}"
    n_weaknesses = _hash_int(seed, 1, 3)
    if isinstance(target_position, dict):
        pos_str = target_position.get("position", str(target_position))
    else:
        pos_str = str(target_position)
    rebuttal = f"{agent_role} challenges {target_role}: '{pos_str}' has gaps"
    weaknesses = [f"weakness_{i}_by_{agent_role}" for i in range(n_weaknesses)]
    return rebuttal, weaknesses


def score_arguments(
    positions: list,
    challenges: list,
    prev_rankings: dict | None = None,
    round_num: int = 1,
) -> dict:
    """Score arguments; returns RoundRankings dict with consensus_level, score_delta, converged."""
    if prev_rankings is None:
        prev_rankings = {}
    seed = f"score_args:{round_num}"
    consensus_level = _hash_float(f"{seed}:consensus", 0.3, 0.95)
    prev_consensus = prev_rankings.get("consensus_level", 0.5)
    score_delta = abs(consensus_level - prev_consensus)
    converged = score_delta < 0.1
    agent_scores = []
    for i, pos in enumerate(positions):
        agent_role = pos.get("agent_role", f"agent_{i}") if isinstance(pos, dict) else f"agent_{i}"
        s = _hash_float(f"{seed}:agent:{agent_role}", 60.0, 95.0)
        agent_scores.append(
            {
                "agent_role": agent_role,
                "score": round(s, 2),
            }
        )
    return {
        "consensus_level": round(consensus_level, 4),
        "score_delta": round(score_delta, 4),
        "converged": converged,
        "agent_scores": agent_scores,
        "round_num": round_num,
    }


# ---------------------------------------------------------------------------
# Synthesis (3 functions)
# ---------------------------------------------------------------------------


def summarize_round(
    positions: list,
    challenges: list,
    rankings: dict | None = None,
    round_num: int = 1,
) -> tuple[str, list]:
    """Summarize round; returns (synthesis_str, key_arguments_list)."""
    n_pos = len(positions) if isinstance(positions, list) else 0
    n_ch = len(challenges) if isinstance(challenges, list) else 0
    synthesis = f"Round {round_num}: {n_pos} positions, {n_ch} challenges"
    key_arguments = [f"argument_{i}_round_{round_num}" for i in range(min(n_pos, 3))]
    return synthesis, key_arguments


def produce_ranking(
    round_syntheses: list,
    final_rankings: dict | None = None,
    candidate_scores: list | None = None,
) -> tuple[list, str, float]:
    """Produce final ranking; returns (ranked, top_candidate, confidence)."""
    if candidate_scores is None:
        candidate_scores = []
    if final_rankings is None:
        final_rankings = {}
    ranked = sorted(
        candidate_scores,
        key=lambda s: s.get("overall_score", 0) if isinstance(s, dict) else 0,
        reverse=True,
    )
    top = ranked[0].get("candidate_id", "unknown") if ranked else "unknown"
    seed = f"produce_rank:{len(round_syntheses)}"
    confidence = _hash_float(seed, 0.6, 0.95)
    return ranked, top, round(confidence, 4)


def generate_report(
    top_candidate: str,
    ranked_candidates: list,
    round_syntheses: list,
    confidence: float = 0.8,
) -> dict:
    """Generate final report; returns FinalReport dict."""
    return {
        "top_candidate": top_candidate,
        "confidence": round(confidence, 4),
        "num_candidates_evaluated": len(ranked_candidates),
        "num_rounds": len(round_syntheses),
        "ranked_candidates": ranked_candidates,
        "round_summaries": round_syntheses,
        "recommendation": f"Recommend site '{top_candidate}' with {round(confidence * 100, 1)}% confidence",
    }
