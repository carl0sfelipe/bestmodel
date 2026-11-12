"""L08 tests: the classic social layer — posts, comments, likes.

The rules under test:
  · writes need a bearer token; reads are public
  · a post carries TEXT only — numbers belong to claims
  · a reply to a reply hangs off the same parent (one level of threading)
  · liking is a toggle and never counts twice
  · a post never enters a validated leaderboard
  · the unified feed mixes the three item types without breaking scope/sort
  · the author is notified about a comment and a like
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import make_passkey_session
from src.dependencies.database_session_provider import get_database_session
from src.main import create_app

HANDLE_A = "ada"
HANDLE_B = "grace"


@pytest.fixture()
def client(database):
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _post(client, token, **overrides):
    payload = {"body": "The 3090 runs this quant at 41 tok/s for me."}
    payload.update(overrides)
    return client.post("/v1/posts", json=payload, headers=_auth(token))


# --- creation ----------------------------------------------------------------


def test_post_requires_auth(client):
    assert client.post("/v1/posts", json={"body": "hello"}).status_code == 401


def test_create_post_and_read_it_publicly(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    created = _post(client, token)
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["author_handle"] == HANDLE_A
    assert payload["like_count"] == 0
    assert payload["comment_count"] == 0

    # reads are public
    public = client.get(f"/v1/posts/{payload['id']}")
    assert public.status_code == 200
    assert public.json()["body"] == payload["body"]


def test_post_body_is_required_and_capped(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    assert _post(client, token, body="").status_code == 422
    assert _post(client, token, body="x" * 2001).status_code == 422


def test_post_refuses_to_carry_numbers(client, database, monkeypatch):
    """A post is text. A measurement belongs in a claim."""
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    refused = client.post(
        "/v1/posts",
        json={"body": "look at this", "claimed_metrics": {"decode_tok_s": 41.5}},
        headers=_auth(token),
    )
    assert refused.status_code == 400
    assert "claim" in refused.json()["detail"]


def test_post_kind_is_validated(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    assert _post(client, token, kind="rant").status_code == 400
    assert _post(client, token, kind="question").status_code == 200


def test_post_attaches_to_a_known_claim_only(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    assert _post(client, token, claim_id="00000000-0000-0000-0000-000000000000").status_code == 404
    assert _post(client, token, model_release_id="not-a-model").status_code == 404
    assert _post(client, token, model_release_id="model-qwen25-coder-7b").status_code == 200


def test_post_rate_limit_scales_with_tier(client, database, monkeypatch):
    """L0 gets three posts a day."""
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    for index in range(3):
        assert _post(client, token, body=f"post {index}").status_code == 200
    blocked = _post(client, token, body="one too many")
    assert blocked.status_code == 429
    assert "per 24h" in blocked.json()["detail"]


# --- comments ----------------------------------------------------------------


def test_comment_requires_auth(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    post = _post(client, token).json()
    assert client.post(f"/v1/posts/{post['id']}/comments", json={"body": "hi"}).status_code == 401


def test_comment_counts_and_lands_in_the_post(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    post = _post(client, token_a).json()

    comment = client.post(
        f"/v1/posts/{post['id']}/comments", json={"body": "same here"}, headers=_auth(token_b)
    )
    assert comment.status_code == 200, comment.text
    assert comment.json()["author_handle"] == HANDLE_B

    fetched = client.get(f"/v1/posts/{post['id']}").json()
    assert fetched["comment_count"] == 1
    assert len(fetched["comments"]) == 1
    assert fetched["comments"][0]["body"] == "same here"


def test_reply_to_a_reply_keeps_one_level_of_threading(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    post = _post(client, token_a).json()

    first = client.post(
        f"/v1/posts/{post['id']}/comments", json={"body": "first"}, headers=_auth(token_b)
    ).json()
    reply = client.post(
        f"/v1/posts/{post['id']}/comments",
        json={"body": "second", "parent_id": first["id"]},
        headers=_auth(token_a),
    ).json()
    # the reply hangs off the same parent as the comment it answers
    assert reply["parent_id"] == first["id"]

    third = client.post(
        f"/v1/posts/{post['id']}/comments",
        json={"body": "third", "parent_id": reply["id"]},
        headers=_auth(token_b),
    ).json()
    assert third["parent_id"] == first["id"]


def test_comment_on_another_post_parent_is_rejected(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    post = _post(client, token_a).json()
    other = _post(client, token_a, body="another post").json()
    comment = client.post(
        f"/v1/posts/{other['id']}/comments", json={"body": "x"}, headers=_auth(token_a)
    ).json()
    refused = client.post(
        f"/v1/posts/{post['id']}/comments",
        json={"body": "x", "parent_id": comment["id"]},
        headers=_auth(token_a),
    )
    assert refused.status_code == 400


def test_comment_on_a_missing_post_is_404(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    response = client.post(
        "/v1/posts/00000000-0000-0000-0000-000000000000/comments",
        json={"body": "x"},
        headers=_auth(token),
    )
    assert response.status_code == 404


# --- likes -------------------------------------------------------------------


def test_like_is_a_toggle_and_counts_once(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    post = _post(client, token_a).json()

    first = client.post(f"/v1/posts/{post['id']}/likes", headers=_auth(token_b))
    assert first.status_code == 200
    assert first.json() == {"liked": True, "like_count": 1}

    again = client.post(f"/v1/posts/{post['id']}/likes", headers=_auth(token_b))
    assert again.json() == {"liked": False, "like_count": 0}

    liked = client.post(f"/v1/posts/{post['id']}/likes", headers=_auth(token_b))
    assert liked.json() == {"liked": True, "like_count": 1}

    # a second account's like is a second like
    client.post(f"/v1/posts/{post['id']}/likes", headers=_auth(token_a))
    assert client.get(f"/v1/posts/{post['id']}").json()["like_count"] == 2


def test_comment_like_toggles(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    post = _post(client, token_a).json()
    comment = client.post(
        f"/v1/posts/{post['id']}/comments", json={"body": "hi"}, headers=_auth(token_b)
    ).json()

    liked = client.post(f"/v1/comments/{comment['id']}/likes", headers=_auth(token_a))
    assert liked.json() == {"liked": True, "like_count": 1}
    unliked = client.post(f"/v1/comments/{comment['id']}/likes", headers=_auth(token_a))
    assert unliked.json() == {"liked": False, "like_count": 0}


def test_like_requires_auth(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    post = _post(client, token).json()
    assert client.post(f"/v1/posts/{post['id']}/likes").status_code == 401


# --- deletion ----------------------------------------------------------------


def test_only_the_author_deletes_a_post(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    post = _post(client, token_a).json()

    assert client.delete(f"/v1/posts/{post['id']}", headers=_auth(token_b)).status_code == 403
    assert client.delete(f"/v1/posts/{post['id']}", headers=_auth(token_a)).status_code == 200
    assert client.get(f"/v1/posts/{post['id']}").status_code == 404


# --- notifications -----------------------------------------------------------


def test_author_is_notified_about_a_comment_and_a_like(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    post = _post(client, token_a).json()

    client.post(
        f"/v1/posts/{post['id']}/comments", json={"body": "same here"}, headers=_auth(token_b)
    )
    client.post(f"/v1/posts/{post['id']}/likes", headers=_auth(token_b))

    notifications = client.get("/v1/notifications", headers=_auth(token_a)).json()
    kinds = {row["kind"] for row in notifications}
    assert "post_commented" in kinds
    assert "post_liked" in kinds


def test_liking_your_own_post_does_not_notify_you(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    post = _post(client, token).json()
    client.post(f"/v1/posts/{post['id']}/likes", headers=_auth(token))
    notifications = client.get("/v1/notifications", headers=_auth(token)).json()
    assert all(row["kind"] != "post_liked" for row in notifications)


# --- the feed ----------------------------------------------------------------


def test_feed_mixes_posts_with_claims_and_runs(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    _post(client, token, body="a note from the wall")
    claim = client.post(
        "/v1/claims",
        json={
            "model_release_id": "model-qwen25-coder-7b",
            "claimed_metrics": {"decode_tok_s": 41.5},
        },
        headers=_auth(token),
    )
    assert claim.status_code in (200, 201), claim.text

    feed = client.get("/v1/feed?scope=global&sort=recent").json()
    kinds = {item["type"] for item in feed}
    assert {"post", "claim", "verified_run"} <= kinds
    posts = [item for item in feed if item["type"] == "post"]
    assert posts[0]["body"] == "a note from the wall"
    assert posts[0]["handle"] == HANDLE_A


def test_following_scope_shows_only_followed_accounts(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    _post(client, token_a, body="from ada")
    _post(client, token_b, body="from grace")

    following = client.get("/v1/feed?scope=following&sort=recent", headers=_auth(token_b)).json()
    assert [item["body"] for item in following if item["type"] == "post"] == []

    client.post(f"/v1/users/{HANDLE_A}/follow", headers=_auth(token_b))
    following = client.get("/v1/feed?scope=following&sort=recent", headers=_auth(token_b)).json()
    assert [item["body"] for item in following if item["type"] == "post"] == ["from ada"]


def test_a_post_never_enters_the_validated_leaderboard(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    _post(client, token, body="I measured 9999 tok/s on my 3090")
    leaderboard = client.get("/v1/leaderboard").text
    assert "9999 tok/s on my 3090" not in leaderboard


def test_a_bad_id_is_a_404_not_a_500(client, database, monkeypatch):
    """A link that points at nothing must not take the database down."""
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    for path in ("/v1/posts/nope", "/v1/posts/00000000-0000-0000-0000-000000000000"):
        response = client.get(path)
        assert response.status_code == 404, path
    assert client.post("/v1/posts/nope/likes", headers=_auth(token)).status_code == 404
    assert (
        client.post("/v1/comments/nope/likes", headers=_auth(token)).status_code == 404
    )
