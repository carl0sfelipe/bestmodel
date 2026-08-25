"""Trust score aggregation from the subscores of plan section 11.9.

Every subscore stays within [0, 1]; the final score is the weighted sum. Phase 0
uses deterministic defaults for subscores that need account history or peer
attestation data not yet available.
"""

from __future__ import annotations

from worker_models import EVIDENCE_ARTIFACT_KINDS, RunRecord

SUBSCORE_WEIGHTS = {
    "environment_completeness": 0.25,
    "statistical_plausibility": 0.25,
    "reproducibility_score": 0.20,
    "account_maturity": 0.15,
    "peer_corroboration": 0.15,
}

PHASE0_DEFAULT_SUBSCORE = 0.5
PENALTY_PER_OUTLIER_FLAG = 0.5
PEER_COUNT_FOR_FULL_CORROBORATION = 5


def environment_completeness(record: RunRecord) -> float:
    present_kinds = {artifact.artifact_kind for artifact in record.artifacts}
    covered = sum(1 for kind in EVIDENCE_ARTIFACT_KINDS if kind in present_kinds)
    return covered / len(EVIDENCE_ARTIFACT_KINDS)


def statistical_plausibility(outlier_flags: list[str]) -> float:
    return max(0.0, 1.0 - PENALTY_PER_OUTLIER_FLAG * len(outlier_flags))


def peer_corroboration(peer_count: int) -> float:
    return min(1.0, peer_count / PEER_COUNT_FOR_FULL_CORROBORATION)


def calculate_trust_assessment(
    record: RunRecord, outlier_flags: list[str], peer_count: int
) -> dict[str, float]:
    assessment = {
        "environment_completeness": environment_completeness(record),
        "statistical_plausibility": statistical_plausibility(outlier_flags),
        "reproducibility_score": PHASE0_DEFAULT_SUBSCORE,
        "account_maturity": PHASE0_DEFAULT_SUBSCORE,
        "peer_corroboration": peer_corroboration(peer_count),
    }
    assessment["final_score"] = sum(
        SUBSCORE_WEIGHTS[name] * score for name, score in assessment.items()
    )
    return {name: min(1.0, max(0.0, score)) for name, score in assessment.items()}
