import pytest

from calculate_ranking_score import (
    calculate_ranking_score,
    energy_efficiency,
    percentile,
    robust_min_max,
)


def candidate(decode=100.0, prefill=1000.0, context=8192, quality=0.9, power=300.0, trust=0.8, feasible=True, vram=20000.0):
    return {
        "decode_tok_s": decode,
        "prefill_tok_s": prefill,
        "context_tokens": context,
        "quality_retention_estimate": quality,
        "power_watt_avg": power,
        "peak_vram_mib": 18000.0,
        "vram_capacity_mib": vram,
        "peak_vram_mib_reported": 18000.0,
        "feasible": feasible,
        "trust_score": trust,
    }


def test_robust_min_max_clamps_to_zero_and_one():
    assert robust_min_max(10.0, 50.0, 150.0) == 0.0
    assert robust_min_max(200.0, 50.0, 150.0) == 1.0
    assert robust_min_max(100.0, 50.0, 150.0) == pytest.approx(0.5)


def test_robust_min_max_without_dispersion_returns_one():
    assert robust_min_max(42.0, 42.0, 42.0) == 1.0


def test_percentile_linear_interpolation():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 50) == pytest.approx(25.0)
    assert percentile([7.0], 95) == 7.0


def test_scores_stay_within_unit_interval():
    cohort = [
        candidate(decode=50.0, trust=0.3),
        candidate(decode=150.0, trust=0.9),
        candidate(decode=250.0, trust=0.6),
    ]
    for scored in calculate_ranking_score(cohort):
        assert 0.0 <= scored["rank_score"] <= 1.0


def test_higher_decode_and_trust_rank_higher():
    cohort = [candidate(decode=50.0, trust=0.2), candidate(decode=250.0, trust=0.9)]
    scored = calculate_ranking_score(cohort)
    assert scored[1]["rank_score"] > scored[0]["rank_score"]


def test_infeasible_candidate_scores_exactly_zero():
    cohort = [candidate(decode=250.0), candidate(decode=150.0, feasible=False)]
    scored = calculate_ranking_score(cohort)
    infeasible = next(c for c in scored if not c["feasible"])
    assert infeasible["rank_score"] == 0.0


def test_single_feasible_candidate_scores_one():
    scored = calculate_ranking_score([candidate()])
    assert scored[0]["rank_score"] == pytest.approx(1.0)


def test_zero_power_yields_zero_energy_efficiency():
    assert energy_efficiency({"decode_tok_s": 100.0, "power_watt_avg": 0.0}) == 0.0
    assert energy_efficiency({"decode_tok_s": 100.0, "power_watt_avg": 250.0}) == pytest.approx(0.4)
