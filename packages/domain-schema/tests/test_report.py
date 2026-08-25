import json

from benchmark_report import ArtifactKind, BenchmarkReport, RuntimeEngine

EXAMPLE_REPORT_JSON = """
{
  "schema_version": "0.9.0",
  "run_id": "01J9XYZ...",
  "runtime": "llama.cpp",
  "runtime_version": "b4568",
  "hardware_fingerprint": "sha256:...",
  "scenario": {
    "prompt_tokens": 4096,
    "generated_tokens": 512,
    "batch_size": 1,
    "context_tokens": 8192
  },
  "metrics": {
    "ttft_ms": 812,
    "prefill_tok_s": 5041,
    "decode_tok_s": 18.7,
    "peak_vram_mib": 21811,
    "power_watt_avg": 412
  },
  "artifacts": [
    {
      "artifact_kind": "runtime_stdout",
      "sha256": "..."
    }
  ]
}
"""


def test_example_report_validates():
    report = BenchmarkReport.model_validate(json.loads(EXAMPLE_REPORT_JSON))

    assert report.schema_version == "0.9.0"
    assert report.runtime == RuntimeEngine.llama_cpp
    assert report.scenario.prompt_tokens == 4096
    assert report.metrics.decode_tok_s == 18.7
    assert report.artifacts[0].artifact_kind == ArtifactKind.runtime_stdout
