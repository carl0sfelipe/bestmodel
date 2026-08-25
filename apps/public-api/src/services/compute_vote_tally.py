"""Pure vote-tally math for claim plausibility voting (S15).

L02 rules enforced here:

- Weight derives from the voter's reputation tier and is bounded to (0, 1]
  ("a single whale cannot flip a verdict alone": one vote can never move the
  margin by more than MAX_WEIGHT).
- Margin = plausible weight - impossible weight. Sign is the community's
  current verdict; magnitude is its strength.
"""

from __future__ import annotations

from typing import Any

MAX_WEIGHT = 1.0
MIN_WEIGHT = 0.2

TIER_WEIGHTS: dict[str, float] = {
    "L0": 0.2,
    "L1": 0.4,
    "L2": 0.6,
    "L3": 0.8,
    "L4": 1.0,
}

VERDICTS = ("plausible", "impossible")


def weight_for_tier(tier: str | None) -> float:
    """Map a trust tier to vote weight; unknown/missing tiers get the floor."""
    return TIER_WEIGHTS.get(tier or "L0", MIN_WEIGHT)


def tally(votes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one-vote-per-voter rows into the public tally payload."""
    plausible_weight = 0.0
    impossible_weight = 0.0
    plausible_count = 0
    impossible_count = 0
    for vote in votes:
        if vote["verdict"] == "plausible":
            plausible_weight += float(vote["weight"])
            plausible_count += 1
        else:
            impossible_weight += float(vote["weight"])
            impossible_count += 1
    return {
        "voter_count": plausible_count + impossible_count,
        "plausible_count": plausible_count,
        "impossible_count": impossible_count,
        "plausible_weight": round(plausible_weight, 4),
        "impossible_weight": round(impossible_weight, 4),
        "margin": round(plausible_weight - impossible_weight, 4),
    }


def margin(votes: list[dict[str, Any]]) -> float:
    return tally(votes)["margin"]
