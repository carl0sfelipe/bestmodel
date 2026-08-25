"""Claim view helpers shared by query and vote services (S15)."""

from __future__ import annotations

from typing import Any

from src.services.compute_vote_tally import tally


def claim_view(record: dict, votes: list[dict]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "claimant_id": record["claimant_id"],
        "rig_id": record.get("rig_id"),
        "model_release_id": record["model_release_id"],
        "quantization_profile_id": record.get("quantization_profile_id"),
        "inference_runtime_id": record.get("inference_runtime_id"),
        "gpu_model_id": record.get("gpu_model_id"),
        "context_tokens": record.get("context_tokens"),
        "claimed_metrics": record["claimed_metrics"],
        "note": record.get("note"),
        "status": record["status"],
        "benchmark_run_id": record.get("benchmark_run_id"),
        "prior_snapshot": record["prior_snapshot"],
        "created_at": record.get("created_at"),
        "tally": tally(votes),
    }
