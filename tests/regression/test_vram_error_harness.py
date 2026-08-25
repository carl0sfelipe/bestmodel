from tests.regression.vram_error_harness import (
    CORPUS,
    P50_TARGET_PERCENT,
    p50_error_percent,
    relative_error_percent,
)


def test_corpus_has_measured_cases():
    assert len(CORPUS) >= 2
    for case in CORPUS:
        assert case["measured_peak_mib"] > 0


def test_individual_errors_are_bounded():
    for case in CORPUS:
        assert relative_error_percent(case) < 15.0, case["name"]


def test_p50_error_meets_exit_criterion():
    assert p50_error_percent() < P50_TARGET_PERCENT
