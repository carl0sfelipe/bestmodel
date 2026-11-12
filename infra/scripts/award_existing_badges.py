#!/usr/bin/env python3
"""Grant the badges that already happened.

The badges are granted when an act is recorded, but the acts that happened
before the wiring existed are still real: a run on your machine that was
validated is a validated run on your machine today.

This script reads the runs that are already validated and grants the badge
their owner earned. It is idempotent — the badge table is unique per
(account, code), so running it twice grants nothing twice — and it grants
nothing that the pool does not record.

    python infra/scripts/award_existing_badges.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "public-api"))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from src.dependencies.database_session_provider import PostgresSession  # noqa: E402

BADGE_FIRST_VERIFIED_RUN = "first_verified_run"

AWARDED_SQL = """
SELECT r.id::text AS run_id, h.owner_account_id::text AS owner_id
FROM benchmark_run r
JOIN hardware_submission h ON h.id = r.hardware_submission_id
JOIN app_user u ON u.id = h.owner_account_id
WHERE r.status = 'validated'
"""

HELD_SQL = """
SELECT app_user_id::text AS owner_id, code
FROM badge
WHERE code = %s
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="say what would be granted")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    connection = psycopg.connect(database_url, row_factory=dict_row)
    session = PostgresSession(connection)
    rows = session._fetchall(AWARDED_SQL)
    held = {
        (row["owner_id"], row["code"])
        for row in session._fetchall(HELD_SQL, (BADGE_FIRST_VERIFIED_RUN,))
    }

    granted = 0
    for row in rows:
        key = (row["owner_id"], BADGE_FIRST_VERIFIED_RUN)
        if key in held:
            continue
        granted += 1
        print(f"would grant {BADGE_FIRST_VERIFIED_RUN} to {row['owner_id']} (run {row['run_id']})")
        if not args.dry_run:
            session.insert_badge(
                {
                    "id": str(uuid.uuid4()),
                    "app_user_id": row["owner_id"],
                    "code": BADGE_FIRST_VERIFIED_RUN,
                }
            )

    session.commit()
    verb = "would grant" if args.dry_run else "granted"
    print(f"{verb} {granted} badge(s) across {len(rows)} validated run(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
