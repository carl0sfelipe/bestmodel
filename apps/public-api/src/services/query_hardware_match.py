"""Hardware-to-models matching query (plan section 9.4).

Builds model x quantization x runtime candidates for the requested GPU set and
model family, evaluates each candidate with the roofline kernel, and returns
matches carrying feasibility and expected performance metrics.
"""

from __future__ import annotations

from typing import Any

from benchmark_scenario import BenchmarkScenario
from estimate_decode_throughput import estimate_decode_tokens_per_second
from estimate_prefill_throughput import estimate_prefill_tokens_per_second, estimate_ttft
from gpu_spec import GpuSpec
from model_arch import ModelArch, ModelArchitecture
from quant_profile import QuantProfile
from roofline_kernel import estimate_context_limit, estimate_vram_footprint

from src.dependencies.database_session_provider import DatabaseSession
from src.schemas.hardware_match_request import HardwareMatchRequest

BATCH_SIZE = 1
TTFT_PROMPT_TOKENS = 8192
ETA_PACK = 1.05
DEFAULT_QUALITY_RETENTION = 1.0
TRUST_SCORE_PLACEHOLDER = 0.5
MAX_MATCHES = 100


def query_hardware_matches(
    session: DatabaseSession, request: HardwareMatchRequest
) -> dict[str, Any]:
    """Return matches for the requested hardware and model family."""
    gpus = session.fetch_gpus_by_ids(request.gpu_model_ids)
    if not gpus:
        return {"matches": []}
    capacity_mib = _total_vram_capacity_mib(gpus, request.gpu_count)
    hardware = _combined_gpu_spec(gpus, request.gpu_count, capacity_mib)
    matches = []
    for model_row in session.fetch_models_by_family(request.target_model_family):
        for quant_row in session.fetch_quantization_profiles():
            for runtime_row in session.fetch_inference_runtimes():
                match = _evaluate_match(hardware, model_row, quant_row, runtime_row, capacity_mib, request)
                matches.append(match)
    matches.sort(key=lambda match: _sort_key(match, request.priority))
    return {"matches": matches[:MAX_MATCHES]}


def _sort_key(match: dict[str, Any], priority: str) -> tuple[Any, ...]:
    if priority == "latency":
        return (not match["feasible"], match["expected_ttft_ms_8k_prompt"])
    return (not match["feasible"], -match["expected_decode_tok_s"])


def _total_vram_capacity_mib(gpus: list[dict[str, Any]], gpu_count: int) -> int:
    return gpu_count * sum(int(row["vram_mib"]) for row in gpus)


def _combined_gpu_spec(
    gpus: list[dict[str, Any]], gpu_count: int, capacity_mib: int
) -> GpuSpec:
    first = gpus[0]
    bandwidth = gpu_count * sum(float(row["memory_bandwidth_gib_s"]) for row in gpus)
    flops = gpu_count * sum(float(row["fp16_tflops"]) for row in gpus if row.get("fp16_tflops"))
    return GpuSpec(
        id=first["id"],
        vendor=first["vendor"],
        marketing_name=first["marketing_name"],
        vram_mib=capacity_mib,
        memory_bandwidth_gib_s=bandwidth,
        fp16_tflops=flops,
        int8_tops=None,
        tdp_watt=int(first["tdp_watt"]),
    )


def _evaluate_match(
    hardware: GpuSpec,
    model_row: dict[str, Any],
    quant_row: dict[str, Any],
    runtime_row: dict[str, Any],
    capacity_mib: int,
    request: HardwareMatchRequest,
) -> dict[str, Any]:
    model = _build_model_arch(model_row)
    quant = _build_quant_profile(quant_row)
    estimates = _roofline_estimates(hardware, model, model_row, quant, quant_row, runtime_row, capacity_mib, request)
    return _match_payload(model_row, quant_row, runtime_row, estimates)


def _roofline_estimates(
    hardware: GpuSpec,
    model: ModelArch,
    model_row: dict[str, Any],
    quant: QuantProfile,
    quant_row: dict[str, Any],
    runtime_row: dict[str, Any],
    capacity_mib: int,
    request: HardwareMatchRequest,
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
        batch_size=BATCH_SIZE,
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
        batch_size=BATCH_SIZE,
        runtime=runtime_row["engine"],
        vram_capacity_mib=capacity_mib,
    )
    scenario = _scenario(request.target_context_tokens, BATCH_SIZE)
    decode = estimate_decode_tokens_per_second(hardware, model, quant, scenario)
    prefill = estimate_prefill_tokens_per_second(hardware, model, quant, scenario)
    ttft_scenario = _scenario(request.target_context_tokens, BATCH_SIZE, TTFT_PROMPT_TOKENS)
    ttft_ms = estimate_ttft(hardware, model, quant, ttft_scenario) * 1000.0
    return {
        "footprint": footprint,
        "context": context,
        "decode": decode,
        "prefill": prefill,
        "ttft_ms": ttft_ms,
    }


def _match_payload(
    model_row: dict[str, Any],
    quant_row: dict[str, Any],
    runtime_row: dict[str, Any],
    estimates: dict[str, Any],
) -> dict[str, Any]:
    footprint = estimates["footprint"]
    context = estimates["context"]
    return {
        "model_release_id": model_row["id"],
        "quantization_profile_id": quant_row["id"],
        "runtime_id": runtime_row["id"],
        "feasible": bool(footprint.is_feasible and context.is_feasible),
        "expected_decode_tok_s": estimates["decode"],
        "expected_prefill_tok_s": estimates["prefill"],
        "expected_ttft_ms_8k_prompt": estimates["ttft_ms"],
        "expected_peak_vram_gib": footprint.peak_vram_gib,
        "max_context_tokens": context.max_context_tokens,
        "quality_retention_estimate": _quality_retention(quant_row),
        "trust_score": TRUST_SCORE_PLACEHOLDER,
    }


def _scenario(context_tokens: int, batch_size: int, prompt_tokens: int | None = None) -> BenchmarkScenario:
    return BenchmarkScenario(
        prompt_tokens=prompt_tokens if prompt_tokens is not None else context_tokens,
        generated_tokens=8,
        batch_size=batch_size,
        context_tokens=context_tokens,
    )


def _parameter_count(model_row: dict[str, Any]) -> float:
    return float(model_row["parameter_count_billion"]) * 1e9


def _kv_cache_bytes_per_element(quant_row: dict[str, Any]) -> float:
    return float(quant_row["kv_cache_bits"]) / 8.0


def _quality_retention(quant_row: dict[str, Any]) -> float:
    value = quant_row.get("expected_quality_retention")
    return float(value) if value is not None else DEFAULT_QUALITY_RETENTION


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
