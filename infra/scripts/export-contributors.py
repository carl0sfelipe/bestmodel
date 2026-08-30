#!/usr/bin/env python3
"""S27 — export per-contributor para o The Lineup (contrato congelado na
S13 do llms.surf). DATABASE_URL -> data/contributor-export.json.

Fail loud: sem DATABASE_URL, endpoint inacessível ou fetch quebrado = exit
não-zero. O JSON na main do bestmodel É a fonte que o workflow lineup do
llms.surf consome — escrever à mão aqui é fraude de fonte.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("export-contributors: DATABASE_URL ausente — fail loud (S27)", file=sys.stderr)
        return 1
    sys.path.insert(0, str(REPO / "apps" / "public-api" / "src" / "dependencies"))
    sys.path.insert(0, str(REPO / "apps" / "public-api" / "src"))
    import psycopg
    from psycopg.rows import dict_row

    from database_session_provider import PostgresSession

    session = PostgresSession(psycopg.connect(dsn, row_factory=dict_row))
    try:
        rows = session.fetch_contributor_points()
    except Exception as exc:  # noqa: BLE001 — fail loud com motivo
        print(f"export-contributors: fetch falhou: {exc}", file=sys.stderr)
        return 1

    # E6-4.5: timeline ADDITIVE (bloco separado; as linhas de contributors
    # mantêm o contrato congelado da S27). Consumida pelo dial
    # referral_conversion do The Lineup.
    timeline = session.fetch_contributor_timeline()

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "S27 fetch_contributor_points (validated signed runs x 2)",
        "contributors": rows,
        "timeline": timeline,
    }
    out = REPO / "data" / "contributor-export.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"export-contributors: {len(rows)} contribuidor(es) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
