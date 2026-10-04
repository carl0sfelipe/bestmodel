"""S37 root guards: the catalog is well-formed, derived JSON stays honest,
and the pool-backend suite actually runs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO / "packages" / "intent-catalog" / "catalog.json"
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ROW_FIELDS = {
    "id",
    "name",
    "glyph",
    "desc",
    "modality",
    "storable",
    "metric",
    "forbiddenFields",
    "classify",
}
DERIVED = [
    REPO / "apps/web/data/derived/models.json",
    REPO / "apps/web/data/derived/pool.json",
    REPO / "apps/web-next/public/data/derived/models.json",
    REPO / "apps/web-next/public/data/derived/pool.json",
]


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_catalog_is_well_formed():
    catalog = _catalog()
    assert isinstance(catalog["version"], int)
    modalities = set(catalog["modalities"])
    ids = [row["id"] for row in catalog["intents"]]
    assert len(ids) == len(set(ids))
    by_id = {row["id"]: row for row in catalog["intents"]}
    fallback = catalog["fallbackIntent"]
    assert by_id[fallback]["storable"] is True
    assert by_id[fallback]["modality"] == "text"
    for row in catalog["intents"]:
        assert ROW_FIELDS <= set(row)
        assert KEBAB.match(row["id"])
        assert row["modality"] in modalities
        assert isinstance(row["storable"], bool)
        assert isinstance(row["name"], str) and isinstance(row["glyph"], str)
        assert isinstance(row["desc"], str)
        metric = row["metric"]
        assert isinstance(metric["field"], str) and isinstance(metric["unit"], str)
        assert isinstance(metric["label"], str)
        assert isinstance(metric["higherIsBetter"], bool)
        assert isinstance(row["forbiddenFields"], list)
        if row["classify"] is not None:
            re.compile(row["classify"])
    assert by_id["music"]["modality"] == "audio"
    assert by_id["image-to-3d"]["modality"] == "3d"
    assert by_id["vision"]["storable"] is False


def _cells(document):
    if isinstance(document, dict):
        cells = document.get("cells")
        if isinstance(cells, list):
            yield from cells
        for value in document.values():
            yield from _cells(value)
    elif isinstance(document, list):
        for item in document:
            yield from _cells(item)


def _model_categories(document):
    if isinstance(document, dict):
        models = document.get("models")
        if isinstance(models, list):
            for model in models:
                category = model.get("category")
                if isinstance(category, str):
                    yield category
        for value in document.values():
            if value is not document.get("models"):
                yield from _model_categories(value)
    elif isinstance(document, list):
        for item in document:
            yield from _model_categories(item)


def test_derived_json_stays_inside_the_catalog():
    catalog = _catalog()
    by_id = {row["id"]: row for row in catalog["intents"]}
    storable = {row["id"] for row in catalog["intents"] if row["storable"]}
    seen = set()
    for path in DERIVED:
        document = json.loads(path.read_text(encoding="utf-8"))
        for category in _model_categories(document):
            assert category in storable, f"{path} model category {category}"
            seen.add(category)
        for cell in _cells(document):
            if not isinstance(cell, dict):
                continue
            category = cell.get("category")
            if not isinstance(category, str):
                continue
            assert category in storable, f"{path} cell category {category}"
            seen.add(category)
            row = by_id[category]
            for field in row["forbiddenFields"]:
                assert cell.get(field) is None, f"{path} {category} carries {field}"
    for category in seen:
        assert by_id[category]["metric"]["higherIsBetter"] is True, category
    assert "music" not in seen
    assert "image-to-3d" not in seen


def test_web_next_does_not_restate_intent_rows():
    catalog = _catalog()
    home = (REPO / "apps/web-next/app/home-client.tsx").read_text(encoding="utf-8")
    engine = (REPO / "apps/web-next/lib/engine.ts").read_text(encoding="utf-8")
    assert 'from "@/lib/intents"' in home
    assert 'from "./intents"' in engine
    for row in catalog["intents"]:
        assert f'id: "{row["id"]}"' not in home
        assert f"id: '{row['id']}'" not in home
        if row["modality"] != "text":
            assert row["metric"]["unit"] not in engine


def test_pool_backend_suite_runs():
    uv = shutil.which("uv")
    assert uv, "uv is required to run the pool-backend intent catalog suite"
    proc = subprocess.run(
        [
            uv,
            "run",
            "--project",
            str(REPO / "apps/pool-backend"),
            "pytest",
            "-q",
            "tests/test_intent_catalog.py",
        ],
        cwd=REPO / "apps/pool-backend",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
