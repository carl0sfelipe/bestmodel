"""Reputation point policy for settlement events (S16).

Pure module so thresholds stay testable and tunable in one place. The tier
ladder mirrors the trust tiers L0–L4 used across the platform; vote weight
(see public-api ``compute_vote_tally``) reads the resulting tier.
"""

from __future__ import annotations

POINTS_CLAIM_SETTLED_VERIFIED = 25
POINTS_DISPUTED_SETTLE_BONUS = 15  # settled a claim the community deemed impossible
POINTS_VERIFIED_RUN_PUBLISHED = 10

# (tier, minimum points) — first match wins when scanned top-down.
TIER_THRESHOLDS: tuple[tuple[str, int], ...] = (
    ("L4", 1500),
    ("L3", 750),
    ("L2", 340),
    ("L1", 100),
    ("L0", 0),
)


def tier_for_points(points: int) -> str:
    for tier, minimum in TIER_THRESHOLDS:
        if points >= minimum:
            return tier
    return "L0"
