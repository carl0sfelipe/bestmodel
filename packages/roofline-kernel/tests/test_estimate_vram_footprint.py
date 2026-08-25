from datetime import date

import pytest

from roofline_kernel.estimate_vram_footprint import estimate_vram_footprint
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


def test_case_a_dense_llama_cpp_single_rtx_3090():
    footprint = estimate_vram_footprint(
        model=_llama_3_8b(),
        parameter_count=8e9,
        num_layers=32,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.0,
        kv_cache_bytes_per_element=2,
        context_tokens=4096,
        batch_size=1,
        runtime="llama_cpp",
        vram_capacity_mib=24576,
    )
    assert footprint.peak_vram_gib == pytest.approx(5.73, rel=0.03)
    assert footprint.is_feasible is True


def test_case_b_32b_vllm_dual_rtx_4090():
    footprint = estimate_vram_footprint(
        model=_qwen_2_5_32b(),
        parameter_count=32.76e9,
        num_layers=64,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.08,
        kv_cache_bytes_per_element=2,
        context_tokens=8192,
        batch_size=1,
        runtime="vllm",
        vram_capacity_mib=49152,
    )
    assert footprint.peak_vram_gib == pytest.approx(23.56, rel=0.03)
    assert footprint.is_feasible is True


def test_case_c_same_32b_single_rtx_4090_infeasible():
    footprint = estimate_vram_footprint(
        model=_qwen_2_5_32b(),
        parameter_count=32.76e9,
        num_layers=64,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.08,
        kv_cache_bytes_per_element=2,
        context_tokens=8192,
        batch_size=1,
        runtime="vllm",
        vram_capacity_mib=24576,
    )
    assert footprint.is_feasible is False


def test_invalid_weight_bits_raises_with_offending_value():
    with pytest.raises(ValueError) as excinfo:
        estimate_vram_footprint(
            model=_llama_3_8b(),
            parameter_count=8e9,
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            weight_bits=0,
            kv_cache_bytes_per_element=2,
            context_tokens=4096,
            batch_size=1,
            runtime="llama_cpp",
            vram_capacity_mib=24576,
        )
    assert "0" in str(excinfo.value)


def test_invalid_vram_capacity_raises_with_offending_value():
    with pytest.raises(ValueError) as excinfo:
        estimate_vram_footprint(
            model=_llama_3_8b(),
            parameter_count=8e9,
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            weight_bits=4.5,
            kv_cache_bytes_per_element=2,
            context_tokens=4096,
            batch_size=1,
            runtime="llama_cpp",
            vram_capacity_mib=0,
        )
    assert "0" in str(excinfo.value)


def test_invalid_batch_size_raises_with_offending_value():
    with pytest.raises(ValueError) as excinfo:
        estimate_vram_footprint(
            model=_llama_3_8b(),
            parameter_count=8e9,
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            weight_bits=4.5,
            kv_cache_bytes_per_element=2,
            context_tokens=4096,
            batch_size=0,
            runtime="llama_cpp",
            vram_capacity_mib=24576,
        )
    assert "0" in str(excinfo.value)


def test_unknown_runtime_falls_back_to_default_base_overhead():
    footprint = estimate_vram_footprint(
        model=_llama_3_8b(),
        parameter_count=8e9,
        num_layers=32,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.0,
        kv_cache_bytes_per_element=2,
        context_tokens=4096,
        batch_size=1,
        runtime="sglang",
        vram_capacity_mib=24576,
    )
    expected_peak_gib = 5.73 + (1.5 - 0.8)
    assert footprint.peak_vram_gib == pytest.approx(expected_peak_gib, rel=0.01)


def test_moe_uses_active_parameter_count_billion():
    model = ModelArch(
        id="deepseek-moe",
        family="deepseek",
        release_name="DeepSeek-MoE",
        architecture=ModelArchitecture.moe,
        parameter_count_billion=15.0,
        active_parameter_count_billion=3.0,
        num_layers=32,
        hidden_size=2048,
        num_attention_heads=16,
        num_kv_heads=8,
        head_dim=128,
        expert_count=128,
        experts_per_token=2,
        max_context_tokens=32768,
    )
    footprint = estimate_vram_footprint(
        model=model,
        parameter_count=15e9,
        num_layers=32,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.05,
        kv_cache_bytes_per_element=2,
        context_tokens=4096,
        batch_size=1,
        runtime="vllm",
        vram_capacity_mib=24576,
    )
    assert footprint.weight_bytes == pytest.approx(3e9 * 4.5 / 8 * 1.05)


def test_moe_falls_back_to_shared_plus_active_experts():
    model = ModelArch(
        id="deepseek-moe",
        family="deepseek",
        release_name="DeepSeek-MoE",
        architecture=ModelArchitecture.moe,
        parameter_count_billion=15.0,
        active_parameter_count_billion=None,
        num_layers=32,
        hidden_size=2048,
        num_attention_heads=16,
        num_kv_heads=8,
        head_dim=128,
        expert_count=128,
        experts_per_token=2,
        max_context_tokens=32768,
    )
    footprint = estimate_vram_footprint(
        model=model,
        parameter_count=15e9,
        num_layers=32,
        num_kv_heads=8,
        head_dim=128,
        weight_bits=4.5,
        eta_pack=1.05,
        kv_cache_bytes_per_element=2,
        context_tokens=4096,
        batch_size=1,
        runtime="vllm",
        vram_capacity_mib=24576,
        parameter_count_per_expert=0.1e9,
    )
    active_parameters = (15e9 - 0.1e9 * 128) + 0.1e9 * 2
    assert footprint.weight_bytes == pytest.approx(active_parameters * 4.5 / 8 * 1.05)
