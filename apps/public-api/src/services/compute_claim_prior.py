"""Frozen prior snapshot for new run claims (S15).

At claim creation we record what OUR data says about the asserted setup:

- ``pool``: measured medians from validated runs of the same model (optionally
  same quantization) — the strongest honest signal we have.
- ``roofline``: kernel prediction for the claimed GPU x model x quant, when a
  GPU is resolvable; null otherwise.

The snapshot is written once and never recomputed (L02 rule), so votes are
always judged against the priors the claimant faced at creation time.
"""

from __future__ import annotations

from typing import Any

from benchmark_scenario import BenchmarkScenario
from estimate_decode_throughput import estimate_decode_tokens_per_second
from gpu_spec import GpuSpec
from model_arch import ModelArch, ModelArchitecture
from quant_profile import QuantProfile

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import utcnow_iso

DEFAULT_CONTEXT_TOKENS = 4096


def compute_claim_prior(
    session: DatabaseSession,
    model_release_id: str,
    quantization_profile_id: str | None,
    gpu_model_id: str | None,
    context_tokens: int | None,
) -> dict[str, Any]:
    pool = _pool_prior(session, model_release_id, quantization_profile_id)
    roofline = _roofline_prior(
        session, model_release_id, quantization_profile_id, gpu_model_id, context_tokens
    )
    return {
        "computed_at": utcnow_iso(),
        "pool": pool if pool["run_count"] > 0 else None,
        "roofline": roofline,
    }


def _pool_prior(
    session: DatabaseSession,
    model_release_id: str,
    quantization_profile_id: str | None,
) -> dict[str, Any]:
    row = session.fetch_pool_measurements(model_release_id, quantization_profile_id)
    return {
        "basis": "measured",
        "model_release_id": model_release_id,
        "quantization_profile_id": quantization_profile_id,
        "run_count": int(row["run_count"]),
        "p50_decode_tok_s": _optional_float(row.get("p50_decode_tok_s")),
        "p50_prefill_tok_s": _optional_float(row.get("p50_prefill_tok_s")),
    }


def _roofline_prior(
    session: DatabaseSession,
    model_release_id: str,
    quantization_profile_id: str | None,
    gpu_model_id: str | None,
    context_tokens: int | None,
) -> dict[str, Any] | None:
    """Kernel prediction when GPU/model/quant rows resolve; honest null else."""
    try:
        model_row = session.fetch_model_by_id(model_release_id)
        gpu_row = None
        if gpu_model_id:
            gpus = session.fetch_gpus_by_ids([gpu_model_id])
            gpu_row = gpus[0] if gpus else None
        if model_row is None or gpu_row is None:
            return None
        quant_row = (
            session.fetch_quantization_profile_by_id(quantization_profile_id)
            if quantization_profile_id
            else None
        )
        if quant_row is None:
            return None

        model = _build_model_arch(model_row)
        quant = _build_quant_profile(quant_row)
        hardware = GpuSpec(
            id=gpu_row["id"],
            vendor=gpu_row["vendor"],
            marketing_name=gpu_row["marketing_name"],
            vram_mib=int(gpu_row["vram_mib"]),
            memory_bandwidth_gib_s=float(gpu_row["memory_bandwidth_gib_s"]),
            fp16_tflops=float(gpu_row["fp16_tflops"]) if gpu_row.get("fp16_tflops") else 0.0,
            int8_tops=None,
            tdp_watt=int(gpu_row["tdp_watt"]),
        )
        scenario = BenchmarkScenario(
            prompt_tokens=context_tokens or DEFAULT_CONTEXT_TOKENS,
            generated_tokens=8,
            batch_size=1,
            context_tokens=context_tokens or DEFAULT_CONTEXT_TOKENS,
        )
        expected_decode = estimate_decode_tokens_per_second(hardware, model, quant, scenario)
        return {
            "basis": "formula",
            "gpu_model_id": gpu_row["id"],
            "quantization_profile_id": quant_row["id"],
            "context_tokens": scenario.context_tokens,
            "expected_decode_tok_s": round(float(expected_decode), 3),
            "plausible_range": [
                round(float(expected_decode) * 0.7, 3),
                round(float(expected_decode) * 1.3, 3),
            ],
        }
    except Exception:
        # A prior must never block claim creation; missing data stays null.
        return None


def _build_model_arch(row: dict[str, Any]) -> ModelArch:
    def opt_float(v):
        return float(v) if v is not None else None

    def opt_int(v):
        return int(v) if v is not None else None

    return ModelArch(
        id=row["id"],
        family=row["family"],
        release_name=row["release_name"],
        architecture=ModelArchitecture(row["architecture"]),
        parameter_count_billion=float(row["parameter_count_billion"]),
        active_parameter_count_billion=opt_float(row.get("active_parameter_count_billion")),
        num_layers=int(row["num_layers"]),
        hidden_size=int(row["hidden_size"]),
        num_attention_heads=int(row["num_attention_heads"]),
        num_kv_heads=int(row["num_kv_heads"]),
        head_dim=int(row["head_dim"]),
        expert_count=opt_int(row.get("expert_count")),
        experts_per_token=opt_int(row.get("experts_per_token")),
        max_context_tokens=int(row["max_context_tokens"]),
    )


def _build_quant_profile(row: dict[str, Any]) -> QuantProfile:
    return QuantProfile(
        id=row["id"],
        display_name=row["display_name"],
        weight_format=row["weight_format"],
        weight_bits=float(row["weight_bits"]),
        kv_cache_format=row["kv_cache_format"],
        kv_cache_bits=float(row["kv_cache_bits"]),
    )


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None
