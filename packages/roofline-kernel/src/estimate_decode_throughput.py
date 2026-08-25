"""Roofline decode throughput prediction.

Implements the decode roofline model from the design doc (section 11.3) and the
pseudocode contract from section 11.5: estimate how many generated tokens per
second a hardware/model/quantization/scenario combination can sustain for
autoregressive (single-batch or batched) decoding.

Decode is memory-bandwidth-bound:

    BW_eff  = BW_nominal * U_runtime * U_quant * U_tp
    D_bytes = W_step + KV_read
    T_step  = D_bytes / BW_eff + T_allreduce
    decode  = batch_size / T_step

All numbers are deterministic; no randomness is used.
"""

from benchmark_scenario import BenchmarkScenario
from gpu_spec import GpuSpec
from model_arch import ModelArch, ModelArchitecture
from quant_profile import QuantProfile

# Utilization coefficients. Values are deterministic engineering defaults; they
# are intentionally kept as module-level named constants so callers and tests
# can refer to them without duplicating magic numbers.
U_RUNTIME = 0.8
"""Fraction of nominal bandwidth actually achieved by a real runtime
(vLLM/llama.cpp/TGI) after scheduling, launch and memory-system overheads."""

U_QUANT = 0.9
"""Read efficiency factor for quantized weights: accounts for the extra
dequantization work and non-contiguous memory reads that quantized formats
(KV cache and group-quantized weights) introduce versus raw fp16."""

U_TP = 1.0
"""Post-tensor-parallel efficiency. For a single GPU there is no all-reduce
communication penalty, so this is 1.0."""

T_ALLREDUCE_SECONDS = 0.0
"""Per-step all-reduce communication latency in seconds. Zero for a single GPU;
a multi-GPU deployment would add its (deterministic) communication overhead."""

_GIB = 1024.0 ** 3
"""Bytes in a GiB, used to convert the hardware bandwidth from GiB/s to B/s."""


def derive_effective_bandwidth_bytes_per_second(
    hardware: GpuSpec,
    quant: QuantProfile,
    scenario: BenchmarkScenario,
) -> float:
    """Return the effective memory bandwidth in bytes/second.

    BW_eff = BW_nominal * U_runtime * U_quant * U_tp.
    ``scenario`` is accepted for API symmetry with the pseudocode contract; the
    effective bandwidth for a single-GPU run does not depend on it.
    """
    nominal_bytes_per_second = hardware.memory_bandwidth_gib_s * _GIB
    return nominal_bytes_per_second * U_RUNTIME * U_QUANT * U_TP


def _bytes_per_weight(quant: QuantProfile) -> float:
    """Number of bytes occupied by a single quantized weight."""
    return quant.weight_bits / 8.0


def _kv_bytes_per_token(model: ModelArch, quant: QuantProfile) -> float:
    """Number of bytes read per KV-cache token: K and V each hold
    ``num_kv_heads * head_dim`` values."""
    values_per_kv = model.num_kv_heads * model.head_dim
    return 2.0 * values_per_kv * (quant.kv_cache_bits / 8.0)


def _active_parameter_count_billion(model: ModelArch) -> float:
    """Parameter count active per token (total for dense models)."""
    if model.active_parameter_count_billion is not None:
        return model.active_parameter_count_billion
    return model.parameter_count_billion


def _shared_and_expert_params_billion(
    model: ModelArch,
) -> tuple[float, float]:
    """Split an MoE model's parameters into shared (non-expert) and the size of
    one single expert.

    Uses ``parameter_count_billion = shared + expert_count * expert_size`` and
    ``active = shared + experts_per_token * expert_size`` to recover both
    unknowns deterministically.
    """
    total = model.parameter_count_billion
    active = _active_parameter_count_billion(model)
    expert_count = model.expert_count
    experts_per_token = model.experts_per_token
    if (
        expert_count is None
        or experts_per_token is None
        or expert_count <= 0
        or experts_per_token >= expert_count
    ):
        # Degenerate/expert-saturated MoE: treat everything as experts.
        return 0.0, total / max(expert_count or 1, 1)
    ratio = experts_per_token / expert_count
    shared = (active - ratio * total) / (1.0 - ratio)
    shared = max(shared, 0.0)
    expert_size = max(total - shared, 0.0) / expert_count
    return shared, expert_size


def _decode_weight_bytes_per_step(
    model: ModelArch,
    quant: QuantProfile,
    batch_size: int,
) -> float:
    """Weight bytes read during one decode step.

    Single-batch (B=1) loads only the active weights for the one token. For a
    batch, weights are amortized: dense models read the whole weight set once
    (``W_shared``), MoE models read the shared layers plus the distinct union of
    experts routed by the batch (``W_experts_distinct``).
    """
    bytes_per_weight = _bytes_per_weight(quant)
    if batch_size <= 1:
        return _active_parameter_count_billion(model) * 1e9 * bytes_per_weight
    if model.architecture == ModelArchitecture.moe and model.expert_count:
        shared, expert_size = _shared_and_expert_params_billion(model)
        distinct_experts = min(model.expert_count, model.experts_per_token * batch_size)
        shared_bytes = shared * 1e9 * bytes_per_weight
        experts_bytes = distinct_experts * expert_size * 1e9 * bytes_per_weight
        return shared_bytes + experts_bytes
    # Dense / multimodal: all weights are shared across the batch.
    return model.parameter_count_billion * 1e9 * bytes_per_weight


def derive_decode_bytes_per_step(
    model: ModelArch,
    quant: QuantProfile,
    scenario: BenchmarkScenario,
) -> float:
    """Total bytes read per decode step: weights plus KV cache.

    Single-batch: ``W_bytes_active + K_token * S``.
    Multi-batch:  ``W_shared + W_experts_distinct + K_token * S * B``.
    """
    weight_bytes = _decode_weight_bytes_per_step(
        model, quant, scenario.batch_size
    )
    kv_read_bytes = (
        _kv_bytes_per_token(model, quant)
        * scenario.context_tokens
        * scenario.batch_size
    )
    return weight_bytes + kv_read_bytes


def estimate_decode_tokens_per_second(
    hardware: GpuSpec,
    model: ModelArch,
    quant: QuantProfile,
    scenario: BenchmarkScenario,
) -> float:
    """Estimate sustained decode throughput in generated tokens/second.

    ``decode = batch_size / (D_bytes / BW_eff + T_allreduce)``. Raises
    ``ValueError`` when a single generation step reads no (or negative) bytes.
    """
    effective_bandwidth_bytes = derive_effective_bandwidth_bytes_per_second(
        hardware, quant, scenario
    )
    bytes_per_generation_step = derive_decode_bytes_per_step(model, quant, scenario)
    if bytes_per_generation_step <= 0:
        raise ValueError(
            f"bytes_per_generation_step={bytes_per_generation_step}, "
            "expected > 0 bytes"
        )
    step_seconds = (
        bytes_per_generation_step / effective_bandwidth_bytes + T_ALLREDUCE_SECONDS
    )
    return scenario.batch_size / step_seconds
