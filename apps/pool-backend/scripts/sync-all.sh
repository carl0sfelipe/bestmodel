#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

start=$(date +%s)

uv run python -m src.sync_pool
uv run python -m src.plausibility
uv run python -m src.derive_export --publish

end=$(date +%s)

DURATION_S=$((end - start)) uv run python - <<'PY'
import os
import src.db

conn = src.db.connect()
try:
    runs = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
    counts = {v: 0 for v in ("ok", "suspicious", "impossible", "exempt")}
    for verdict, n in conn.execute(
        "SELECT verdict, COUNT(*) FROM plausibility_flag GROUP BY verdict"
    ):
        counts[verdict] = n
finally:
    conn.close()

published = sorted(name for name in os.listdir("out/derived") if name.endswith(".json"))
flags = ", ".join(f"{v}={counts[v]}" for v in ("ok", "suspicious", "impossible", "exempt"))
print(f"runs: {runs}")
print(f"flags: {flags}")
print(f"published: {', '.join(published)}")
print(f"duration: {os.environ['DURATION_S']}s")
PY
