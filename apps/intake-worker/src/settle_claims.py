"""Claim settlement after validation finishes (S16).

Called by the intake worker once a run reaches a terminal status. Only
**validated** runs settle the linked claim; rejected/quarantined runs leave it
open so the claimant can retry with better evidence.

Reputation follows the L02 incentive rules:
- base credit to the claimant for converting a claim into verified evidence;
- an extra bonus when the community had voted the claim impossible (margin
  below zero at settlement time) — settling disputed claims earns more.
"""

from __future__ import annotations

from typing import Any

from reputation_policy import (
    POINTS_CLAIM_SETTLED_VERIFIED,
    POINTS_DISPUTED_SETTLE_BONUS,
    tier_for_points,
)

STATUS_VALIDATED = "validated"


def settle_claims_for_run(repository, run_id: str, status: str) -> dict[str, Any] | None:
    context = repository.fetch_settlement_context(run_id)
    if context is None or status != STATUS_VALIDATED:
        return None

    events = [("claim_settled_verified", POINTS_CLAIM_SETTLED_VERIFIED)]
    if float(context["margin"]) < 0:
        # The community doubted this claim; proving them wrong is worth extra.
        events.append(("claim_settled_verified", POINTS_DISPUTED_SETTLE_BONUS))

    total_delta = sum(delta for _, delta in events)
    new_tier = tier_for_points(int(context["points"]) + total_delta)
    repository.complete_claim_settlement(
        claim_id=context["claim_id"],
        claimant_id=context["claimant_id"],
        events=events,
        new_points=int(context["points"]) + total_delta,
        new_tier=new_tier,
    )
    return {"claim_id": context["claim_id"], "points_awarded": total_delta, "tier": new_tier}
