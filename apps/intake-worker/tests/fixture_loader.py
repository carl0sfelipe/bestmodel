"""Shared fixture loader for intake-worker tests."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def load_valid_run() -> dict:
    return load_fixture("valid_run.json")


def load_fraudulent_run() -> dict:
    return load_fixture("fraudulent_run.json")
