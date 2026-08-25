"""Ollama probe adapter.

Runs a ``BenchmarkScenario`` via ``ollama run --verbose`` and converts the
``/api/generate``-style timings (``load_ns``, ``prompt_eval_count``,
``prompt_eval_duration``, ``eval_count``, ``eval_duration``) into the standard
metric dict. Third-party process calls are allowed only in this file.
"""

import subprocess
from typing import Any

from benchmark_metrics import BenchmarkMetrics
from benchmark_scenario import BenchmarkScenario

from probe import ProbeError, ProbeResult, Scenario
from stdout_parser import parse_ollama_metrics


class OllamaProbe:
    """Runs a standardized scenario through Ollama."""

    runtime = "ollama"

    def __init__(
        self,
        model_name: str,
        *,
        executable: str = "ollama",
        peak_vram_mib: int = 0,
        power_watt_avg: float = 0.0,
        runtime_version: str = "unknown",
        runner: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.executable = executable
        self.peak_vram_mib = peak_vram_mib
        self.power_watt_avg = power_watt_avg
        self.runtime_version = runtime_version
        self._runner = runner or subprocess.run

    def _build_command(self, scenario: Scenario) -> list[str]:
        return [self.executable, "run", self.model_name, "--verbose"]

    def _capture_stdout(self, command: list[str]) -> str:
        result = self._runner(command, capture_output=True, text=True)
        returncode = getattr(result, "returncode", 0)
        if returncode != 0:
            raise ProbeError(
                self.runtime,
                f"command failed with return code {returncode}: "
                f"{' '.join(command)}",
            )
        stdout = getattr(result, "stdout", "")
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        return stdout

    def run(self, scenario: BenchmarkScenario) -> ProbeResult:
        std_scenario = Scenario.from_benchmark_scenario(scenario)
        stdout = self._capture_stdout(self._build_command(std_scenario))
        metrics = parse_ollama_metrics(stdout)
        if self.peak_vram_mib > 0:
            metrics["peak_vram_mib"] = self.peak_vram_mib
        if metrics["peak_vram_mib"] <= 0:
            raise ProbeError(
                self.runtime,
                "peak_vram_mib is not reported in Ollama stdout; pass a "
                "positive peak_vram_mib to OllamaProbe",
            )
        metrics["power_watt_avg"] = self.power_watt_avg
        return ProbeResult(
            runtime=self.runtime,
            runtime_version=self.runtime_version,
            metrics=BenchmarkMetrics(**metrics),
            raw_stdout=stdout,
        )
