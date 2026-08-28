"""Tests for the model card harvester (Story 4.2).

The real fixture (``fixtures/model-card.md``) is a verbatim commit of
https://huggingface.co/smarttasks/phi-4-GGUF/raw/main/README.md — a card with
a TheBloke-style "Speed — generation tok/s by device" table: one row per
quant, one column per GPU, unit-less numbers under a column header that names
the GPU and the metric ("NVIDIA GeForce RTX 3090 t/s"). Tests never touch the
network; everything else is a synthetic card exercising the documented
conservative semantics of the spec.
"""

from __future__ import annotations

import json
from pathlib import Path

from harvester import harvest
from model_card_harvester import GPU_ALIASES, extract_model_card_metrics

FIXTURES = Path(__file__).parent / "fixtures"
CARD = FIXTURES / "model-card.md"
META = FIXTURES / "model-card.meta.json"


def _extract_real_card() -> dict:
    meta = json.loads(META.read_text(encoding="utf-8"))
    return extract_model_card_metrics(
        CARD.read_text(encoding="utf-8"), meta["source_url"], meta["fetched_at"]
    )


def test_real_fixture_yields_decode_tok_s_cells_on_mapped_gpu() -> None:
    fixture = _extract_real_card()
    meta = json.loads(META.read_text(encoding="utf-8"))

    assert fixture["source_url"] == meta["source_url"]
    assert fixture["harvested_at"] == meta["fetched_at"]
    cells = fixture["cells"]
    assert len(cells) >= 1
    # Exact expectations for the committed fixture: the only mapped-GPU column
    # is "NVIDIA GeForce RTX 3090 t/s" (CPU and RTX A4000 are out of the map),
    # with one unit-less cell per quantization row.
    assert len(cells) == 5
    assert {cell["gpu_model_id"] for cell in cells} == {"gpu-rtx-3090"}
    assert {cell["gpu_model_id"] for cell in cells} <= set(GPU_ALIASES.values())
    assert sorted(cell["value"] for cell in cells) == [53.2, 63.0, 71.0, 73.2, 82.3]
    for cell in cells:
        assert cell["metric"] == "decode_tok_s"
        assert cell["unit"] == "tok/s"
        assert cell["recipe_id"] is None
        assert cell["note"]
        assert "phi-4" in cell["model_release_id"]


def test_extraction_is_deterministic() -> None:
    assert _extract_real_card() == _extract_real_card()
    # Byte-level determinism of the fixture payload too (Story 4.1 hashes it).
    assert json.dumps(_extract_real_card()) == json.dumps(_extract_real_card())


def test_tables_outside_documented_format_yield_zero_cells() -> None:
    off_format = """# Off Format Card

| Benchmark | Score |
| --- | --- |
| MMLU | 42.1 |
| HellaSwag | 60.0 |

## Metric declared but no GPU column

| Quant | tok/s |
| --- | --- |
| Q4_K_M | 12.5 tok/s |

## GPU column but no metric anywhere in the header

| Quant | RTX 4090 |
| --- | --- |
| Q4_K_M | 42.0 |

## Unicode GPU name is outside the alias map

| Quant | RTX 4090 á |
| --- | --- |
| Q4_K_M | 42.0 tok/s |
"""
    fixture = extract_model_card_metrics(off_format, "https://example/off-format", "2026-08-26")

    assert fixture["source_url"] == "https://example/off-format"
    assert fixture["harvested_at"] == "2026-08-26"
    assert fixture["cells"] == []


def test_harvest_integration_stages_unverified_harvested_cells(tmp_path: Path) -> None:
    fixture = _extract_real_card()
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    staging = tmp_path / "staging.jsonl"

    result = harvest(fixture_path, staging)

    assert result.added >= 1
    rows = [json.loads(line) for line in staging.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == result.added
    for row in rows:
        assert row["source_class"] == "harvested"
        assert row["status"] == "unverified"
        assert row["metric"] == "decode_tok_s"
        assert row["gpu_model_id"] in GPU_ALIASES.values()
        assert row["unit"] == "tok/s"
        assert row["harvested_at"] == fixture["harvested_at"]

    rerun = harvest(fixture_path, staging)
    assert rerun.added == 0
    assert rerun.skipped == result.added
    assert len(staging.read_text(encoding="utf-8").splitlines()) == len(rows)


def test_synthetic_card_covers_every_gpu_alias_and_unit_variants() -> None:
    synthetic = """# Test Model GGUF

Benchmarks measured with llama.cpp on a quiet machine.

## Explicit units in cells, header has no metric token

| Quant | RTX 3090 | 3090 | rtx 3090 ti | RTX 4090 | 4090 |
| --- | --- | --- | --- | --- | --- |
| Q4_K_M | 41.5 tok/s | 42.5 tok/s | 43.5 tok/s | 44.5 tok/s | 45.5 tok/s |
| Q8_0 | 31.5 tok/s | 32.5 tok/s | 33.5 tok/s | 34.5 tok/s | 35.5 tok/s |

## Metric token in the header, cells with and without unit

| Quant | tok/s on RTX 3090 | tokens per second on RTX 4090 |
| --- | --- | --- |
| Q4_K_M | 51.5 | 52.5 |
| Q8_0 | 53.5 tok/s | 54.5 |
"""
    fixture = extract_model_card_metrics(synthetic, "https://example/synthetic", "2026-08-26")
    cells = fixture["cells"]

    # Table 1: every column is a mapped GPU alias; cells carry "tok/s" so they
    # are accepted even though the header declares no metric. 2 rows x 5 cols.
    # Table 2: metric in the header accepts bare numbers too. 2 rows x 2 cols.
    assert len(cells) == 14
    assert all(cell["metric"] == "decode_tok_s" for cell in cells)
    assert all(cell["unit"] == "tok/s" for cell in cells)
    assert all(cell["recipe_id"] is None for cell in cells)

    def pairs(note_needle: str) -> list[tuple[str, float]]:
        return sorted(
            (cell["gpu_model_id"], cell["value"])
            for cell in cells
            if note_needle in cell["note"]
        )

    assert pairs("column 'RTX 3090'") == [("gpu-rtx-3090", 31.5), ("gpu-rtx-3090", 41.5)]
    assert pairs("column '3090'") == [("gpu-rtx-3090", 32.5), ("gpu-rtx-3090", 42.5)]
    assert pairs("column 'rtx 3090 ti'") == [("gpu-rtx-3090", 33.5), ("gpu-rtx-3090", 43.5)]
    assert pairs("column 'RTX 4090'") == [("gpu-rtx-4090", 34.5), ("gpu-rtx-4090", 44.5)]
    assert pairs("column '4090'") == [("gpu-rtx-4090", 35.5), ("gpu-rtx-4090", 45.5)]

    with_units_from_header = [
        (cell["gpu_model_id"], cell["value"])
        for cell in cells
        if "(unit from header)" in cell["note"]
    ]
    assert sorted(with_units_from_header) == [
        ("gpu-rtx-3090", 51.5),
        ("gpu-rtx-4090", 52.5),
        ("gpu-rtx-4090", 54.5),
    ]
    # 11 cells carry the unit explicitly, 3 inherit it from the header metric.
    assert len(cells) - len(with_units_from_header) == 11
    # model_release_id is derived from the card title heading + the table row.
    assert {cell["model_release_id"] for cell in cells} == {
        "Test Model GGUF / Q4_K_M",
        "Test Model GGUF / Q8_0",
    }
