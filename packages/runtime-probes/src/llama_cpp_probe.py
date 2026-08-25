"""llama.cpp probe adapter.

Maps a ``BenchmarkScenario`` to llama-cli arguments and parses the
``--verbose`` stdout. Third-party process calls are allowed only in this file.
"""

import re
import subprocess
from typing import Any

from benchmark_metrics import BenchmarkMetrics
from benchmark_scenario import BenchmarkScenario

from probe import ProbeError, ProbeResult, Scenario
from stdout_parser import parse_llama_cpp_metrics

_BUILD_RE = re.compile(r"build\s*[:=]\s*([^\s)]+)")


class LlamaCppProbe:
    """Runs a standardized scenario through llama-cli."""

    runtime = "llama.cpp"

    def __init__(
        self,
        model_path: str,
        *,
        executable: str = "llama-cli",
        prompt_text: str | None = None,
        runtime_version: str | None = None,
        runner: Any | None = None,
    ) -> None:
        self.model_path = model_path
        self.executable = executable
        self.prompt_text = prompt_text
        self.runtime_version = runtime_version
        self._runner = runner or subprocess.run

    def _build_command(self, scenario: Scenario) -> list[str]:
        command = [
            self.executable,
            "-m",
            self.model_path,
            "--verbose",
            "--n-predict",
            str(scenario.generated_tokens),
            "--ctx-size",
            str(scenario.context_tokens),
            "--parallel",
            str(scenario.batch_size),
        ]
        if self.prompt_text is not None:
            command += ["--prompt", self.prompt_text]
        return command

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

    def _detect_version(self, stdout: str) -> str | None:
        match = _BUILD_RE.search(stdout)
        return match.group(1) if match else None

    def run(self, scenario: BenchmarkScenario) -> ProbeResult:
        std_scenario = Scenario.from_benchmark_scenario(scenario)
        command = self._build_command(std_scenario)
        stdout = self._capture_stdout(command)
        metrics = parse_llama_cpp_metrics(stdout)
        version = self.runtime_version or self._detect_version(stdout) or "unknown"
        return ProbeResult(
            runtime=self.runtime,
            runtime_version=version,
            metrics=BenchmarkMetrics(**metrics),
            raw_stdout=stdout,
        )
