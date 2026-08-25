"""Unit tests for prefill throughput and TTFT prediction (S05).

Expected values are hand-computed from the documented roofline formulas
(design doc 11.4 / 11.6) using literal utilization constants, so this file
independently guards against accidental changes to the model.
"""

import pytest

from benchmark_scenario import BenchmarkScenario
from model_arch import ModelArch, ModelArchitecture
from quant_profile import KvCacheFormat, QuantFormat, QuantProfile
from estimate_prefill_throughput import (
    O_LATENCY_SECONDS,
    U_COMPUTE,
    derive_effective_flops,
    derive_prefill_flops_per_token,
    estimate_prefill_tokens_per_second,
    estimate_ttft,
)
from hardware_fixtures import A100_80GB, H100_80GB, RTX_4090


def _dense_model(parameter_count_billion: float = 13.0) -> ModelArch:
    return ModelArch(
        id="llama-13b",
        family="llama",
        release_name="Llama-13B",
        architecture=ModelArchitecture.dense,
        parameter_count_billion=parameter_count_billion,
        active_parameter_count_billion=None,
        num_layers=40,
        hidden_size=5120,
        num_attention_heads=40,
        num_kv_heads=8,
        head_dim=128,
        max_context_tokens=32768,
    )


def _fp16_quant() -> QuantProfile:
    return QuantProfile(
        id="fp16",
        display_name="FP16",
        weight_format=QuantFormat.fp16,
        weight_bits=16.0,
        kv_cache_format=KvCacheFormat.fp16,
        kv_cache_bits=16.0,
    )


def _scenario(prompt_tokens: int = 2048) -> BenchmarkScenario:
    return BenchmarkScenario(
        prompt_tokens=prompt_tokens,
        generated_tokens=64,
        batch_size=1,
        context_tokens=8192,
    )


def _hand_prefill(hardware, model: ModelArch, prompt_tokens: int) -> float:
    active_params = model.parameter_count_billion * 1e9
    f_attention = (
        2.0
        * model.num_layers
        * model.num_attention_heads
        * prompt_tokens
        * prompt_tokens
        * model.head_dim
    )
    f_prefill = 2.0 * active_params * prompt_tokens + f_attention
    f_token = f_prefill / prompt_tokens
    c_eff = hardware.fp16_tflops * 1e12 * U_COMPUTE
    return c_eff / f_token


def test_fixtures_carry_known_nominal_compute():
    assert A100_80GB.fp16_tflops == pytest.approx(312.0)
    assert H100_80GB.fp16_tflops == pytest.approx(989.0)
    assert RTX_4090.fp16_tflops == pytest.approx(165.0)


def test_effective_flops_matches_hand_computed():
    quant = _fp16_quant()
    scenario = _scenario()
    expected = A100_80GB.fp16_tflops * 1e12 * 0.7
    actual = derive_effective_flops(A100_80GB, quant, scenario)
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize(
    "hardware",
    [A100_80GB, H100_80GB, RTX_4090],
)
def test_prefill_matches_hand_computed(hardware):
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(prompt_tokens=2048)

    expected = _hand_prefill(hardware, model, prompt_tokens=2048)
    actual = estimate_prefill_tokens_per_second(
        hardware, model, quant, scenario
    )
    assert actual == pytest.approx(expected, rel=0.10)


def test_flops_per_token_matches_hand_computed():
    model = _dense_model()
    prompt_tokens = 2048
    expected = (
        2.0 * 13.0e9 * prompt_tokens
        + 2.0 * 40 * 40 * prompt_tokens * prompt_tokens * 128
    ) / prompt_tokens
    actual = derive_prefill_flops_per_token(model, _scenario(prompt_tokens))
    assert actual == pytest.approx(expected)


def test_prefill_plausible_range_on_a100():
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(prompt_tokens=2048)
    tok_s = estimate_prefill_tokens_per_second(A100_80GB, model, quant, scenario)
    assert 4000.0 <= tok_s <= 16000.0


def test_ttft_matches_hand_computed():
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(prompt_tokens=2048)
    expected = 2048.0 / _hand_prefill(A100_80GB, model, 2048) + O_LATENCY_SECONDS
    actual = estimate_ttft(A100_80GB, model, quant, scenario)
    assert actual == pytest.approx(expected, rel=0.10)


def test_larger_prompt_increases_ttft():
    model = _dense_model()
    quant = _fp16_quant()
    short = estimate_ttft(
        A100_80GB, model, quant, _scenario(prompt_tokens=512)
    )
    long = estimate_ttft(
        A100_80GB, model, quant, _scenario(prompt_tokens=4096)
    )
    assert long > short


def test_rejects_non_positive_flops_per_token():
    model = _dense_model(parameter_count_billion=-2.0)
    quant = _fp16_quant()
    scenario = _scenario(prompt_tokens=64)
    with pytest.raises(
        ValueError, match=r"flops_per_prompt_token=-.*, expected > 0 FLOPs"
    ):
        estimate_prefill_tokens_per_second(A100_80GB, model, quant, scenario)


def test_rejects_empty_prompt():
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(prompt_tokens=0)
    with pytest.raises(
        ValueError, match=r"flops_per_prompt_token=0\.0, expected > 0 FLOPs"
    ):
        estimate_ttft(A100_80GB, model, quant, scenario)
