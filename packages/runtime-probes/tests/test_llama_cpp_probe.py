import pytest
from benchmark_scenario import BenchmarkScenario

from fake_runtime import FakeRuntime, load_fixture
from llama_cpp_probe import LlamaCppProbe
from probe import ProbeError, ProbeResult, Scenario
from stdout_parser import StdoutParseError

FIXTURE = load_fixture("llama_cpp_stdout.txt")


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
    probe = LlamaCppProbe(
        model_path="/models/qwen2.5-7b-instruct-q4_k_m.gguf",
        runner=FakeRuntime(FIXTURE),
    )
    result = probe.run(_scenario())

    assert isinstance(result, ProbeResult)
    assert result.runtime == "llama.cpp"
    assert result.runtime_version == "b4568"
    assert result.metrics.ttft_ms == 1711.75
    assert result.metrics.prefill_tok_s == 2392.73
    assert result.metrics.decode_tok_s == 18.67
    assert result.metrics.peak_vram_mib == 21811
    assert result.metrics.power_watt_avg == 0.0
    assert result.raw_stdout == FIXTURE


def test_command_maps_scenario_to_llama_cli_args():
    probe = LlamaCppProbe(model_path="model.gguf")
    command = probe._build_command(
        Scenario(
            prompt_tokens=4096,
            generated_tokens=128,
            batch_size=2,
            context_tokens=16384,
        )
    )
    assert "--n-predict" in command
    assert command[command.index("--n-predict") + 1] == "128"
    assert "--ctx-size" in command
    assert command[command.index("--ctx-size") + 1] == "16384"
    assert "--parallel" in command
    assert command[command.index("--parallel") + 1] == "2"


def test_malformed_stdout_raises_clear_error():
    probe = LlamaCppProbe(
        model_path="model.gguf",
        runner=FakeRuntime("no timing output at all\n"),
    )
    with pytest.raises(StdoutParseError) as excinfo:
        probe.run(_scenario(prompt_tokens=1, generated_tokens=1))
    assert "llama_cpp" in str(excinfo.value)


def test_nonzero_return_code_raises_probe_error():
    probe = LlamaCppProbe(
        model_path="model.gguf",
        runner=FakeRuntime("", returncode=1),
    )
    with pytest.raises(ProbeError) as excinfo:
        probe.run(_scenario(prompt_tokens=1, generated_tokens=1))
    assert "llama.cpp" in str(excinfo.value)
