from benchmark_metrics import MetricKind
from benchmark_report import ArtifactKind, HardwareClass, RuntimeEngine
from model_arch import ModelArchitecture
from quant_profile import KvCacheFormat, QuantFormat


def _values(enum_cls):
    return [member.value for member in enum_cls]


def test_model_architecture_values():
    assert _values(ModelArchitecture) == ["dense", "moe", "multimodal"]


def test_quant_format_values():
    assert _values(QuantFormat) == [
        "fp16",
        "bf16",
        "fp8",
        "int8",
        "int4",
        "awq",
        "gptq",
        "exl2",
        "gguf_q2",
        "gguf_q3",
        "gguf_q4",
        "gguf_q5",
        "gguf_q6",
        "gguf_q8",
    ]


def test_kv_cache_format_values():
    assert _values(KvCacheFormat) == ["fp16", "bf16", "fp8", "int8", "int4"]


def test_runtime_engine_values():
    assert _values(RuntimeEngine) == [
        "llama_cpp",
        "ollama",
        "vllm",
        "sglang",
        "exllamav2",
        "tensorrt_llm",
        "mlx",
        "lmstudio",
    ]


def test_hardware_class_values():
    assert _values(HardwareClass) == ["gpu", "cpu", "npu", "integrated_gpu"]


def test_metric_kind_values():
    assert _values(MetricKind) == [
        "ttft_ms",
        "prefill_tok_s",
        "decode_tok_s",
        "peak_vram_mib",
        "peak_ram_mib",
        "power_watt_avg",
        "temperature_c_max",
        "energy_joule",
    ]


def test_artifact_kind_values():
    assert _values(ArtifactKind) == [
        "runtime_stdout",
        "runtime_stderr",
        "runtime_config",
        "gpu_smi_trace",
        "system_topology",
        "screenshot",
        "prompt_template",
    ]
