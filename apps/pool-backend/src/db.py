"""SQLite connection and schema migration for the localmaxxing pool.

The lm_model category CHECK is built from the intent catalog at migrate time.
SQLite cannot ALTER a CHECK, so a stale CHECK rebuilds the table in place.
lm_run stays a text speed-test (tok_s_out NOT NULL).
"""

import os
import sqlite3

from src.config import resolve_db_path
from src.intents import category_check_sql

_SYNC_META = """CREATE TABLE IF NOT EXISTS sync_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)"""
_LM_RIG = """CREATE TABLE IF NOT EXISTS lm_rig(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, hw_class TEXT NOT NULL,
  mem_gb REAL, gpu_count INTEGER NOT NULL DEFAULT 1,
  bandwidth_gbs REAL, run_count INTEGER NOT NULL DEFAULT 0)"""
_LM_RUN = """CREATE TABLE IF NOT EXISTS lm_run(
  id TEXT PRIMARY KEY,
  model_slug TEXT NOT NULL REFERENCES lm_model(slug),
  rig_key TEXT NOT NULL REFERENCES lm_rig(key),
  bits INTEGER, quant TEXT, engine TEXT,
  tok_s_out REAL NOT NULL, tok_s_prefill REAL, ttft_ms REAL,
  peak_vram_gb REAL, context_length INTEGER, batch_size INTEGER,
  spec_decoding INTEGER NOT NULL DEFAULT 0,
  mtp_enabled INTEGER NOT NULL DEFAULT 0,
  concurrency INTEGER, created_at TEXT NOT NULL, raw_json TEXT NOT NULL)"""
_PLAUSIBILITY = """CREATE TABLE IF NOT EXISTS plausibility_flag(
  run_id TEXT PRIMARY KEY REFERENCES lm_run(id),
  ceiling_tok_s REAL NOT NULL, ratio REAL NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('ok','suspicious','impossible','exempt')),
  reason TEXT NOT NULL, computed_at TEXT NOT NULL)"""


def lm_model_ddl(table: str = "lm_model") -> str:
    """CREATE TABLE for lm_model. The CHECK string comes from the catalog."""
    return (
        f"CREATE TABLE {table}(\n"
        "  slug TEXT PRIMARY KEY, hf_id TEXT NOT NULL, display_name TEXT NOT NULL,\n"
        "  family TEXT, params_b REAL, active_params_b REAL,\n"
        "  is_moe INTEGER NOT NULL DEFAULT 0,\n"
        f"  category TEXT NOT NULL {category_check_sql()},\n"
        "  eval_score REAL, raw_json TEXT NOT NULL)"
    )


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open the SQLite database, creating its directory and enabling FKs."""
    path = db_path if db_path is not None else resolve_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _lm_model_sql(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'lm_model'"
    ).fetchone()
    if row is None:
        return None
    return row["sql"]


def _rebuild_lm_model(conn: sqlite3.Connection) -> None:
    """Swap lm_model for one whose CHECK matches the catalog. One transaction."""
    previous = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS lm_model_new")
        conn.execute("BEGIN")
        conn.execute(lm_model_ddl("lm_model_new"))
        conn.execute("INSERT INTO lm_model_new SELECT * FROM lm_model")
        conn.execute("DROP TABLE lm_model")
        conn.execute("ALTER TABLE lm_model_new RENAME TO lm_model")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON" if previous else "PRAGMA foreign_keys = OFF")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"foreign_key_check after lm_model rebuild: {violations!r}")


def _ensure_lm_model(conn: sqlite3.Connection) -> None:
    stored = _lm_model_sql(conn)
    check = category_check_sql()
    if stored is None:
        conn.execute(lm_model_ddl())
        return
    if check not in stored:
        _rebuild_lm_model(conn)


def migrate(conn: sqlite3.Connection) -> None:
    """Apply DDL. Rebuild lm_model when its stored CHECK is stale. Idempotent."""
    conn.execute(_SYNC_META)
    _ensure_lm_model(conn)
    conn.execute(_LM_RIG)
    conn.execute(_LM_RUN)
    conn.execute(_PLAUSIBILITY)
    conn.commit()
