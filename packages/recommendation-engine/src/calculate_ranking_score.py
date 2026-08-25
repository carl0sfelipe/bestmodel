"""Balanced ranking score (plan section 11.10).

Score = 0.30*Decode + 0.20*Prefill + 0.15*ContextCapacity
      + 0.15*QualityRetention + 0.10*EnergyEfficiency + 0.10*Trust

Every sub-score is normalized with robust_min_max(value, p5, p95) over the
candidate set; infeasible candidates are zeroed (section 11.10).
"""

from __future__ import annotations

import math
from typing import Any

BALANCED_WEIGHTS = {
    "decode": 0.30,
    "prefill": 0.20,
    "context_capacity": 0.15,
    "quality_retention": 0.15,
    "energy_efficiency": 0.10,
    "trust": 0.10,
}


def robust_min_max(value: float, p5: float, p95: float) -> float:
    """Robust min-max normalization clamped to [0, 1]. Returns 1.0 when the
    range has no dispersion (p95 == p5) per section 11.10."""
    if p95 == p5:
        return 1.0
    return max(0.0, min(1.0, (value - p5) / (p95 - p5)))


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile of a non-empty value list."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def energy_efficiency(candidate: dict[str, Any]) -> float:
    power = candidate.get("power_watt_avg") or 0.0
    if power <= 0:
        return 0.0
    return (candidate.get("decode_tok_s") or 0.0) / power


def _dimension_values(candidates: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    dimensions = {
        "decode": [c.get("decode_tok_s") or 0.0 for c in candidates],
        "prefill": [c.get("prefill_tok_s") or 0.0 for c in candidates],
        "context_capacity": [float(c.get("context_tokens") or 0) for c in candidates],
        "quality_retention": [c.get("quality_retention_estimate") or 0.0 for c in candidates],
        "energy_efficiency": [energy_efficiency(c) for c in candidates],
        "trust": [c.get("trust_score") or 0.0 for c in candidates],
    }
    return {
        name: (percentile(values, 5), percentile(values, 95))
        for name, values in dimensions.items()
    }


def _sub_scores(candidate: dict[str, Any], ranges: dict[str, tuple[float, float]]) -> float:
    values = {
        "decode": candidate.get("decode_tok_s") or 0.0,
        "prefill": candidate.get("prefill_tok_s") or 0.0,
        "context_capacity": float(candidate.get("context_tokens") or 0),
        "quality_retention": candidate.get("quality_retention_estimate") or 0.0,
        "energy_efficiency": energy_efficiency(candidate),
        "trust": candidate.get("trust_score") or 0.0,
    }
    return sum(
        BALANCED_WEIGHTS[name] * robust_min_max(values[name], ranges[name][0], ranges[name][1])
        for name in BALANCED_WEIGHTS
    )


def calculate_ranking_score(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each candidate with rank_score. Normalization ranges are
    computed over the feasible subset; infeasible candidates score exactly 0."""
    scored = [dict(candidate) for candidate in candidates]
    feasible = [c for c in scored if c.get("feasible", True)]
    ranges = _dimension_values(feasible) if feasible else {}
    for candidate in scored:
        if not candidate.get("feasible", True) or not feasible:
            candidate["rank_score"] = 0.0
        else:
            candidate["rank_score"] = round(_sub_scores(candidate, ranges), 6)
    return scored
