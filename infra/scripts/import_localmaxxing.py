#!/usr/bin/env python3
"""Import localmaxxing.com community-pool cells as run_claims (S22).

Usage:
    uv run python infra/scripts/import_localmaxxing.py --dry-run
    uv run python infra/scripts/import_localmaxxing.py --apply
    uv run python infra/scripts/import_localmaxxing.py --apply --source /tmp/pool.json

Reads the aggregated pool snapshot (apps/web/data/derived/pool.json by
default — regenerate with `bash apps/pool-backend/scripts/sync-all.sh` for
fresh data), maps cells onto our catalog and inserts owner-approved,
unverified claims. Idempotent per external ref.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SRC = REPO_ROOT / "apps" / "public-api"
for candidate in (str(API_SRC), str(REPO_ROOT / "packages" / "fake-adapters" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

DEFAULT_SOURCE = REPO_ROOT / "apps" / "web" / "data" / "derived" / "pool.json"
DEFAULT_DATABASE_URL = "postgresql://bestmodel:bestmodel@localhost:5434/bestmodel"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only, never write")
    mode.add_argument("--apply", action="store_true", help="insert missing claims")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not args.source.exists():
        print(f"source not found: {args.source}", file=sys.stderr)
        return 1
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    cells = payload["cells"] if isinstance(payload, dict) else payload
    print(f"loaded {len(cells)} cells from {args.source}")

    from src.dependencies.database_session_provider import PostgresSession
    from src.services.import_localmaxxing_claims import import_cells

    dsn = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    connection = psycopg.connect(dsn, row_factory=dict_row)
    session = PostgresSession(connection)
    try:
        stats = import_cells(session, cells, dry_run=args.dry_run, limit=args.limit)
    finally:
        session.close()

    print(json.dumps(stats, indent=2))
    print()
    print(
        f"{'would import' if args.dry_run else 'imported'}: {stats['imported']} · "
        f"already present: {stats['existing']} · "
        f"skipped: nomodel={stats['nomodel']} nometrics={stats['nometrics']} "
        f"multigpu={stats['multigpu-v1']}"
    )
    if stats["unmapped_models"]:
        print("\ntop unmapped models (catalog-expansion backlog):")
        for slug, count in list(stats["unmapped_models"].items())[:10]:
            print(f"  {count:3d}× {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
