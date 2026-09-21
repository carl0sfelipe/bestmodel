"""S37: the intent catalog is the only category list.

A fixture row added only to a temporary catalog must reach the SQLite CHECK,
the API filter and the classifier. The committed catalog must not grow a
measurement.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "packages" / "intent-catalog" / "catalog.json"
CONTRACT = Path(__file__).resolve().parents[1] / "CONTRATO-GLOBAL.md"

CASES = [
    ("MusicGen", "", "music"),
    ("MAGNeT", "", "music"),
    ("ACE-Step", "", "music"),
    ("YuE", "", "music"),
    ("DiffRhythm", "", "music"),
    ("Stable Audio", "", "music"),
    ("Whisper Large v3", "", "audio"),
    ("faster-whisper", "", "audio"),
    ("AudioGen", "", "audio"),
    ("Qwen2.5-Coder", "", "code"),
    ("Codestral", "", "code"),
    ("Llama-3-8B", "", "chat"),
]

# The CHECK this story replaces. Kept here as the legacy database shape, not
# as a live allowlist.
_LEGACY_DDL = """
CREATE TABLE lm_model(
  slug TEXT PRIMARY KEY, hf_id TEXT NOT NULL, display_name TEXT NOT NULL,
  family TEXT, params_b REAL, active_params_b REAL,
  is_moe INTEGER NOT NULL DEFAULT 0,
  category TEXT NOT NULL CHECK(category IN ('chat','code')),
  eval_score REAL, raw_json TEXT NOT NULL);
