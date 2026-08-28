"""HuggingFace model card harvester (Epic 4, Story 4.2).

Extracts benchmark cells from the markdown of a HuggingFace model card
(style: one table row per quantization, one column per GPU, cells holding a
throughput number) and returns them as a fixture-dict for the deterministic
framework of Story 4.1 (``harvester.harvest``). Only stdlib is used; network
fetching is a thin ``urllib`` wrapper and is never exercised by tests.

Conservative semantics (violating any of these would fabricate data):

* Only markdown tables whose header row contains a mapped metric token
  ("tok/s", "t/s", "tokens per second", "tokens/sec") OR at least one column
  whose header names a GPU in the fixed alias map are considered at all.
* A cell becomes a benchmark cell only when its column header names a known
  GPU, and either the cell itself carries a metric unit ("82.3 tok/s"), or
  the cell is a bare number and the table header declares the metric
  (unit then inherited from the mapped metric, always "tok/s").
* Anything else — dashes, ranges ("28-29 tok/s"), approximations ("~13
  tok/s"), thousands separators, columns whose header is not in the GPU
  alias map (CPU, A4000, 5090, accented/unicode names, ...) — yields no
  cell. A card (or table) that does not match the documented format yields
  zero cells, which is a valid, honest result.
* GPU alias matching is case-insensitive and token-based on
  alphanumerics, so "NVIDIA GeForce RTX 3090 t/s" matches the alias
  "rtx 3090" while "5090" does not match "3090". If several aliases match
  a header, the first map entry wins.
* ``metric`` is always ``decode_tok_s`` with ``unit`` ``"tok/s"`` — the only
  mapping documented for this story.
* ``model_release_id`` is a free staging string (staging has no FK): the
  first ``#``-heading above the table (the card title) joined with the
  row's first cell, e.g. "MyModel GGUF / mymodel-Q4_K_M.gguf". Binding to
  catalog identities happens later, in the review queue (Story 4.4).
* ``recipe_id`` is always ``None``; the ``note`` field records the exact
  column/row the cell came from.
"""

from __future__ import annotations

import re
import urllib.request
from typing import Any

USER_AGENT = "canirunit-harvester/0.1"

# Documented metric mapping (fixed): alias -> (metric, unit).
METRIC_ALIASES: dict[str, tuple[str, str]] = {
    "tok/s": ("decode_tok_s", "tok/s"),
    "t/s": ("decode_tok_s", "tok/s"),
    "tokens per second": ("decode_tok_s", "tok/s"),
    "tokens/sec": ("decode_tok_s", "tok/s"),
}

