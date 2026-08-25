"""Roofline prefill throughput and TTFT prediction.

Implements the prefill roofline model from the design doc (section 11.4) and the
pseudocode contract from section 11.6: estimate prefill tokens/second and
time-to-first-token for a hardware/model/quantization/scenario combination.

Prefill is compute-bound:

    F_prefill = 2 * P_active * S + F_attention
    F_attention = 2 * L * H * S^2 * d_h
    F_token = F_prefill / S
    C_eff = C_nominal * U_compute
    prefill = C_eff / F_token
    TTFT = S_prompt / prefill + O_latency

All numbers are deterministic; no randomness is used.
"""

from benchmark_scenario import BenchmarkScenario
from gpu_spec import GpuSpec
from model_arch import ModelArch
from quant_profile import QuantProfile

U_COMPUTE = 0.7
"""Fraction of nominal fp16 FLOPs actually achieved during prefill after
kernel inefficiency, memory stalls and non-compute overhead are accounted for."""

O_LATENCY_SECONDS = 0.1
"""Fixed scheduling/model-load overhead (seconds) added to the pure compute time
when estimating time-to-first-token."""


def derive_effective_flops(
    hardware: GpuSpec,
    quant: QuantProfile,
    scenario: BenchmarkScenario,
) -> float:
    """Return effective compute throughput in FLOPs/second.

    ``C_eff = C_nominal * U_compute`` where ``C_nominal`` comes from the
    hardware's nominal fp16 TFLOPs. ``quant`` and ``scenario`` are accepted for
    API symmetry with the pseudocode contract; prefill compute is modeled as
    independent of quantization.
    """
    nominal_flops = hardware.fp16_tflops * 1e12
    return nominal_flops * U_COMPUTE


def derive_prefill_flops_per_token(
    model: ModelArch,
    scenario: BenchmarkScenario,
) -> float:
    """FLOPs per processed prompt token for a full prefill pass.

    ``F_token = (2 * P_active * S + 2 * L * H * S^2 * d_h) / S``. When the
    scenario has an empty prompt the value is defined as 0 so the caller's
    ``> 0`` guard raises a ``ValueError``.
    """
    s = scenario.prompt_tokens
    active_params = (
        model.active_parameter_count_billion
        if model.active_parameter_count_billion is not None
        else model.parameter_count_billion
    ) * 1e9
    if s <= 0:
        return 0.0
    f_attention = (
        2.0
        * model.num_layers
        * model.num_attention_heads
        * s
        * s
        * model.head_dim
    )
    f_prefill = 2.0 * active_params * s + f_attention
    return f_prefill / s


def estimate_prefill_tokens_per_second(
    hardware: GpuSpec,
    model: ModelArch,
    quant: QuantProfile,
    scenario: BenchmarkScenario,
) -> float:
    """Estimate prefill throughput in processed tokens/second.

    ``prefill = C_eff / F_token``. Raises ``ValueError`` when a prompt token
    costs no (or negative) FLOPs.
    """
    effective_flops = derive_effective_flops(hardware, quant, scenario)
    flops_per_prompt_token = derive_prefill_flops_per_token(model, scenario)
    if flops_per_prompt_token <= 0:
        raise ValueError(
            f"flops_per_prompt_token={flops_per_prompt_token}, "
            "expected > 0 FLOPs"
        )
    return effective_flops / flops_per_prompt_token


def estimate_ttft(
    hardware: GpuSpec,
    model: ModelArch,
    quant: QuantProfile,
    scenario: BenchmarkScenario,
) -> float:
    """Estimate time-to-first-token in seconds.

    ``TTFT = S_prompt / prefill + O_latency``. An empty prompt raises
    ``ValueError`` through ``estimate_prefill_tokens_per_second``.
    """
    prefill_tokens_per_second = estimate_prefill_tokens_per_second(
        hardware, model, quant, scenario
    )
    return scenario.prompt_tokens / prefill_tokens_per_second + O_LATENCY_SECONDS
