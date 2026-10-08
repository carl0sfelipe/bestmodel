"""Honesty rules shared by the match routes (S48).

Both match services rank roofline estimates, never measurements, so every row
declares ``source_class='derived'`` (see ``source_transparency.py``). Their
throughput fields are text-generation decode/prefill numbers, so only engines
that serve text generation are evaluated: a diffusion engine (comfyui) under
a text model is a meaningless cell, not a slow one.
"""

from __future__ import annotations

from typing import Any

MATCH_SOURCE_CLASS = "derived"

TEXT_GENERATION_ENGINES = frozenset(
    {"llama_cpp", "ollama", "vllm", "sglang", "exllamav2", "tensorrt_llm", "mlx", "lmstudio"}
)


def text_generation_runtimes(runtimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only runtimes whose engine serves text generation."""
    return [row for row in runtimes if row["engine"] in TEXT_GENERATION_ENGINES]
