"""Model-to-hardware matching query (plan flow 2).

Searches GPU x quantization x runtime x gpu_count candidates for the requested
model, keeps the feasible ones, and returns minimum, recommended and
cost-efficient configurations tagged by role.
"""

from __future__ import annotations

from typing import Any

from benchmark_scenario import BenchmarkScenario
from estimate_decode_throughput import estimate_decode_tokens_per_second
from estimate_prefill_throughput import estimate_prefill_tokens_per_second
from gpu_spec import GpuSpec
from model_arch import ModelArch, ModelArchitecture
from quant_profile import QuantProfile
from roofline_kernel import estimate_context_limit, estimate_vram_footprint

from src.dependencies.database_session_provider import DatabaseSession
from src.schemas.model_match_request import ModelMatchRequest

MAX_GPU_COUNT = 8
ETA_PACK = 1.05
GENERATED_TOKENS = 8


def query_model_configs(
    session: DatabaseSession, request: ModelMatchRequest
) -> dict[str, Any]:
    """Return tagged feasible configurations for the requested model."""
    model_row = session.fetch_model_by_id(request.model_release_id)
    if not model_row:
        return {"configs": []}
    candidates = _collect_candidates(session, model_row, request)
    if not candidates:
        return {"configs": []}
    minimum = min(candidates, key=lambda c: c["_total_vram_gib"])
    recommended = max(candidates, key=lambda c: c["expected_decode_tok_s"])
    cost_efficient = max(candidates, key=lambda c: c["expected_decode_tok_s"] / c["_total_vram_gib"])
    return {"configs": _tagged_configs([(minimum, "minimum"), (recommended, "recommended"), (cost_efficient, "cost_efficient")])}


def _collect_candidates(
    session: DatabaseSession, model_row: dict[str, Any], request: ModelMatchRequest
) -> list[dict[str, Any]]:
    candidates = []
    for gpu_row in session.fetch_all_gpus():
        for gpu_count in range(1, MAX_GPU_COUNT + 1):
            for quant_row in session.fetch_quantization_profiles():
                for runtime_row in session.fetch_inference_runtimes():
                    config = _evaluate_config(model_row, gpu_row, gpu_count, quant_row, runtime_row, request)
                    if config["feasible"]:
                        candidates.append(config)
    return candidates


def _tagged_configs(selections: list[tuple[dict[str, Any], str]]) -> list[dict[str, Any]]:
    chosen: dict[str, list[str]] = {}
    for config, role in selections:
        key = (config["gpu_model_id"], config["gpu_count"], config["quantization_profile_id"], config["runtime_id"])
        chosen.setdefault(key, []).append(role)
    configs = []
    for (gpu_model_id, gpu_count, quant_id, runtime_id), roles in chosen.items():
        source = next(
            c for c, _ in selections
            if (c["gpu_model_id"], c["gpu_count"], c["quantization_profile_id"], c["runtime_id"]) == (gpu_model_id, gpu_count, quant_id, runtime_id)
        )
        payload = {key: value for key, value in source.items() if not key.startswith("_")}
        payload["role"] = "+".join(roles)
        configs.append(payload)
    return configs


def _evaluate_config(
    model_row: dict[str, Any],
    gpu_row: dict[str, Any],
    gpu_count: int,
    quant_row: dict[str, Any],
    runtime_row: dict[str, Any],
    request: ModelMatchRequest,
) -> dict[str, Any]:
    capacity_mib = gpu_count * int(gpu_row["vram_mib"])
    hardware = _gpu_spec(gpu_row, gpu_count, capacity_mib)
    model = _build_model_arch(model_row)
    quant = _build_quant_profile(quant_row)
    estimates = _roofline_estimates(hardware, model, model_row, quant, quant_row, runtime_row, capacity_mib, request)
    return _config_payload(gpu_row, gpu_count, quant_row, runtime_row, capacity_mib, estimates)


