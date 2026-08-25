"""Standard probe protocol and shared data structures.

This module is runtime-agnostic: it never launches third-party processes and
works for any runtime adapter (llama.cpp, Ollama, vLLM, ...).
"""

from dataclasses import dataclass
from typing import Protocol

from benchmark_metrics import BenchmarkMetrics
from benchmark_scenario import BenchmarkScenario


@dataclass(frozen=True)
class Scenario:
    """Standalone scenario descriptor used to build runtime invocations.

    Structurally mirrors ``BenchmarkScenario`` from domain-schema so probes can
    build runtime arguments without depending on the Pydantic model.
    """

    prompt_tokens: int
    generated_tokens: int
    batch_size: int = 1
    context_tokens: int = 0

    @classmethod
    def from_benchmark_scenario(cls, scenario: BenchmarkScenario) -> "Scenario":
        return cls(
            prompt_tokens=scenario.prompt_tokens,
            generated_tokens=scenario.generated_tokens,
            batch_size=scenario.batch_size,
            context_tokens=scenario.context_tokens,
        )


@dataclass(frozen=True)
class ProbeResult:
    """Normalized result produced by a runtime probe."""

    runtime: str
    runtime_version: str
    metrics: BenchmarkMetrics
    raw_stdout: str


class Probe(Protocol):
    """Contract implemented by every runtime adapter."""

    runtime: str

    def run(self, scenario: BenchmarkScenario) -> ProbeResult: ...


class ProbeError(RuntimeError):
    """Raised when a runtime probe fails outside of stdout parsing."""

    def __init__(self, runtime: str, message: str) -> None:
        self.runtime = runtime
        super().__init__(f"[{runtime}] {message}")
