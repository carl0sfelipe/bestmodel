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


def test_zero_peak_vram_allowed_negative_rejected():
    # Zero is a valid video-run report (no nvidia-smi on the bench machine);
    # negative values are still rejected.
    metrics = BenchmarkMetrics(
        ttft_ms=0.0,
        prefill_tok_s=0.0,
        decode_tok_s=0.0,
        peak_vram_mib=0,
        power_watt_avg=0.0,
    )
    assert metrics.peak_vram_mib == 0
    with pytest.raises(ValidationError):
        BenchmarkMetrics(
            ttft_ms=100.0,
            prefill_tok_s=1000.0,
            decode_tok_s=20.0,
            peak_vram_mib=-1,
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
