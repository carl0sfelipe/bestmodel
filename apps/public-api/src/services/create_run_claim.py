"""Run-claim creation with frozen prior snapshot (S15)."""

from __future__ import annotations

import uuid
from typing import Any

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError, hours_ago_iso, utcnow_iso
from src.services.claim_view import claim_view
from src.services.compute_claim_prior import compute_claim_prior


def create_run_claim(
    session: DatabaseSession,
    caller: dict,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from src.services.rate_limit_policy import claim_limit

    reputation = session.fetch_reputation_by_user(caller["id"])
    tier = reputation["tier"] if reputation else "L0"
    used = session.count_claims_since(caller["id"], hours_ago_iso(24))
    if used >= claim_limit(tier):
        raise AuthError(
            429,
            f"claim limit reached ({claim_limit(tier)} per 24h at {tier}); "
            "verified runs raise your ceiling",
        )

    metrics = payload.get("claimed_metrics") or {}
    if "decode_tok_s" not in metrics:
        raise AuthError(400, "claimed_metrics must include decode_tok_s")
    _reject_non_positive(metrics)

    model = session.fetch_model_by_id(payload["model_release_id"])
    if model is None:
        raise AuthError(404, f"unknown model_release_id: {payload['model_release_id']}")

    rig_id = None
    if payload.get("rig_slug"):
        rig = session.find_rig_by_slug(payload["rig_slug"])
        if rig is None or rig["owner_id"] != caller["id"]:
            raise AuthError(404, f"rig not found for this account: {payload['rig_slug']}")
        rig_id = rig["id"]

    if payload.get("quantization_profile_id"):
        quant = session.fetch_quantization_profile_by_id(payload["quantization_profile_id"])
        if quant is None:
            raise AuthError(404, "unknown quantization_profile_id")

    prior = compute_claim_prior(
        session,
        payload["model_release_id"],
        payload.get("quantization_profile_id"),
        payload.get("gpu_model_id"),
        payload.get("context_tokens"),
    )

    now = utcnow_iso()
    record = {
        "id": str(uuid.uuid4()),
        "claimant_id": caller["id"],
        "rig_id": rig_id,
        "model_release_id": payload["model_release_id"],
        "quantization_profile_id": payload.get("quantization_profile_id"),
        "inference_runtime_id": payload.get("inference_runtime_id"),
        "gpu_model_id": payload.get("gpu_model_id"),
        "context_tokens": payload.get("context_tokens"),
        "claimed_metrics": metrics,
        "note": payload.get("note"),
        "status": "open",
        "prior_snapshot": prior,
        "created_at": now,
        "updated_at": now,
    }
    session.insert_run_claim(record)
    session.commit()
    return claim_view(record, votes=[])


def _reject_non_positive(metrics: dict) -> None:
    for key, value in metrics.items():
        if isinstance(value, (int, float)) and value <= 0:
            raise AuthError(400, f"claimed metric {key} must be positive")