def _roofline_estimates(
    hardware: GpuSpec,
    model: ModelArch,
    model_row: dict[str, Any],
    quant: QuantProfile,
    quant_row: dict[str, Any],
    runtime_row: dict[str, Any],
    capacity_mib: int,
    request: ModelMatchRequest,
) -> dict[str, Any]:
    footprint = estimate_vram_footprint(
        model=model,
        parameter_count=_parameter_count(model_row),
        num_layers=int(model_row["num_layers"]),
        num_kv_heads=int(model_row["num_kv_heads"]),
        head_dim=int(model_row["head_dim"]),
        weight_bits=float(quant_row["weight_bits"]),
        kv_cache_bytes_per_element=_kv_cache_bytes_per_element(quant_row),
        context_tokens=request.target_context_tokens,
        batch_size=request.batch_size,
        runtime=runtime_row["engine"],
        vram_capacity_mib=capacity_mib,
    )
    context = estimate_context_limit(
        model=model,
        parameter_count=_parameter_count(model_row),
        num_layers=int(model_row["num_layers"]),
        num_kv_heads=int(model_row["num_kv_heads"]),
        head_dim=int(model_row["head_dim"]),
        weight_bits=float(quant_row["weight_bits"]),
        eta_pack=ETA_PACK,
        kv_cache_bytes_per_element=_kv_cache_bytes_per_element(quant_row),
        target_context_tokens=request.target_context_tokens,
        batch_size=request.batch_size,
        runtime=runtime_row["engine"],
        vram_capacity_mib=capacity_mib,
    )
    scenario = BenchmarkScenario(
        prompt_tokens=request.target_context_tokens,
        generated_tokens=GENERATED_TOKENS,
        batch_size=request.batch_size,
        context_tokens=request.target_context_tokens,
    )
    decode = estimate_decode_tokens_per_second(hardware, model, quant, scenario)
    prefill = estimate_prefill_tokens_per_second(hardware, model, quant, scenario)
    return {
        "footprint": footprint,
        "context": context,
        "decode": decode,
        "prefill": prefill,
    }


def _config_payload(
    gpu_row: dict[str, Any],
    gpu_count: int,
    quant_row: dict[str, Any],
    runtime_row: dict[str, Any],
    capacity_mib: int,
    estimates: dict[str, Any],
) -> dict[str, Any]:
    footprint = estimates["footprint"]
    context = estimates["context"]
    return {
        "gpu_model_id": gpu_row["id"],
        "gpu_count": gpu_count,
        "quantization_profile_id": quant_row["id"],
        "runtime_id": runtime_row["id"],
        "feasible": bool(footprint.is_feasible and context.is_feasible),
        "expected_peak_vram_gib": footprint.peak_vram_gib,
        "expected_decode_tok_s": estimates["decode"],
        "expected_prefill_tok_s": estimates["prefill"],
        "max_context_tokens": context.max_context_tokens,
        "_total_vram_gib": capacity_mib / 1024.0,
    }


def _gpu_spec(row: dict[str, Any], gpu_count: int, capacity_mib: int) -> GpuSpec:
    flops = float(row["fp16_tflops"]) * gpu_count if row.get("fp16_tflops") else 0.0
    return GpuSpec(
        id=row["id"],
        vendor=row["vendor"],
        marketing_name=row["marketing_name"],
        vram_mib=capacity_mib,
        memory_bandwidth_gib_s=float(row["memory_bandwidth_gib_s"]) * gpu_count,
        fp16_tflops=flops,
        int8_tops=None,
        tdp_watt=int(row["tdp_watt"]),
    )


def _parameter_count(model_row: dict[str, Any]) -> float:
    return float(model_row["parameter_count_billion"]) * 1e9


def _kv_cache_bytes_per_element(quant_row: dict[str, Any]) -> float:
    return float(quant_row["kv_cache_bits"]) / 8.0


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _build_model_arch(row: dict[str, Any]) -> ModelArch:
    return ModelArch(
        id=row["id"],
        family=row["family"],
        release_name=row["release_name"],
        architecture=ModelArchitecture(row["architecture"]),
        parameter_count_billion=float(row["parameter_count_billion"]),
        active_parameter_count_billion=_optional_float(row["active_parameter_count_billion"]),
        num_layers=int(row["num_layers"]),
        hidden_size=int(row["hidden_size"]),
        num_attention_heads=int(row["num_attention_heads"]),
        num_kv_heads=int(row["num_kv_heads"]),
        head_dim=int(row["head_dim"]),
        expert_count=_optional_int(row["expert_count"]),
        experts_per_token=_optional_int(row["experts_per_token"]),
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
        group_size=_optional_int(row["group_size"]),
        calibration_set=row.get("calibration_set"),
        expected_quality_retention=_optional_float(row["expected_quality_retention"]),
    )
