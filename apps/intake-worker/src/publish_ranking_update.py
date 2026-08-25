"""Publishes a ranking update event once validation finishes (plan section 11).

The full leaderboard re-ranking belongs to S11; this module only emits the
notification carrying the run id, its final status and trust score.
"""

from __future__ import annotations

RANKING_UPDATE_EVENT = "benchmark_run.ranking_update"


def publish_ranking_update(repository, run_id: str, status: str, trust_score: float) -> None:
    repository.publish_ranking_update(
        {
            "event": RANKING_UPDATE_EVENT,
            "run_id": run_id,
            "status": status,
            "trust_score": trust_score,
        }
    )
