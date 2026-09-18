"""Music intent nested under the audio modality.

Honesty: fixture numbers are labeled stubs (1.0). Classification uses names
only — never copies measured Modal cells into the pool.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_PY = ROOT / "apps/pool-backend/src/category.py"
FIXTURE = ROOT / "tests/fixtures/music_audio_intent.json"


def _load_category():
    spec = importlib.util.spec_from_file_location("pool_category", CATEGORY_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cat = _load_category()


def test_music_nests_under_audio_modality():
    assert cat.modality_of("music") == "audio"
    assert cat.modality_of("audio") == "audio"
    assert cat.modality_of("chat") == "text"
    assert cat.modality_of("code") == "text"
    assert "music" in cat.AUDIO_MODALITY_CATEGORIES
    assert "audio" in cat.AUDIO_MODALITY_CATEGORIES
    assert "chat" not in cat.AUDIO_MODALITY_CATEGORIES


@pytest.mark.parametrize(
    ("display", "hf_id", "expected"),
    [
        ("MusicGen Small", "facebook/musicgen-small", "music"),
        ("MusicGen Medium", "facebook/musicgen-medium", "music"),
        ("MAGNeT small", "facebook/magnet-small-10secs", "music"),
        ("JASCO 400M", "facebook/jasco-chords-drums-400M", "music"),
        ("ACE-Step 1.5", "ACE-Step/ACE-Step-1.5", "music"),
        ("ACEStep XL", "acestep/acestep-xl", "music"),
        ("YuE2 3B", "map/YuE2-3B", "music"),
        ("DiffRhythm full", "ASLP-lab/DiffRhythm-1.2", "music"),
        ("Stable Audio Open", "stabilityai/stable-audio-open-1.0", "music"),
        ("Whisper Large v3", "openai/whisper-large-v3", "audio"),
        ("Faster Whisper", "Systran/faster-whisper-large-v3", "audio"),
        ("AudioGen", "facebook/audiogen-medium", "audio"),
        ("Qwen2.5 Coder 7B", "unsloth/Qwen2.5-Coder-7B-Instruct-GGUF", "code"),
        ("Llama 3.1 8B Instruct", "unsloth/Llama-3.1-8B-Instruct-GGUF", "chat"),
    ],
)
def test_model_category_classifies_music_audio_code_chat(display, hf_id, expected):
    assert cat.model_category(display, hf_id) == expected


def test_whisper_is_not_music_or_llm():
    assert cat.model_category("Whisper Large v3", "openai/whisper-large-v3") == "audio"
    assert cat.model_category("whisper-large-v3") != "music"
    assert cat.model_category("whisper-large-v3") not in ("chat", "code")


def test_musicgen_is_not_chat_or_code_or_audio_stt():
    assert cat.model_category("facebook/musicgen-small") == "music"
    assert cat.model_category("", "facebook/musicgen-small") != "audio"


def test_category_filter_accepts_music_and_audio():
    assert cat.validate_category_filter("music") == "music"
    assert cat.validate_category_filter("audio") == "audio"
    assert cat.validate_category_filter("chat") == "chat"
    assert cat.validate_category_filter(None) is None
    with pytest.raises(ValueError, match="invalid category"):
        cat.validate_category_filter("not-an-intent")


def test_sqlite_check_accepts_music_and_audio_rejects_garbage():
    conn = sqlite3.connect(":memory:")
    check = cat.category_check_sql()
    conn.execute(
        f"""CREATE TABLE lm_model(
          slug TEXT PRIMARY KEY,
          category TEXT NOT NULL CHECK(category IN {check}))"""
    )
    conn.execute("INSERT INTO lm_model VALUES ('facebook-musicgen-small', 'music')")
    conn.execute("INSERT INTO lm_model VALUES ('whisper-large-v3', 'audio')")
    conn.execute("INSERT INTO lm_model VALUES ('llama-3-1-8b', 'chat')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO lm_model VALUES ('bogus', 'podcast')")
    rows = {
        slug: category
        for slug, category in conn.execute("SELECT slug, category FROM lm_model")
    }
    assert rows["facebook-musicgen-small"] == "music"
    assert rows["whisper-large-v3"] == "audio"
    conn.close()


def test_sqlite_rebuild_widens_legacy_chat_code_check():
    """Existing DBs used CHECK (chat, code); rebuild must accept music/audio."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE lm_model(
          slug TEXT PRIMARY KEY, hf_id TEXT NOT NULL, display_name TEXT NOT NULL,
          family TEXT, params_b REAL, active_params_b REAL,
          is_moe INTEGER NOT NULL DEFAULT 0,
          category TEXT NOT NULL CHECK(category IN ('chat','code')),
          eval_score REAL, raw_json TEXT NOT NULL)"""
    )
    conn.execute(
        "INSERT INTO lm_model VALUES ('llama','meta/llama','Llama',NULL,NULL,NULL,0,'chat',NULL,'{}')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO lm_model VALUES ('mg','facebook/musicgen-small','MusicGen',"
            "NULL,NULL,NULL,0,'music',NULL,'{}')"
        )
    check = cat.category_check_sql()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        f"""CREATE TABLE lm_model_new(
          slug TEXT PRIMARY KEY, hf_id TEXT NOT NULL, display_name TEXT NOT NULL,
          family TEXT, params_b REAL, active_params_b REAL,
          is_moe INTEGER NOT NULL DEFAULT 0,
          category TEXT NOT NULL CHECK(category IN {check}),
          eval_score REAL, raw_json TEXT NOT NULL)"""
    )
    conn.execute("INSERT INTO lm_model_new SELECT * FROM lm_model")
    conn.execute("DROP TABLE lm_model")
    conn.execute("ALTER TABLE lm_model_new RENAME TO lm_model")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO lm_model VALUES ('mg','facebook/musicgen-small','MusicGen',"
        "NULL,NULL,NULL,0,'music',NULL,'{}')"
    )
    conn.execute(
        "INSERT INTO lm_model VALUES ('wh','openai/whisper-large-v3','Whisper',"
        "NULL,NULL,NULL,0,'audio',NULL,'{}')"
    )
    rows = dict(conn.execute("SELECT slug, category FROM lm_model"))
    assert rows["mg"] == "music"
    assert rows["wh"] == "audio"
    assert rows["llama"] == "chat"
    conn.close()


def test_fixture_shows_music_cell_distinct_from_whisper_audio():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["sourceClass"] == "fixture_stub"
    by_slug = {model["slug"]: model for model in payload["models"]}
    whisper = by_slug["whisper-large-v3"]
    musicgen = by_slug["facebook-musicgen-small"]
    assert whisper["category"] == "audio"
    assert whisper["modality"] == "audio"
    assert musicgen["category"] == "music"
    assert musicgen["modality"] == "audio"
    assert musicgen["category"] != whisper["category"]

    cells = {cell["modelSlug"]: cell for cell in payload["cells"]}
    audio_cell = cells["whisper-large-v3"]
    music_cell = cells["facebook-musicgen-small"]
    assert audio_cell["category"] == "audio"
    assert music_cell["category"] == "music"
    assert "tokSOutMedian" not in audio_cell
    assert "tokSOutMedian" not in music_cell
    assert "decode_tok_s" not in music_cell
    assert audio_cell.get("audioXReal") is not None
    assert music_cell.get("rtf") is not None
    assert music_cell.get("peakVramGb") is not None
    for row in payload["models"] + payload["cells"]:
        assert row["sourceClass"] == "fixture_stub"