CREATE TABLE lm_rig(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, hw_class TEXT NOT NULL,
  mem_gb REAL, gpu_count INTEGER NOT NULL DEFAULT 1,
  bandwidth_gbs REAL, run_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE lm_run(
  id TEXT PRIMARY KEY,
  model_slug TEXT NOT NULL REFERENCES lm_model(slug),
  rig_key TEXT NOT NULL REFERENCES lm_rig(key),
  bits INTEGER, quant TEXT, engine TEXT,
  tok_s_out REAL NOT NULL, tok_s_prefill REAL, ttft_ms REAL,
  peak_vram_gb REAL, context_length INTEGER, batch_size INTEGER,
  spec_decoding INTEGER NOT NULL DEFAULT 0,
  mtp_enabled INTEGER NOT NULL DEFAULT 0,
  concurrency INTEGER, created_at TEXT NOT NULL, raw_json TEXT NOT NULL);
"""

_FIXTURE_ROW = {
    "id": "zz-fixture",
    "name": "Fixture",
    "glyph": "?",
    "desc": "fixture_stub",
    "modality": "video",
    "storable": True,
    "metric": {
        "field": "zzPerSec",
        "unit": "zz/s",
        "label": "fixture",
        "higherIsBetter": True,
    },
    "forbiddenFields": ["tokSOutMedian"],
    "classify": "zz-fixture-model",
    "sourceClass": "fixture_stub",
    "placeholder": 1.0,
}


def _node_view(env: dict) -> dict:
    script = """
import { classifyModel, STORABLE_CATEGORIES } from "./apps/web/scripts/intent-catalog.mjs";
const cases = JSON.parse(process.env.CASES);
console.log(JSON.stringify({
  classes: cases.map(([display, hfId]) => classifyModel(display, hfId)),
  storable: STORABLE_CATEGORIES(),
}));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_real_catalog_contract_and_api(tmp_path, monkeypatch):
    monkeypatch.delenv("BESTMODEL_INTENT_CATALOG", raising=False)
    monkeypatch.setenv("BESTMODEL_POOL_DB", str(tmp_path / "pool.sqlite3"))
    from src.db import connect, migrate
    from src.intents import category_check_sql, classify

    conn = connect()
    migrate(conn)
    conn.close()
    client = TestClient(__import__("src.main", fromlist=["app"]).app)
    for category in ("music", "image-to-3d"):
        response = client.get("/v1/models", params={"category": category})
        assert response.status_code == 200
        assert response.json() == {"models": []}
    for category in ("vision", "nope"):
        response = client.get("/v1/models", params={"category": category})
        assert response.status_code == 422
    check = category_check_sql()
    assert check in CONTRACT.read_text(encoding="utf-8"), check
    assert [classify(display, hf_id) for display, hf_id, _expected in CASES] == [
        expected for _display, _hf_id, expected in CASES
    ]


def test_fixture_row_reaches_check_api_and_node(tmp_path, monkeypatch):
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["intents"].append(_FIXTURE_ROW)
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setenv("BESTMODEL_INTENT_CATALOG", str(catalog_path))
    monkeypatch.setenv("BESTMODEL_POOL_DB", str(tmp_path / "pool.sqlite3"))

    from src.db import connect, migrate
    from src.intents import category_check_sql, classify
    from src.main import app

    assert "'zz-fixture'" in category_check_sql()
    assert classify("ZZ-Fixture-Model 7B", "x/y") == "zz-fixture"
    conn = connect()
    migrate(conn)
    conn.execute(
        """INSERT INTO lm_model
           (slug, hf_id, display_name, is_moe, category, raw_json)
           VALUES ('zz', 'x/zz', 'ZZ', 0, 'zz-fixture', '{}')"""
    )
    conn.commit()
    conn.close()
    client = TestClient(app)
    ok = client.get("/v1/models", params={"category": "zz-fixture"})
    assert ok.status_code == 200
    assert ok.json() == {"models": []}
    assert client.get("/v1/models", params={"category": "nope"}).status_code == 422

    env = os.environ.copy()
    env["BESTMODEL_INTENT_CATALOG"] = str(catalog_path)
    env["CASES"] = json.dumps([["ZZ-Fixture-Model 7B", "x/y"]])
    view = _node_view(env)
    assert view["classes"] == ["zz-fixture"]
    assert "zz-fixture" in view["storable"]


def test_fixture_id_is_absent_without_override(monkeypatch):
    monkeypatch.delenv("BESTMODEL_INTENT_CATALOG", raising=False)
    from src.intents import category_check_sql, classify, storable_categories

    assert "zz-fixture" not in storable_categories()
    assert "zz-fixture" not in category_check_sql()
    assert classify("ZZ-Fixture-Model 7B", "x/y") != "zz-fixture"
    env = os.environ.copy()
    env.pop("BESTMODEL_INTENT_CATALOG", None)
    env["CASES"] = json.dumps([[display, hf_id] for display, hf_id, _expected in CASES])
    view = _node_view(env)
    assert view["classes"] == [expected for _display, _hf_id, expected in CASES]
    assert view["storable"] == list(storable_categories())


def test_legacy_check_rebuilds_once(tmp_path, monkeypatch):
    monkeypatch.delenv("BESTMODEL_INTENT_CATALOG", raising=False)
    db_path = tmp_path / "legacy.sqlite3"
    raw = sqlite3.connect(db_path)
    raw.executescript(_LEGACY_DDL)
    raw.execute(
        """INSERT INTO lm_model (slug, hf_id, display_name, is_moe, category, raw_json)
           VALUES ('llama', 'meta/llama', 'Llama', 0, 'chat', '{}')"""
    )
    raw.execute(
        """INSERT INTO lm_rig (key, label, hw_class, mem_gb, gpu_count)
           VALUES ('rtx-3090', 'RTX 3090', 'DISCRETE_GPU', 24, 1)"""
    )
    raw.execute(
        """INSERT INTO lm_run
           (id, model_slug, rig_key, tok_s_out, spec_decoding, mtp_enabled, created_at, raw_json)
           VALUES ('run-1', 'llama', 'rtx-3090', 1.0, 0, 0, '2026-09-21T00:00:00Z', '{"sourceClass":"fixture_stub"}')"""
    )
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute(
            """INSERT INTO lm_model (slug, hf_id, display_name, is_moe, category, raw_json)
               VALUES ('mg', 'x/musicgen', 'MusicGen', 0, 'music', '{}')"""
        )
    raw.commit()
    raw.close()

    import src.db as dbmod

    rebuilds = {"n": 0}
    original = dbmod._rebuild_lm_model

    def _count(conn):
        rebuilds["n"] += 1
        return original(conn)

    monkeypatch.setattr(dbmod, "_rebuild_lm_model", _count)
    conn = dbmod.connect(str(db_path))
    dbmod.migrate(conn)
    assert rebuilds["n"] == 1
    conn.execute(
        """INSERT INTO lm_model (slug, hf_id, display_name, is_moe, category, raw_json)
           VALUES ('mg', 'x/musicgen', 'MusicGen', 0, 'music', '{}')"""
    )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    dbmod.migrate(conn)
    assert rebuilds["n"] == 1
    conn.close()
