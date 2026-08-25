import pytest
from pydantic import ValidationError

from benchmark_metrics import BenchmarkMetrics


def test_valid_metrics_parse():
    metrics = BenchmarkMetrics(
        ttft_ms=100.0,
        prefill_tok_s=1000.0,
        decode_tok_s=20.0,
        peak_vram_mib=1024,
        power_watt_avg=300.0,
    )
    assert metrics.peak_vram_mib == 1024
    assert metrics.decode_tok_s == 20.0


def test_rejects_non_positive_peak_vram():
    with pytest.raises(ValidationError):
        BenchmarkMetrics(
            ttft_ms=100.0,
            prefill_tok_s=1000.0,
            decode_tok_s=20.0,
            peak_vram_mib=0,
            power_watt_avg=300.0,
        )


def test_rejects_negative_decode_rate():
    with pytest.raises(ValidationError):
        BenchmarkMetrics(
            ttft_ms=100.0,
            prefill_tok_s=1000.0,
            decode_tok_s=-0.5,
            peak_vram_mib=1024,
            power_watt_avg=300.0,
        )
