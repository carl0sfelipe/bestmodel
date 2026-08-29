"""Run record model and domain object builders for the intake worker.

A run event carries everything the validation pipeline needs: report fields,
reported metrics, catalog rows (hardware/model/quant), the benchmark scenario
and the uploaded artifacts with their declared digests and raw content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from benchmark_scenario import BenchmarkScenario
from gpu_spec import GpuSpec
from model_arch import ModelArch
from quant_profile import QuantProfile

SUPPORTED_SCHEMA_VERSION = "0.9.0"


def scenario_is_video(record: "RunRecord") -> bool:
    """Video runs carry clip dimensions instead of token dimensions (AD-1);
    their evidence keys and plausibility rules differ from the LLM ones."""
    return record.scenario.get("scenario_kind") == "video"

EVIDENCE_ARTIFACT_KINDS = ("runtime_stdout", "runtime_config", "gpu_smi_trace")


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_kind: str
    declared_sha256: str
    content: str


@dataclass(frozen=True)
class DimensionGroup:
    hardware_model_id: str
    model_release_id: str
    quantization_profile_id: str
    runtime_engine: str
    context_tokens: int
    batch_size: int


@dataclass
class RunRecord:
    run_id: str
    schema_version: str
    runtime_version: Optional[str]
    runtime_engine: str
    hardware_fingerprint: str
    signature_valid: bool
    duration_seconds: float
    hardware: dict[str, Any]
    model: dict[str, Any]
    quant: dict[str, Any]
    scenario: dict[str, Any]
    metrics: dict[str, float]
    dimension: DimensionGroup
    artifacts: list[ArtifactRecord] = field(default_factory=list)


def build_run_record(payload: dict[str, Any]) -> RunRecord:
    dimension_payload = payload["dimension"]
    dimension = DimensionGroup(
        hardware_model_id=dimension_payload["hardware_model_id"],
        model_release_id=dimension_payload["model_release_id"],
        quantization_profile_id=dimension_payload["quantization_profile_id"],
        runtime_engine=dimension_payload["runtime_engine"],
        # Video scenarios carry no token dimensions (AD-1); 0/1 keep the
        # dimension group hashable without inventing token counts.
        context_tokens=int(dimension_payload["context_tokens"] or 0),
        batch_size=int(dimension_payload["batch_size"] or 1),
    )
    artifacts = [
        ArtifactRecord(
            artifact_kind=item["artifact_kind"],
            declared_sha256=item["declared_sha256"],
            content=item["content"],
        )
        for item in payload.get("artifacts", [])
    ]
    return RunRecord(
        run_id=payload["run_id"],
        schema_version=payload["schema_version"],
        runtime_version=payload.get("runtime_version"),
        runtime_engine=payload["runtime_engine"],
        hardware_fingerprint=payload["hardware_fingerprint"],
        signature_valid=bool(payload["signature_valid"]),
        duration_seconds=float(payload["duration_seconds"]),
        hardware=payload["hardware"],
        model=payload["model"],
        quant=payload["quant"],
        scenario=payload["scenario"],
        metrics={key: float(value) for key, value in payload["metrics"].items()},
        dimension=dimension,
        artifacts=artifacts,
    )


def build_gpu_spec(record: RunRecord) -> GpuSpec:
    return GpuSpec(**record.hardware)


def build_model_arch(record: RunRecord) -> ModelArch:
    return ModelArch(**record.model)


def build_quant_profile(record: RunRecord) -> QuantProfile:
    return QuantProfile(**record.quant)


def build_scenario(record: RunRecord) -> BenchmarkScenario:
    return BenchmarkScenario(**record.scenario)
