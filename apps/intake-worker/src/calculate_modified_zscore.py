"""Robust statistical outlier scoring (plan section 12.4).

Uses the MAD-based modified z-score. When MAD is zero (identical samples or too
few peers) the score is skipped rather than producing a divide-by-zero.
"""

from __future__ import annotations

from statistics import median

from worker_models import RunRecord

CONSISTENCY_CONSTANT = 0.6745
OUTLIER_THRESHOLD = 3.5
STATISTICAL_OUTLIER = "statistical_outlier"
MINIMUM_SAMPLE_COUNT = 3


def calculate_modified_zscore(sample: float, peers: list[float]) -> float | None:
    population = peers + [sample]
    if len(population) < MINIMUM_SAMPLE_COUNT:
        return None
    center = median(population)
    mad = median(abs(value - center) for value in population)
    if mad == 0:
        return None
    return CONSISTENCY_CONSTANT * (sample - center) / mad


def is_statistical_outlier(modified_zscore: float | None) -> bool:
    return modified_zscore is not None and abs(modified_zscore) > OUTLIER_THRESHOLD


def check_statistical_plausibility(record: RunRecord, peer_decode_values: list[float]) -> str | None:
    zscore = calculate_modified_zscore(record.metrics["decode_tok_s"], peer_decode_values)
    if is_statistical_outlier(zscore):
        return STATISTICAL_OUTLIER
    return None
