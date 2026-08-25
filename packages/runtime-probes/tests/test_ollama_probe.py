import pytest
from benchmark_scenario import BenchmarkScenario

from fake_runtime import FakeRuntime, load_fixture
from ollama_probe import OllamaProbe
from probe import ProbeError
from stdout_parser import StdoutParseError

FIXTURE = load_fixture("ollama_stdout.txt")


def _scenario(**kwargs):
    defaults = dict(
        prompt_tokens=4096,
        generated_tokens=512,
        batch_size=1,
        context_tokens=8192,
    )
    defaults.update(kwargs)
    return BenchmarkScenario(**defaults)


def test_probe_metrics_match_fixture():
    probe = OllamaProbe(
        model_name="qwen2.5:7b",
        peak_vram_mib=21811,
        runner=FakeRuntime(FIXTURE),
    )
    result = probe.run(_scenario())

    assert result.runtime == "ollama"
    assert result.metrics.ttft_ms == 2050.0
    assert result.metrics.prefill_tok_s == 2048.0
    assert result.metrics.decode_tok_s == 20.0
    assert result.metrics.peak_vram_mib == 21811
    assert result.raw_stdout == FIXTURE


def test_command_is_ollama_run_verbose():
    probe = OllamaProbe(model_name="qwen2.5:7b")
    command = probe._build_command(
        type("S", (), {"prompt_tokens": 1, "generated_tokens": 1, "batch_size": 1, "context_tokens": 4})()
    )
    assert command == ["ollama", "run", "qwen2.5:7b", "--verbose"]


def test_missing_peak_vram_raises_clear_error():
    probe = OllamaProbe(model_name="qwen2.5:7b", runner=FakeRuntime(FIXTURE))
    with pytest.raises(ProbeError) as excinfo:
        probe.run(_scenario())
    assert "ollama" in str(excinfo.value)


def test_malformed_stdout_raises_clear_error():
    probe = OllamaProbe(
        model_name="qwen2.5:7b",
        peak_vram_mib=21811,
        runner=FakeRuntime("not ollama output at all\n"),
    )
    with pytest.raises(StdoutParseError) as excinfo:
        probe.run(_scenario(prompt_tokens=1, generated_tokens=1))
    assert "ollama" in str(excinfo.value)
