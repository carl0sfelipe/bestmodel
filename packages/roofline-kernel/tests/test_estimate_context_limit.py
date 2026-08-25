from datetime import date

import pytest

from roofline_kernel.estimate_context_limit import (
    estimate_context_limit,
    estimate_max_context_tokens,
)
from model_arch import ModelArch, ModelArchitecture


def _llama_3_8b() -> ModelArch:
    return ModelArch(
        id="llama-3-8b",
        family="llama",
        release_name="Llama-3-8B",
        architecture=ModelArchitecture.dense,
        parameter_count_billion=8.0,
        num_layers=32,
        hidden_size=4096,
        num_attention_heads=32,
        num_kv_heads=8,
        head_dim=128,
        max_context_tokens=8192,
        released_at=date(2024, 4, 18),
    )


def _qwen_2_5_32b() -> ModelArch:
    return ModelArch(
        id="qwen-2.5-32b",
        family="qwen",
        release_name="Qwen-2.5-32B",
        architecture=ModelArchitecture.dense,
        parameter_count_billion=32.76,
        num_layers=64,
        hidden_size=5120,
        num_attention_heads=40,
        num_kv_heads=8,
        head_dim=128,
        max_context_tokens=131072,
    )


def test_case_a_max_context_capped_by_model_limit():
    estimate = estimate_context_limit(
        model=_llama_3_8b(),
        parameter_count=8e9,
        num_layers=32,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.0,
        kv_cache_bytes_per_element=2,
        target_context_tokens=4096,
        batch_size=1,
        runtime="llama_cpp",
        vram_capacity_mib=24576,
    )
    assert estimate.max_context_tokens == 8192
    assert estimate.is_feasible is True
    assert estimate.suggestions == ()


def test_case_b_32b_vllm_dual_rtx_4090_feasible():
    estimate = estimate_context_limit(
        model=_qwen_2_5_32b(),
        parameter_count=32.76e9,
        num_layers=64,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.08,
        kv_cache_bytes_per_element=2,
        target_context_tokens=8192,
        batch_size=1,
        runtime="vllm",
        vram_capacity_mib=49152,
    )
    assert estimate.max_context_tokens == pytest.approx(98468, rel=0.03)
    assert estimate.max_context_tokens >= 32000
    assert estimate.is_feasible is True


def test_case_c_single_rtx_4090_infeasible_with_suggestions():
    estimate = estimate_context_limit(
        model=_qwen_2_5_32b(),
        parameter_count=32.76e9,
        num_layers=64,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.08,
        kv_cache_bytes_per_element=2,
        target_context_tokens=8192,
        batch_size=1,
        runtime="vllm",
        vram_capacity_mib=24576,
    )
    assert estimate.max_context_tokens == 5072
    assert estimate.max_context_tokens < 8192
    assert estimate.is_feasible is False
    assert len(estimate.suggestions) >= 2
    assert str(estimate.max_context_tokens) in estimate.suggestions[0]
    assert "KV" in estimate.suggestions[1]


def test_invalid_batch_size_raises_with_offending_value():
    with pytest.raises(ValueError) as excinfo:
        estimate_context_limit(
            model=_llama_3_8b(),
            parameter_count=8e9,
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            weight_bits=4.5,
            eta_pack=1.0,
            kv_cache_bytes_per_element=2,
            target_context_tokens=4096,
            batch_size=0,
            runtime="llama_cpp",
            vram_capacity_mib=24576,
        )
    assert "0" in str(excinfo.value)


def test_invalid_vram_capacity_raises_with_offending_value():
    with pytest.raises(ValueError) as excinfo:
        estimate_context_limit(
            model=_llama_3_8b(),
            parameter_count=8e9,
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            weight_bits=4.5,
            eta_pack=1.0,
            kv_cache_bytes_per_element=2,
            target_context_tokens=4096,
            batch_size=1,
            runtime="llama_cpp",
            vram_capacity_mib=0,
        )
    assert "0" in str(excinfo.value)


def test_max_context_tokens_respects_cap():
    max_tokens = estimate_max_context_tokens(
        vram_capacity_mib=24576,
        weight_bytes=4.5e9,
        runtime_overhead_bytes=0.8 * 2**30,
        kv_bytes_per_token=131072,
        batch_size=1,
        model_max_context_tokens=2048,
    )
    assert max_tokens == 2048


def test_max_context_tokens_negative_available_clamps_to_zero():
    max_tokens = estimate_max_context_tokens(
        vram_capacity_mib=24576,
        weight_bytes=40e9,
        runtime_overhead_bytes=0.8 * 2**30,
        kv_bytes_per_token=131072,
        batch_size=1,
        model_max_context_tokens=131072,
    )
    assert max_tokens == 0
