import json
from pathlib import Path

from benchmark_report import BenchmarkReport

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schema" / "benchmark_report.v0.9.0.json"
)


def test_committed_schema_matches_model_schema():
    committed = json.loads(SCHEMA_PATH.read_text())
    assert committed == BenchmarkReport.model_json_schema()
