from calculate_modified_zscore import (
    calculate_modified_zscore,
    check_statistical_plausibility,
    is_statistical_outlier,
)
from fixture_loader import load_valid_run
from worker_models import build_run_record


def test_insufficient_peers_skips_scoring():
    assert calculate_modified_zscore(95.0, [94.0]) is None


def test_zero_mad_skips_scoring():
    assert calculate_modified_zscore(95.0, [95.0, 95.0, 95.0]) is None


def test_typical_value_is_not_an_outlier():
    zscore = calculate_modified_zscore(95.0, [90.0, 100.0, 96.0, 94.0])
    assert zscore is not None
    assert not is_statistical_outlier(zscore)


def test_extreme_value_is_an_outlier():
    zscore = calculate_modified_zscore(300.0, [90.0, 95.0, 100.0])
    assert zscore is not None
    assert is_statistical_outlier(zscore)


def test_check_flags_statistical_outlier():
    record = build_run_record(load_valid_run())
    record.metrics["decode_tok_s"] = 300.0
    flag = check_statistical_plausibility(record, [90.0, 95.0, 100.0])
    assert flag == "statistical_outlier"


def test_check_passes_consistent_peers():
    record = build_run_record(load_valid_run())
    assert check_statistical_plausibility(record, [90.0, 96.0, 94.0]) is None