# Documented GPU alias map (fixed, case-insensitive). "rtx 3090 ti" maps to
# the plain 3090 because the catalog has no 3090 Ti and staging is unbound.
GPU_ALIASES: dict[str, str] = {
    "rtx 3090": "gpu-rtx-3090",
    "3090": "gpu-rtx-3090",
    "rtx 3090 ti": "gpu-rtx-3090",
    "rtx 4090": "gpu-rtx-4090",
    "4090": "gpu-rtx-4090",
}

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_NUMBER_UNIT_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(tok/s|t/s|tokens/sec|tokens per second)$",
    re.IGNORECASE,
)
_BARE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def fetch_model_card(url: str) -> str:
    """Download a model card README from ``url`` and return its text.

    Kept for real (manual) use; tests never touch the network.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_SPLIT_RE.split(text.lower()) if token]


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    if not phrase or len(phrase) > len(tokens):
        return False
    return any(tokens[i : i + len(phrase)] == phrase for i in range(len(tokens) - len(phrase) + 1))


def _header_has_metric(header_cell: str) -> bool:
    tokens = _tokens(header_cell)
    return any(_contains_phrase(tokens, _tokens(alias)) for alias in METRIC_ALIASES)


def _header_gpu(header_cell: str) -> str | None:
    if not header_cell.isascii():  # accented/unicode GPU names are out of the map
        return None
    tokens = _tokens(header_cell)
    for alias, gpu_model_id in GPU_ALIASES.items():
        if _contains_phrase(tokens, _tokens(alias)):
            return gpu_model_id
    return None


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1


def _is_separator_line(line: str) -> bool:
    stripped = line.strip()
    return (
        _is_table_line(stripped)
        and "-" in stripped
        and set(stripped) <= set("|-: ")
    )


def _clean_text(text: str) -> str:
    return " ".join(text.strip().strip("*`_").strip().split())


def _table_title(headings: list[tuple[int, int, str]], header_index: int) -> str | None:
    h1_above = [text for index, level, text in headings if level == 1 and index < header_index]
    if h1_above:
        return h1_above[0]  # card title, i.e. the `# ` heading above the table
    any_above = [text for index, _, text in headings if index < header_index]
    return any_above[-1] if any_above else None


def _model_release_id(title: str | None, row_label: str) -> str:
    parts = [part for part in (title, row_label) if part]
    return " / ".join(parts) if parts else "unknown"


def extract_model_card_metrics(markdown_text: str, source_url: str, harvested_at: str) -> dict[str, Any]:
    """Extract benchmark cells from a model card's markdown.

    Returns a fixture-dict in the Story 4.1 format:
    ``{"source_url": str, "harvested_at": str, "cells": [...]}`` where each
    cell has ``gpu_model_id``, ``model_release_id``, ``recipe_id`` (always
    ``None``), ``metric``, ``value``, ``unit`` and a ``note``. Zero cells is
    a valid result for any card that does not match the documented table
    format. The function is pure: same input, same dict.
    """
    lines = markdown_text.splitlines()
    headings = [
        (index, len(match.group(1)), _clean_text(match.group(2)))
        for index, line in enumerate(lines)
        if (match := _HEADING_RE.match(line.strip()))
    ]

    metric, unit = METRIC_ALIASES["tok/s"]
    cells: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if (
            not _is_table_line(lines[index])
            or index + 1 >= len(lines)
            or not _is_separator_line(lines[index + 1])
        ):
            index += 1
            continue

        header_cells = _split_row(lines[index])
        header_has_metric = any(_header_has_metric(cell) for cell in header_cells)
        gpu_columns = {
            column: gpu
            for column, cell in enumerate(header_cells)
            if (gpu := _header_gpu(cell)) is not None
        }
        # Gate: header declares a mapped metric OR a known-GPU column;
        # otherwise the table is out of the documented format -> no cells.
        row_index = index + 2
        if header_has_metric or gpu_columns:
            title = _table_title(headings, index)
            while (
                row_index < len(lines)
                and _is_table_line(lines[row_index])
                and not _is_separator_line(lines[row_index])
            ):
                row_cells = _split_row(lines[row_index])
                row_label = _clean_text(row_cells[0]) if row_cells else ""
                for column, gpu_model_id in gpu_columns.items():
                    if column >= len(row_cells):
                        continue
                    raw_cell = _clean_text(row_cells[column])
                    value: float | None = None
                    unit_from_header = False
                    if match := _NUMBER_UNIT_RE.match(raw_cell):
                        value = float(match.group(1))
                    elif _BARE_NUMBER_RE.match(raw_cell) and header_has_metric:
                        value = float(raw_cell)
                        unit_from_header = True
                    if value is None:
                        continue
                    note = (
                        f"markdown table cell: column '{header_cells[column]}', row '{row_label}'"
                        + (" (unit from header)" if unit_from_header else "")
                    )
                    cells.append(
                        {
                            "gpu_model_id": gpu_model_id,
                            "model_release_id": _model_release_id(title, row_label),
                            "recipe_id": None,
                            "metric": metric,
                            "value": value,
                            "unit": unit,
                            "note": note,
                        }
                    )
                row_index += 1
        index = max(row_index, index + 2)

    return {"source_url": source_url, "harvested_at": harvested_at, "cells": cells}
