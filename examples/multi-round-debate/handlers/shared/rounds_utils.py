"""Core round utilities -- deterministic stubs for testing.

Uses only hashlib and json from stdlib.  8 functions that produce
consistent, reproducible output from the same inputs.

Designed for real LLM dispatch when an Anthropic client is available;
these stubs provide synthetic fallback for testing.
"""

from __future__ import annotations

import hashlib

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


_STANCES = ["for", "against", "neutral"]
_AGENTS = ["agent_0", "agent_1", "agent_2"]


# ---------------------------------------------------------------------------
# Public API (one per event facet)
# ---------------------------------------------------------------------------


def initiate_round(
    topic: str,
    round_num: int = 1,
    num_agents: int = 3,
    prev_synthesis: str = "",
    prev_scores: list | None = None,
) -> dict:
    """Initialize a debate round with context from previous rounds.

    Returns a RoundState dict.
    """
    if prev_scores is None:
        prev_scores = []
    agents = [f"agent_{i}" for i in range(num_agents)]
    _seed = f"initiate:{topic}:{round_num}"
    return {
        "round_num": round_num,
        "topic": topic,
        "agents": agents,
        "prev_synthesis": prev_synthesis,
        "prev_scores": prev_scores,
        "round_summary": f"Round {round_num} on '{topic}' with {num_agents} agents",
    }


def assign_positions(
    round_state: dict,
    round_num: int = 1,
) -> list[dict]:
    """Assign positions with stance cycling via round_num % 3."""
    agents = round_state.get("agents", _AGENTS[:])
    assignments = []
    for i, agent in enumerate(agents):
        stance_idx = (i + round_num) % 3
        stance = _STANCES[stance_idx]
        assignments.append(
            {
                "agent": agent,
                "stance": stance,
                "round_num": round_num,
            }
        )
    return assignments


def refine_argument(
    agent: str,
    topic: str,
    stance: str,
    round_num: int = 1,
    prev_synthesis: str = "",
) -> dict:
    """Refine an argument; confidence = base + round_num * 0.05."""
    seed = f"refine:{agent}:{topic}:{stance}:{round_num}"
    base_confidence = _hash_float(seed, 0.5, 0.8)
    confidence = min(1.0, base_confidence + round_num * 0.05)
    return {
        "agent": agent,
        "stance": stance,
        "argument": f"{agent} argues {stance} on '{topic}' (round {round_num})",
        "confidence": round(confidence, 4),
    }


def challenge_argument(
    agent: str,
    target_agent: str,
    target_argument: str,
    round_num: int = 1,
) -> dict:
    """Challenge another agent's argument with counter-claims."""
    seed = f"challenge:{agent}:{target_agent}:{round_num}"
    n_weaknesses = _hash_int(seed, 1, 3)
    if isinstance(target_argument, dict):
        target_argument = target_argument.get("argument", str(target_argument))
    return {
        "challenge": f"{agent} challenges {target_agent}: '{target_argument}' has gaps",
        "weaknesses": [f"weakness_{i}_by_{agent}" for i in range(n_weaknesses)],
    }


def score_round(
    arguments: list,
    challenges: list,
    prev_scores: list | None = None,
    round_num: int = 1,
) -> list[dict]:
    """Score the round; improvement = current / prev (division)."""
    if prev_scores is None:
        prev_scores = []
    scores = []
    for i, arg in enumerate(arguments):
        agent = arg.get("agent", f"agent_{i}") if isinstance(arg, dict) else f"agent_{i}"
        seed = f"score:{agent}:{round_num}"
        current = _hash_float(seed, 60.0, 95.0)
        prev = prev_scores[i]["score"] if i < len(prev_scores) else 50.0
        improvement = round(current / max(prev, 1.0), 4)
        scores.append(
            {
                "agent": agent,
                "score": round(current, 2),
                "improvement": improvement,
            }
        )
    return scores


def evaluate_convergence(
    current_scores: list,
    prev_scores: list | None = None,
    round_num: int = 1,
) -> dict:
    """Evaluate convergence; score_delta = abs(curr-prev)/max(prev,1)."""
    if prev_scores is None:
        prev_scores = []
    if not current_scores:
        return {
            "score_delta": 1.0,
            "position_drift": 1.0,
            "agreement_level": 0.0,
            "converged": False,
        }
    avg_current = sum(s["score"] for s in current_scores) / len(current_scores)
    if prev_scores:
        avg_prev = sum(s["score"] for s in prev_scores) / len(prev_scores)
    else:
        avg_prev = 50.0
    score_delta = abs(avg_current - avg_prev) / max(avg_prev, 1.0)
    seed = f"convergence:{round_num}"
    position_drift = _hash_float(seed, 0.0, 0.5)
    agreement_level = 1.0 - score_delta
    converged = score_delta < 0.1
    return {
        "score_delta": round(score_delta, 4),
        "position_drift": round(position_drift, 4),
        "agreement_level": round(agreement_level, 4),
        "converged": converged,
    }


def summarize_round(
    arguments: list,
    challenges: list,
    scores: list,
    round_num: int = 1,
) -> tuple[str, list]:
    """Summarize round; returns (synthesis_str, key_shifts_list)."""
    n_args = len(arguments)
    n_chall = len(challenges)
    synthesis = f"Round {round_num}: {n_args} arguments, {n_chall} challenges"
    key_shifts = [f"shift_{i}_round_{round_num}" for i in range(min(n_args, 3))]
    return synthesis, key_shifts


def declare_outcome(
    round_syntheses: list,
    final_scores: list,
    convergence_trajectory: list,
    topic: str,
) -> dict:
    """Declare outcome with winner and convergence trajectory."""
    if final_scores:
        best = max(final_scores, key=lambda s: s.get("score", 0) if isinstance(s, dict) else 0)
        winner = best.get("agent", "unknown") if isinstance(best, dict) else "unknown"
    else:
        winner = "unknown"
    return {
        "winner": winner,
        "final_synthesis": f"Final outcome for '{topic}': {len(round_syntheses)} rounds completed",
        "convergence_trajectory": convergence_trajectory,
        "total_rounds": len(round_syntheses),
    }
