"""Runtime evidence extraction and consistency checks (plan section 12.2).

Parses the ``runtime_stdout`` artifact for reported metric lines and rejects the
run when key evidence is missing or contradicts the submitted metrics.
"""

from __future__ import annotations

from worker_models import RunRecord

STDOUT_ARTIFACT_KIND = "runtime_stdout"
EVIDENCE_METRIC_KEYS = ("ttft_ms", "prefill_tok_s", "decode_tok_s", "peak_vram_mib")
RELATIVE_TOLERANCE = 0.10
EVIDENCE_LINE_PREFIX = "metric "


def extract_runtime_evidence(record: RunRecord) -> list[str]:
    reasons: list[str] = []
    stdout_content = _find_stdout_content(record)
    if stdout_content is None:
        return ["missing_runtime_stdout_evidence"]
    evidence = parse_metric_lines(stdout_content)
    for key in EVIDENCE_METRIC_KEYS:
        if key not in evidence:
            reasons.append(f"missing_evidence:{key}")
            continue
        if not _values_consistent(evidence[key], record.metrics.get(key, 0.0)):
            reasons.append(f"evidence_mismatch:{key}")
    return reasons


def _find_stdout_content(record: RunRecord) -> str | None:
    for artifact in record.artifacts:
        if artifact.artifact_kind == STDOUT_ARTIFACT_KIND:
            return artifact.content
    return None


def parse_metric_lines(stdout_content: str) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for line in stdout_content.splitlines():
        stripped = line.strip()
        if not stripped.startswith(EVIDENCE_LINE_PREFIX):
            continue
        fields = stripped.split()
        if len(fields) != 3:
            continue
        try:
            parsed[fields[1]] = float(fields[2])
        except ValueError:
            continue
    return parsed


def _values_consistent(evidence_value: float, reported_value: float) -> bool:
    if reported_value == 0.0:
        return evidence_value == 0.0
    return abs(evidence_value - reported_value) <= RELATIVE_TOLERANCE * abs(reported_value)
