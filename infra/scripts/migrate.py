#!/usr/bin/env python3
"""Apply pending SQL migrations in lexicographic order.

Each migration file contains its own BEGIN;/COMMIT; and is executed directly.
Applied filenames are recorded in schema meta.schema_migrations so that
repeated runs are idempotent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://bestmodel:bestmodel@localhost:5434/bestmodel",
)


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(f"migrations directory not found: {MIGRATIONS_DIR}", file=sys.stderr)
        return 1

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("no migration files found", file=sys.stderr)
        return 1

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS meta")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS meta.schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM meta.schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        pending = [f for f in migration_files if f.name not in applied]
        if not pending:
            print("no pending migrations; all already applied")
            return 0

        for migration in pending:
            with conn.cursor() as cur:
                cur.execute(migration.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO meta.schema_migrations (filename) VALUES (%s)",
                    (migration.name,),
                )
            print(f"applied {migration.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
