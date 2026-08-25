"""Roofline plausibility curation: recompute every run's decode ceiling and
store the verdict. Flags are derived data, so the whole table is recomputed
(DELETE + INSERT in one transaction) to avoid stale state.

Executable via `uv run python -m src.plausibility`. Reads lm_run joined with
its model and rig; never deletes or alters lm_run rows.
"""

import sqlite3
from datetime import datetime, timezone

from src.config import DB_PATH, IMPOSSIBLE_FRACTION, SUSPICIOUS_FRACTION
from src.db import connect, migrate

REASON_RATIO = "ratio_vs_ceiling"
REASON_SPEC_DECODING = "spec_decoding"
REASON_MTP_ENABLED = "mtp_enabled"
REASON_BATCH_GT_1 = "batch_gt_1"
REASON_CONCURRENCY_GT_1 = "concurrency_gt_1"
REASON_MISSING_INPUTS = "missing_inputs"

RUN_JOIN_SQL = """
    SELECT r.id AS run_id, r.tok_s_out, r.bits, r.batch_size,
           r.spec_decoding, r.mtp_enabled, r.concurrency,
           m.params_b, m.active_params_b, m.is_moe, g.bandwidth_gbs
    FROM lm_run r
    JOIN lm_model m ON m.slug = r.model_slug
    JOIN lm_rig g ON g.key = r.rig_key
"""


def effective_params_b(row: sqlite3.Row) -> float | None:
    """Active weights in GB read per token: active_params_b for MoE, else params_b."""
    if row["is_moe"]:
        return row["active_params_b"]
    return row["params_b"]


def exemption_reason(row: sqlite3.Row) -> str | None:
    """First §6 exemption that applies, else None (ratio path)."""
    if row["spec_decoding"]:
        return REASON_SPEC_DECODING
    if row["mtp_enabled"]:
        return REASON_MTP_ENABLED
    if (row["batch_size"] or 0) > 1:
        return REASON_BATCH_GT_1
    if (row["concurrency"] or 0) > 1:
        return REASON_CONCURRENCY_GT_1
    params = effective_params_b(row)
    if row["bandwidth_gbs"] is None or row["bits"] is None or params is None or params <= 0:
        return REASON_MISSING_INPUTS
    return None


def verdict_for(ratio: float) -> str:
    if ratio > IMPOSSIBLE_FRACTION:
        return "impossible"
    if ratio > SUSPICIOUS_FRACTION:
        return "suspicious"
    return "ok"


def compute_flag(row: sqlite3.Row) -> dict:
    """ceiling/ratio/verdict for one run; exempt rows carry 0.0 sentinels."""
    reason = exemption_reason(row)
    if reason is not None:
        return {"ceiling_tok_s": 0.0, "ratio": 0.0, "verdict": "exempt", "reason": reason}
    params = effective_params_b(row)
    ceiling = row["bandwidth_gbs"] / (params * row["bits"] / 8)
    ratio = row["tok_s_out"] / ceiling
    return {
        "ceiling_tok_s": round(ceiling, 4),
        "ratio": round(ratio, 4),
        "verdict": verdict_for(ratio),
        "reason": REASON_RATIO,
    }


def recompute_flags(conn: sqlite3.Connection) -> int:
    """Rebuild plausibility_flag for every lm_run row in one transaction."""
    computed_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for row in conn.execute(RUN_JOIN_SQL):
        flag = compute_flag(row)
        rows.append(
            {
                "run_id": row["run_id"],
                "ceiling_tok_s": flag["ceiling_tok_s"],
                "ratio": flag["ratio"],
                "verdict": flag["verdict"],
                "reason": flag["reason"],
                "computed_at": computed_at,
            }
        )
    conn.execute("DELETE FROM plausibility_flag")
    conn.executemany(
        """INSERT INTO plausibility_flag
           (run_id, ceiling_tok_s, ratio, verdict, reason, computed_at)
           VALUES (:run_id, :ceiling_tok_s, :ratio, :verdict, :reason, :computed_at)""",
        rows,
    )
    conn.commit()
    return len(rows)


def summary(conn: sqlite3.Connection | None = None) -> dict:
    """Verdict counts + top 10 worst (impossible|suspicious) by ratio desc."""
    close_after = conn is None
    if conn is None:
        conn = connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
        counts = {verdict: 0 for verdict in ("ok", "suspicious", "impossible", "exempt")}
        for verdict, count in conn.execute(
            "SELECT verdict, COUNT(*) FROM plausibility_flag GROUP BY verdict"
        ):
            counts[verdict] = count
        worst = [
            {
                "runId": row["run_id"],
                "modelSlug": row["model_slug"],
                "rigKey": row["rig_key"],
                "ratio": row["ratio"],
            }
            for row in conn.execute(
                """SELECT p.run_id, r.model_slug, r.rig_key, p.ratio
                   FROM plausibility_flag p
                   JOIN lm_run r ON r.id = p.run_id
                   WHERE p.verdict IN ('impossible','suspicious')
                   ORDER BY p.ratio DESC
                   LIMIT 10"""
            )
        ]
        return {
            "total": total,
            "ok": counts["ok"],
            "suspicious": counts["suspicious"],
            "impossible": counts["impossible"],
            "exempt": counts["exempt"],
            "worst": worst,
        }
    finally:
        if close_after:
            conn.close()


def main() -> None:
    conn = connect()
    migrate(conn)
    count = recompute_flags(conn)
    conn.close()
    print(f"plausibility: {count} flags recomputed")


if __name__ == "__main__":
    main()
