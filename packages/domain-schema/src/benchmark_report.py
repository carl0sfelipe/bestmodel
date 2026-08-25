from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, field_validator

from benchmark_metrics import BenchmarkMetrics
from benchmark_scenario import BenchmarkScenario


class RuntimeEngine(StrEnum):
    llama_cpp = "llama_cpp"
    ollama = "ollama"
    vllm = "vllm"
    sglang = "sglang"
    exllamav2 = "exllamav2"
    tensorrt_llm = "tensorrt_llm"
    mlx = "mlx"
    lmstudio = "lmstudio"


class HardwareClass(StrEnum):
    gpu = "gpu"
    cpu = "cpu"
    npu = "npu"
    integrated_gpu = "integrated_gpu"


class ArtifactKind(StrEnum):
    runtime_stdout = "runtime_stdout"
    runtime_stderr = "runtime_stderr"
    runtime_config = "runtime_config"
    gpu_smi_trace = "gpu_smi_trace"
    system_topology = "system_topology"
    screenshot = "screenshot"
    prompt_template = "prompt_template"


class BenchmarkArtifact(BaseModel):
    artifact_kind: ArtifactKind
    sha256: str


class BenchmarkReport(BaseModel):
    schema_version: Literal["0.9.0"] = "0.9.0"
    run_id: str
    runtime: RuntimeEngine
    runtime_version: str
    hardware_fingerprint: str
    scenario: BenchmarkScenario
    metrics: BenchmarkMetrics
    artifacts: list[BenchmarkArtifact] = []

    @field_validator("runtime", mode="before")
    @classmethod
    def _coerce_runtime_alias(cls, value):
        if value == "llama.cpp":
            return "llama_cpp"
        return value
