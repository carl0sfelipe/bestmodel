"""Reputation-scaled posting limits (S20 anti-abuse).

L02: claim/vote rate limits scale with reputation — new accounts get low
ceilings, proven accounts get headroom. Pure module; the API layer enforces
by counting rows inside the sliding window.
"""

from __future__ import annotations

CLAIMS_PER_24H: dict[str, int] = {"L0": 2, "L1": 5, "L2": 10, "L3": 25, "L4": 50}
VOTES_PER_HOUR: dict[str, int] = {"L0": 5, "L1": 15, "L2": 40, "L3": 100, "L4": 250}


def claim_limit(tier: str | None) -> int:
    return CLAIMS_PER_24H.get(tier or "L0", CLAIMS_PER_24H["L0"])


def vote_limit(tier: str | None) -> int:
    return VOTES_PER_HOUR.get(tier or "L0", VOTES_PER_HOUR["L0"])
