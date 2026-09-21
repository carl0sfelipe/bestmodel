"""Intent catalog loader. The id list lives in catalog.json, read by path.

pool-backend does not import packages/ or apps/. BESTMODEL_INTENT_CATALOG
overrides the path so a test can add a row without editing this module.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_CATALOG = Path(__file__).resolve().parents[3] / "packages" / "intent-catalog" / "catalog.json"


def catalog_path() -> Path:
    override = os.environ.get("BESTMODEL_INTENT_CATALOG")
    if override:
        return Path(override)
    return _CATALOG


def load() -> dict:
    """Read the catalog on every call. No module-level cache."""
    return json.loads(catalog_path().read_text(encoding="utf-8"))


def storable_categories() -> tuple[str, ...]:
    return tuple(row["id"] for row in load()["intents"] if row["storable"])


def category_check_sql() -> str:
    inner = ",".join(f"'{name}'" for name in storable_categories())
    return f"CHECK(category IN ({inner}))"


def classify(display_name: str, hf_id: str = "") -> str:
    """First matching classify regex in file order, else fallbackIntent."""
    catalog = load()
    text = f"{display_name or ''} {hf_id or ''}"
    for row in catalog["intents"]:
        pattern = row.get("classify")
        if pattern and re.search(pattern, text, re.I):
            return row["id"]
    return catalog["fallbackIntent"]
