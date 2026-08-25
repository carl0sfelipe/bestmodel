import pytest

from fake_runtime import load_fixture
from stdout_parser import (
    StdoutParseError,
    parse_llama_cpp_metrics,
    parse_ollama_metrics,
)


def test_parse_llama_cpp_known_values():
    metrics = parse_llama_cpp_metrics(load_fixture("llama_cpp_stdout.txt"))
    assert metrics["ttft_ms"] == 1711.75
    assert metrics["prefill_tok_s"] == 2392.73
    assert metrics["decode_tok_s"] == 18.67
    assert metrics["peak_vram_mib"] == 21811
    assert metrics["power_watt_avg"] == 0.0


def test_parse_ollama_known_values():
    metrics = parse_ollama_metrics(load_fixture("ollama_stdout.txt"))
    assert metrics["ttft_ms"] == 2050.0
    assert metrics["prefill_tok_s"] == 2048.0
    assert metrics["decode_tok_s"] == 20.0


def test_ollama_text_only_path_matches_json_path():
    text = (
        "load duration:        50.0ms\n"
        "prompt eval count:    4096 token(s)\n"
        "prompt eval duration: 2.0s\n"
        "eval count:           512 token(s)\n"
        "eval duration:        25.6s\n"
    )
    metrics = parse_ollama_metrics(text)
    assert metrics["ttft_ms"] == 2050.0
    assert metrics["prefill_tok_s"] == 2048.0
    assert metrics["decode_tok_s"] == 20.0


def test_llama_missing_fields_raise_with_runtime():
    with pytest.raises(StdoutParseError) as excinfo:
        parse_llama_cpp_metrics("llama-cli started but produced no timing lines\n")
    assert "llama_cpp" in str(excinfo.value)


def test_ollama_missing_fields_raise_with_runtime():
    with pytest.raises(StdoutParseError) as excinfo:
        parse_ollama_metrics("total duration: 5.0s\n")
    assert "ollama" in str(excinfo.value)
