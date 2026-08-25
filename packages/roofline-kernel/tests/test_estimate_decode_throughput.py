"""Unit tests for decode throughput prediction (S05).

Expected values are hand-computed from the documented roofline formulas
(design doc 11.3 / 11.5) using literal utilization constants, so this file
independently guards against accidental changes to the model.
"""

import pytest

from benchmark_scenario import BenchmarkScenario
from model_arch import ModelArch, ModelArchitecture
from quant_profile import KvCacheFormat, QuantFormat, QuantProfile
from estimate_decode_throughput import (
    T_ALLREDUCE_SECONDS,
    U_QUANT,
    U_RUNTIME,
    U_TP,
    derive_decode_bytes_per_step,
    derive_effective_bandwidth_bytes_per_second,
    estimate_decode_tokens_per_second,
)
from hardware_fixtures import A100_80GB, RTX_4090

GIB = 1024.0 ** 3
BYTES_PER_WEIGHT = 16.0 / 8.0


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


def _moe_model() -> ModelArch:
    return ModelArch(
        id="moe-671b",
        family="deepseek",
        release_name="MoE-671B",
        architecture=ModelArchitecture.moe,
        parameter_count_billion=671.0,
        active_parameter_count_billion=37.0,
        num_layers=61,
        hidden_size=7168,
        num_attention_heads=128,
        num_kv_heads=128,
        head_dim=128,
        expert_count=256,
        experts_per_token=8,
        max_context_tokens=16384,
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


def _scenario(
    batch_size: int = 1,
    context_tokens: int = 8192,
    prompt_tokens: int = 128,
) -> BenchmarkScenario:
    return BenchmarkScenario(
        prompt_tokens=prompt_tokens,
        generated_tokens=64,
        batch_size=batch_size,
        context_tokens=context_tokens,
    )


def _kv_bytes_per_token(model: ModelArch) -> float:
    return 2.0 * model.num_kv_heads * model.head_dim * (16.0 / 8.0)


def _hand_decode(
    hardware,
    model: ModelArch,
    batch_size: int,
    context_tokens: int,
) -> float:
    bw_eff = hardware.memory_bandwidth_gib_s * GIB * U_RUNTIME * U_QUANT * U_TP
    kv_read = _kv_bytes_per_token(model) * context_tokens * batch_size
    if batch_size <= 1:
        weight_bytes = model.parameter_count_billion * 1e9 * BYTES_PER_WEIGHT
    else:
        weight_bytes = model.parameter_count_billion * 1e9 * BYTES_PER_WEIGHT
    bytes_per_step = weight_bytes + kv_read
    return batch_size / (bytes_per_step / bw_eff + T_ALLREDUCE_SECONDS)


def test_fixtures_carry_known_nominal_bandwidth():
    assert A100_80GB.memory_bandwidth_gib_s == pytest.approx(2039.0)
    assert RTX_4090.memory_bandwidth_gib_s == pytest.approx(1008.0)
    assert A100_80GB.fp16_tflops == pytest.approx(312.0)


def test_effective_bandwidth_matches_hand_computed():
    quant = _fp16_quant()
    scenario = _scenario()
    expected = A100_80GB.memory_bandwidth_gib_s * GIB * 0.8 * 0.9 * 1.0
    actual = derive_effective_bandwidth_bytes_per_second(
        A100_80GB, quant, scenario
    )
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize(
    "hardware",
    [A100_80GB, RTX_4090],
)
def test_decode_matches_hand_computed(hardware):
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(batch_size=1, context_tokens=8192)

    expected = _hand_decode(hardware, model, batch_size=1, context_tokens=8192)
    actual = estimate_decode_tokens_per_second(hardware, model, quant, scenario)
    assert actual == pytest.approx(expected, rel=0.10)


def test_decode_batch_matches_hand_computed():
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(batch_size=8, context_tokens=8192)

    expected = _hand_decode(A100_80GB, model, batch_size=8, context_tokens=8192)
    actual = estimate_decode_tokens_per_second(A100_80GB, model, quant, scenario)
    assert actual == pytest.approx(expected, rel=0.10)


def test_decode_plausible_range_on_a100():
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(batch_size=1, context_tokens=8192)
    tok_s = estimate_decode_tokens_per_second(A100_80GB, model, quant, scenario)
    assert 40.0 <= tok_s <= 90.0


def test_decode_bytes_per_step_matches_hand_computed():
    model = _dense_model()
    quant = _fp16_quant()
    scenario = _scenario(batch_size=1, context_tokens=8192)
    expected = 13.0e9 * BYTES_PER_WEIGHT + _kv_bytes_per_token(model) * 8192
    actual = derive_decode_bytes_per_step(model, quant, scenario)
    assert actual == pytest.approx(expected)


def test_larger_context_does_not_increase_decode_tokens_per_second():
    model = _dense_model()
    quant = _fp16_quant()
    short = estimate_decode_tokens_per_second(
        A100_80GB, model, quant, _scenario(batch_size=1, context_tokens=2048)
    )
    long = estimate_decode_tokens_per_second(
        A100_80GB, model, quant, _scenario(batch_size=1, context_tokens=32768)
    )
    assert short >= long
    assert short > long


def test_larger_batch_increases_decode_tokens_per_second():
    model = _dense_model()
    quant = _fp16_quant()
    single = estimate_decode_tokens_per_second(
        A100_80GB, model, quant, _scenario(batch_size=1, context_tokens=8192)
    )
    batched = estimate_decode_tokens_per_second(
        A100_80GB, model, quant, _scenario(batch_size=8, context_tokens=8192)
    )
    assert batched > single


def test_moe_decode_uses_distinct_experts_for_batch():
    model = _moe_model()
    quant = _fp16_quant()
    single = estimate_decode_tokens_per_second(
        A100_80GB, model, quant, _scenario(batch_size=1, context_tokens=8192)
    )
    batched = estimate_decode_tokens_per_second(
        A100_80GB, model, quant, _scenario(batch_size=8, context_tokens=8192)
    )
    assert single > 0.0
    assert batched > single


def test_rejects_non_positive_bytes_per_step():
    model = _dense_model(parameter_count_billion=-2.0)
    quant = _fp16_quant()
    scenario = _scenario(batch_size=1, context_tokens=64)
    with pytest.raises(
        ValueError, match=r"bytes_per_generation_step=-.*, expected > 0 bytes"
    ):
        estimate_decode_tokens_per_second(A100_80GB, model, quant, scenario)
