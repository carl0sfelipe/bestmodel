"""Voting and retraction on run claims (S15)."""

from __future__ import annotations

import uuid

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError, utcnow_iso
from src.services.claim_view import claim_view
from src.services.compute_vote_tally import weight_for_tier


def vote_on_claim(
    session: DatabaseSession,
    caller: dict,
    claim_id: str,
    verdict: str,
) -> dict:
    claim = _require_open_claim(session, claim_id)
    if claim["claimant_id"] == caller["id"]:
        raise AuthError(400, "the claimant cannot vote on their own claim")

    reputation = session.fetch_reputation_by_user(caller["id"])
    tier = reputation["tier"] if reputation else None
    session.upsert_claim_vote(
        {
            "id": str(uuid.uuid4()),
            "run_claim_id": claim_id,
            "voter_id": caller["id"],
            "verdict": verdict,
            "weight": weight_for_tier(tier),
            "created_at": utcnow_iso(),
        }
    )
    session.commit()
    return claim_view(claim, session.fetch_votes_for_claim(claim_id))


def retract_run_claim(session: DatabaseSession, caller: dict, claim_id: str) -> dict:
    claim = _require_open_claim(session, claim_id)
    if claim["claimant_id"] != caller["id"]:
        raise AuthError(403, "only the claimant can retract a claim")
    session.set_run_claim_status(claim_id, "retracted")
    session.commit()
    return claim_view(session.find_run_claim_by_id(claim_id), [])


def get_claim_with_tally(session: DatabaseSession, claim_id: str) -> dict:
    claim = session.find_run_claim_by_id(claim_id)
    if claim is None:
        raise AuthError(404, f"claim not found: {claim_id}")
    return claim_view(claim, session.fetch_votes_for_claim(claim_id))


def _require_open_claim(session: DatabaseSession, claim_id: str) -> dict:
    claim = session.find_run_claim_by_id(claim_id)
    if claim is None:
        raise AuthError(404, f"claim not found: {claim_id}")
    if claim["status"] != "open":
        raise AuthError(409, f"claim is not open (status: {claim['status']})")
    return claim
