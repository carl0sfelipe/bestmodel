"""Unit tests for the shared match honesty rules (S48)."""

from __future__ import annotations

from benchmark_report import RuntimeEngine

from src.services.match_honesty import TEXT_GENERATION_ENGINES, text_generation_runtimes


def test_every_engine_is_classified():
    # A new RuntimeEngine must be placed on purpose, not silently dropped.
    assert TEXT_GENERATION_ENGINES | {"comfyui"} == {engine.value for engine in RuntimeEngine}


def test_filter_drops_diffusion_engine():
    rows = [{"id": "llama-cpp", "engine": "llama_cpp"}, {"id": "comfyui", "engine": "comfyui"}]
    assert [row["id"] for row in text_generation_runtimes(rows)] == ["llama-cpp"]
