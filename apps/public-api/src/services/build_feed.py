"""Feed assembly (S17): followed accounts first, global fallback.

Items are typed so the console can render one list:

- ``claim``        — a run claim with its live vote tally
- ``verified_run`` — a validated, account-attributed benchmark run

``scope=following`` shows only followed accounts (empty graph -> empty feed);
``scope=global`` ignores the graph. ``sort=trending`` ranks claims by community
activity inside the item ordering key; ``sort=recent`` (default) is pure time.
"""

from __future__ import annotations

from src.dependencies.database_session_provider import DatabaseSession
from src.services.compute_vote_tally import tally as compute_tally


def build_feed(
    session: DatabaseSession,
    viewer: dict | None,
    scope: str = "following",
    sort: str = "recent",
    limit: int = 30,
) -> list[dict]:
    followee_ids = session.list_followee_ids(viewer["id"]) if viewer else []
    if scope == "following" and not followee_ids:
        return []

    user_ids = followee_ids if scope == "following" else None  # None => global
    items: list[dict] = []
    items.extend(_claim_items(session, user_ids))
    items.extend(_run_items(session, user_ids))

    if sort == "trending":
        items.sort(key=lambda item: item["_sort_key"], reverse=True)
    else:
        items.sort(key=lambda item: item["_created"], reverse=True)

    for item in items:
        item.pop("_sort_key", None)
        item.pop("_created", None)
    return items[:limit]


def _claim_items(session: DatabaseSession, user_ids: list[str] | None) -> list[dict]:
    claims = session.list_recent_claims_by_users(user_ids, 100)
    items = []
    for claim in claims:
        t = compute_tally(session.fetch_votes_for_claim(claim["id"]))
        created = str(claim.get("created_at"))
        activity = abs(t["margin"]) + t["voter_count"]
        items.append(
            {
                "type": "claim",
                "id": claim["id"],
                "handle": claim.get("claimant_handle"),
                "status": claim["status"],
                "model_release_id": claim["model_release_id"],
                "claimed_metrics": claim["claimed_metrics"],
                "tally": t,
                "created_at": claim.get("created_at"),
                "_created": created,
                "_sort_key": f"{created}|{activity:08.2f}",
            }
        )
    return items


def _run_items(session: DatabaseSession, user_ids: list[str] | None) -> list[dict]:
    runs = session.list_recent_validated_runs_by_owners(user_ids, 100)
    return [
        {
            "type": "verified_run",
            "run_id": run["run_id"],
            "model_release_id": run["model_release_id"],
            "decode_tok_s": run.get("decode_tok_s"),
            "submitted_at": run["submitted_at"],
            "_created": str(run["submitted_at"]),
            "_sort_key": str(run["submitted_at"]),
        }
        for run in runs
    ]
