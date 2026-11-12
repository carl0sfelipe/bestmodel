"""L08: the classic social layer — posts, comments, likes.

A post carries TEXT only. Numbers belong to claims: a post may reference a
claim, a rig or a model, and it never carries a measurement of its own. This
is the same honesty rule the rest of the platform runs on, and it is why the
service layer refuses to accept metrics in a post body.

Reads are public. Writes need a bearer token, and they are rate limited by
reputation tier exactly like claims and votes are.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError, hours_ago_iso, utcnow_iso


def _is_uuid(value: str) -> bool:
    """Whether the id can be a row id at all.

    The ids are uuids. A string that cannot be one would make the database
    raise (invalid input syntax for type uuid) and answer 500 for what is
    simply a link that points at nothing.
    """
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True

POST_KINDS = ("note", "question", "showcase")
MAX_POST_BODY = 2000
MAX_COMMENT_BODY = 1000


# --------------------------------------------------------------------- posts


def create_post(
    session: DatabaseSession,
    caller: dict,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from src.services.rate_limit_policy import post_limit

    body = (payload.get("body") or "").strip()
    if not body:
        raise AuthError(400, "body is required")
    if len(body) > MAX_POST_BODY:
        raise AuthError(400, f"body must be at most {MAX_POST_BODY} characters")

    kind = payload.get("kind") or "note"
    if kind not in POST_KINDS:
        raise AuthError(400, f"kind must be one of {', '.join(POST_KINDS)}")

    # A post may quote a number only by pointing at the claim that carries it.
    for forbidden in ("claimed_metrics", "decode_tok_s", "metrics"):
        if forbidden in payload:
            raise AuthError(
                400,
                "a post carries text, not numbers — put the measurement in a claim and link it",
            )

    reputation = session.fetch_reputation_by_user(caller["id"])
    tier = reputation["tier"] if reputation else "L0"
    used = session.count_posts_since(caller["id"], hours_ago_iso(24))
    if used >= post_limit(tier):
        raise AuthError(
            429,
            f"post limit reached ({post_limit(tier)} per 24h at {tier}); "
            "verified runs raise your ceiling",
        )

    claim_id = payload.get("claim_id")
    if claim_id is not None:
        if not _is_uuid(claim_id):
            raise AuthError(404, f"unknown claim_id: {claim_id}")
        claim = session.find_run_claim_by_id(claim_id)
        if claim is None:
            raise AuthError(404, f"unknown claim_id: {claim_id}")

    rig_slug = payload.get("rig_slug")
    if rig_slug:
        if session.find_rig_by_slug(rig_slug) is None:
            raise AuthError(404, f"unknown rig_slug: {rig_slug}")

    model_release_id = payload.get("model_release_id")
    if model_release_id and session.fetch_model_by_id(model_release_id) is None:
        raise AuthError(404, f"unknown model_release_id: {model_release_id}")

    now = utcnow_iso()
    record = {
        "id": str(uuid.uuid4()),
        "author_id": caller["id"],
        "body": body,
        "kind": kind,
        "claim_id": claim_id,
        "rig_slug": rig_slug,
        "model_release_id": model_release_id,
        "comment_count": 0,
        "like_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    session.insert_post(record)
    session.commit()
    return post_view(session, {**record, "author_handle": caller.get("handle")}, viewer=caller)


def get_post(
    session: DatabaseSession,
    post_id: str,
    viewer: dict | None = None,
) -> dict[str, Any]:
    if not _is_uuid(post_id):
        raise AuthError(404, "post not found")
    row = session.find_post_by_id(post_id)
    if row is None or row.get("deleted_at") is not None:
        raise AuthError(404, "post not found")
    payload = post_view(session, row, viewer=viewer)
    comments = []
    for comment in session.list_comments_for_post(post_id):
        comments.append(
            {
                "id": comment["id"],
                "post_id": comment["post_id"],
                "parent_id": comment.get("parent_id"),
                "author_handle": comment.get("author_handle"),
                "body": comment["body"],
                "like_count": session.count_comment_likes(comment["id"]),
                "liked_by_viewer": bool(
                    viewer and session.has_comment_like(comment["id"], viewer["id"])
                ),
                "created_at": comment["created_at"],
            }
        )
    payload["comments"] = comments
    return payload


def delete_post(session: DatabaseSession, caller: dict, post_id: str) -> dict[str, Any]:
    if not _is_uuid(post_id):
        raise AuthError(404, "post not found")
    row = session.find_post_by_id(post_id)
    if row is None or row.get("deleted_at") is not None:
        raise AuthError(404, "post not found")
    if row.get("author_id") != caller["id"]:
        raise AuthError(403, "only the author can delete a post")
    affected = session.soft_delete_post(post_id, caller["id"])
    session.commit()
    if affected == 0:
        raise AuthError(404, "post not found")
    return {"deleted": True}


# ------------------------------------------------------------------ comments


def add_comment(
    session: DatabaseSession,
    caller: dict,
    post_id: str,
    body: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    from src.services.rate_limit_policy import comment_limit

    text = (body or "").strip()
    if not text:
        raise AuthError(400, "body is required")
    if len(text) > MAX_COMMENT_BODY:
        raise AuthError(400, f"body must be at most {MAX_COMMENT_BODY} characters")

    if not _is_uuid(post_id):
        raise AuthError(404, "post not found")
    post = session.find_post_by_id(post_id)
    if post is None or post.get("deleted_at") is not None:
        raise AuthError(404, "post not found")

    reputation = session.fetch_reputation_by_user(caller["id"])
    tier = reputation["tier"] if reputation else "L0"
    used = session.count_comments_since(caller["id"], hours_ago_iso(1))
    if used >= comment_limit(tier):
        raise AuthError(
            429,
            f"comment limit reached ({comment_limit(tier)} per hour at {tier}); "
            "verified runs raise your ceiling",
        )

    resolved_parent = None
    if parent_id:
        if not _is_uuid(parent_id):
            raise AuthError(404, f"unknown parent_id: {parent_id}")
        parent = session.find_comment_by_id(parent_id)
        if parent is None or parent.get("deleted_at") is not None:
            raise AuthError(404, f"unknown parent_id: {parent_id}")
        if parent["post_id"] != post_id:
            raise AuthError(400, "parent_id belongs to another post")
        # One level of threading: a reply to a reply hangs off the same
        # parent, so the conversation never grows a tree.
        resolved_parent = parent.get("parent_id") or parent["id"]

    record = {
        "id": str(uuid.uuid4()),
        "post_id": post_id,
        "author_id": caller["id"],
        "parent_id": resolved_parent,
        "body": text,
        "like_count": 0,
        "created_at": utcnow_iso(),
    }
    session.insert_comment(record)
    session.increment_post_comment_count(post_id)
    session.commit()

    _notify(
        session,
        recipient_id=post.get("author_id"),
        actor_id=caller["id"],
        kind="post_commented",
        payload={"post_id": post_id, "comment_id": record["id"]},
        skip_when_same=True,
    )
    return {
        "id": record["id"],
        "post_id": post_id,
        "parent_id": resolved_parent,
        "author_handle": caller.get("handle"),
        "body": text,
        "like_count": 0,
        "liked_by_viewer": False,
        "created_at": record["created_at"],
    }


# --------------------------------------------------------------------- likes


def toggle_post_like(session: DatabaseSession, caller: dict, post_id: str) -> dict[str, Any]:
    if not _is_uuid(post_id):
        raise AuthError(404, "post not found")
    post = session.find_post_by_id(post_id)
    if post is None or post.get("deleted_at") is not None:
        raise AuthError(404, "post not found")
    if session.has_post_like(post_id, caller["id"]):
        session.delete_post_like(post_id, caller["id"])
        liked = False
    else:
        session.insert_post_like(post_id, caller["id"])
        liked = True
    session.commit()
    count = session.count_post_likes(post_id)
    if liked:
        _notify(
            session,
            recipient_id=post.get("author_id"),
            actor_id=caller["id"],
            kind="post_liked",
            payload={"post_id": post_id},
            skip_when_same=True,
        )
    return {"liked": liked, "like_count": count}


def toggle_comment_like(
    session: DatabaseSession, caller: dict, comment_id: str
) -> dict[str, Any]:
    if not _is_uuid(comment_id):
        raise AuthError(404, "comment not found")
    comment = session.find_comment_by_id(comment_id)
    if comment is None or comment.get("deleted_at") is not None:
        raise AuthError(404, "comment not found")
    if session.has_comment_like(comment_id, caller["id"]):
        session.delete_comment_like(comment_id, caller["id"])
        liked = False
    else:
        session.insert_comment_like(comment_id, caller["id"])
        liked = True
    session.commit()
    return {"liked": liked, "like_count": session.count_comment_likes(comment_id)}


# --------------------------------------------------------------------- views


def post_view(
    session: DatabaseSession,
    row: dict[str, Any],
    viewer: dict | None = None,
) -> dict[str, Any]:
    post_id = row["id"]
    return {
        "id": post_id,
        "author_handle": row.get("author_handle"),
        "body": row["body"],
        "kind": row.get("kind") or "note",
        "claim_id": row.get("claim_id"),
        "rig_slug": row.get("rig_slug"),
        "model_release_id": row.get("model_release_id"),
        "comment_count": int(row.get("comment_count") or 0),
        "like_count": session.count_post_likes(post_id),
        "liked_by_viewer": bool(viewer and session.has_post_like(post_id, viewer["id"])),
        "created_at": row["created_at"],
    }


def _notify(
    session: DatabaseSession,
    recipient_id: str | None,
    actor_id: str,
    kind: str,
    payload: dict[str, Any],
    skip_when_same: bool = True,
) -> None:
    """Write a notification row, unless the actor is the recipient."""
    if not recipient_id:
        return
    if skip_when_same and recipient_id == actor_id:
        return
    session.insert_notification(
        {
            "id": str(uuid.uuid4()),
            "recipient_id": recipient_id,
            "kind": kind,
            "payload": payload,
        }
    )
    session.commit()
