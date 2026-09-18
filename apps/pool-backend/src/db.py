"""SQLite connection and schema migration for the localmaxxing pool.

DDL is the literal contract §4; identity and data rules live in the
consumers (sync_pool, plausibility, derive_export).
"""

import os
import sqlite3

from src.category import category_check_sql
from src.config import DB_PATH

_CATEGORY_CHECK = category_check_sql()


def _lm_model_ddl(table: str = "lm_model", if_not_exists: bool = True) -> str:
    exists = "IF NOT EXISTS " if if_not_exists else ""
    return f"""CREATE TABLE {exists}{table}(
  slug TEXT PRIMARY KEY, hf_id TEXT NOT NULL, display_name TEXT NOT NULL,
  family TEXT, params_b REAL, active_params_b REAL,
  is_moe INTEGER NOT NULL DEFAULT 0,
  category TEXT NOT NULL CHECK(category IN {_CATEGORY_CHECK}),
  eval_score REAL, raw_json TEXT NOT NULL)"""


DDL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS sync_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
    _lm_model_ddl(),
    """CREATE TABLE IF NOT EXISTS lm_rig(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, hw_class TEXT NOT NULL,
  mem_gb REAL, gpu_count INTEGER NOT NULL DEFAULT 1,
  bandwidth_gbs REAL, run_count INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS lm_run(
  id TEXT PRIMARY KEY,
  model_slug TEXT NOT NULL REFERENCES lm_model(slug),
  rig_key TEXT NOT NULL REFERENCES lm_rig(key),
  bits INTEGER, quant TEXT, engine TEXT,
  tok_s_out REAL NOT NULL, tok_s_prefill REAL, ttft_ms REAL,
  peak_vram_gb REAL, context_length INTEGER, batch_size INTEGER,
  spec_decoding INTEGER NOT NULL DEFAULT 0,
  mtp_enabled INTEGER NOT NULL DEFAULT 0,
  concurrency INTEGER, created_at TEXT NOT NULL, raw_json TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS plausibility_flag(
  run_id TEXT PRIMARY KEY REFERENCES lm_run(id),
  ceiling_tok_s REAL NOT NULL, ratio REAL NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('ok','suspicious','impossible','exempt')),
  reason TEXT NOT NULL, computed_at TEXT NOT NULL)""",
]


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open the SQLite database, creating its directory and enabling FKs."""
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply the contract §4 DDL; widen category CHECK on existing DBs."""
    for statement in DDL_STATEMENTS:
        conn.execute(statement)
    _ensure_category_check(conn)
    conn.commit()


def _ensure_category_check(conn: sqlite3.Connection) -> None:
    """SQLite cannot ALTER a CHECK; rebuild lm_model when 'music' is missing."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'lm_model'"
    ).fetchone()
    if row is None:
        return
    sql = row[0] or ""
    if "'music'" in sql and "'audio'" in sql:
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(_lm_model_ddl("lm_model_new", if_not_exists=False))
    conn.execute("INSERT INTO lm_model_new SELECT * FROM lm_model")
    conn.execute("DROP TABLE lm_model")
    conn.execute("ALTER TABLE lm_model_new RENAME TO lm_model")
    conn.execute("PRAGMA foreign_keys = ON")
