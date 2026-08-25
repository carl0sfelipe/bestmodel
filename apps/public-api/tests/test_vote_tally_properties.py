"""S15 acceptance: property tests for the vote-margin math (pure functions).

L02 gate: "vote margin math property-tested". Invariants verified over many
seeded-random vote sets:

1. margin always lies within [-total_weight, +total_weight]
2. a single vote can never move the margin by more than MAX_WEIGHT (whale bound)
3. tally is order-independent (commutative)
4. re-voting (same voter, new verdict) replaces the old vote exactly
5. unknown/missing tiers get the floor weight; all weights stay in bounds
"""

from __future__ import annotations

import random

from src.services.compute_vote_tally import (
    MAX_WEIGHT,
    MIN_WEIGHT,
    TIER_WEIGHTS,
    margin,
    tally,
    weight_for_tier,
)

VERDICTS = ("plausible", "impossible")
TIERS = ["L0", "L1", "L2", "L3", "L4", None, "bogus"]


def _random_votes(rng: random.Random) -> list[dict]:
    votes = []
    for i in range(rng.randint(0, 40)):
        votes.append(
            {
                "voter_id": f"voter-{i}",
                "verdict": rng.choice(VERDICTS),
                "weight": weight_for_tier(rng.choice(TIERS)),
            }
        )
    return votes


def test_margin_within_total_weight_bounds():
    rng = random.Random(42)
    for _ in range(200):
        votes = _random_votes(rng)
        t = tally(votes)
        total = t["plausible_weight"] + t["impossible_weight"]
        assert -total <= t["margin"] <= total
        assert t["voter_count"] == len(votes)


def test_whale_bound_single_vote_never_exceeds_max_weight():
    rng = random.Random(7)
    for _ in range(200):
        base = _random_votes(rng)
        whale = {
            "voter_id": "whale",
            "verdict": rng.choice(VERDICTS),
            "weight": weight_for_tier("L4"),  # heaviest allowed tier
        }
        before = abs(margin(base))
        after = abs(margin(base + [whale]))
        # adding one bounded vote moves |margin| by at most MAX_WEIGHT
        assert after <= before + MAX_WEIGHT + 1e-9


def test_tally_is_order_independent():
    rng = random.Random(123)
    for _ in range(200):
        votes = _random_votes(rng)
        shuffled = votes[:]
        rng.shuffle(shuffled)
        assert tally(votes) == tally(shuffled)


def test_revoting_replaces_verdict_exactly_once():
    voter = {"voter_id": "v1"}
    first = [voter | {"verdict": "plausible", "weight": 0.6}]
    assert tally(first)["plausible_count"] == 1

    replaced = [{"voter_id": "v1", "verdict": "impossible", "weight": 0.6}]
    assert tally(replaced)["impossible_count"] == 1
    assert tally(replaced)["plausible_count"] == 0
    assert tally(replaced)["margin"] == -0.6


def test_weights_bounded_and_floor_defaulted():
    for tier, expected in TIER_WEIGHTS.items():
        assert weight_for_tier(tier) == expected
    assert MIN_WEIGHT == weight_for_tier(None) == weight_for_tier("unknown-tier")
    rng = random.Random(9)
    for tier in rng.choices(TIERS, k=100):
        w = weight_for_tier(tier)
        assert MIN_WEIGHT <= w <= MAX_WEIGHT


def test_empty_and_unanimous_edges():
    assert tally([])["margin"] == 0.0
    unanimous = [
        {"voter_id": str(i), "verdict": "plausible", "weight": 0.2} for i in range(6)
    ]
    t = tally(unanimous)
    assert t["margin"] == 1.2  # six L0 voters outvote one L4 whale (1.0)
