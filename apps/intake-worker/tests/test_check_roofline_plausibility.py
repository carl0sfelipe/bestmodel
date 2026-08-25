import pytest

from check_memory_plausibility import check_memory_plausibility, minimum_vram_mib
from check_roofline_plausibility import (
    check_roofline_plausibility,
    decode_roofline_tokens_per_second,
)
from fixture_loader import load_fraudulent_run, load_valid_run
from worker_models import build_run_record


def test_valid_run_passes_roofline():
    record = build_run_record(load_valid_run())
    assert check_roofline_plausibility(record) is None


def test_valid_run_passes_memory_floor():
    record = build_run_record(load_valid_run())
    assert check_memory_plausibility(record) is None


def test_fraudulent_run_flags_roofline_violation():
    record = build_run_record(load_fraudulent_run())
    assert check_roofline_plausibility(record) == "roofline_violation"


def test_fraudulent_run_flags_impossible_memory_footprint():
    record = build_run_record(load_fraudulent_run())
    assert check_memory_plausibility(record) == "impossible_memory_footprint"


def test_decode_roofline_matches_hand_calculation():
    record = build_run_record(load_valid_run())
    # RTX 4090 (1008 GiB/s) * 0.8 * 0.9 / (8B * 4.5/8 bytes + KV read)
    roofline = decode_roofline_tokens_per_second(record)
    assert roofline == pytest.approx(171.9, rel=0.03)


def test_minimum_vram_matches_hand_calculation():
    record = build_run_record(load_valid_run())
    assert minimum_vram_mib(record) == pytest.approx(6625.8, rel=0.03)
