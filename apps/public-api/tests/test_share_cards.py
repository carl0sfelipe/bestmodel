"""S18 tests: share cards (SVG + markdown) with a golden-file template gate.

The golden SVG pins the card template; regenerate deliberately with
``pytest --update-golden`` style flows by deleting the file and re-running
(see README note in the golden header).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_passkey_session, sample_report_dict, sign_report
from src.main import create_app
from src.services.render_claim_card import render_claim_card_markdown, render_claim_card_svg

GOLDEN = Path(__file__).resolve().parent / "golden" / "claim_card.svg"

HANDLE_A = "ada"


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _open_claim(client, database, monkeypatch) -> dict:
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    # give the pool a measured decode median so the card shows the strongest prior
    seeded_run = next(
        r for r in database._runs
        if r["model_release_id"] == "model-qwen25-coder-7b" and r["status"] == "validated"
    )
    database._metrics.append(
        {"benchmark_run_id": seeded_run["id"], "kind": "decode_tok_s", "p50_value": 17.4, "unit": "tok/s"}
    )
    claim = client.post(
        "/v1/claims",
        json={
            "model_release_id": "model-qwen25-coder-7b",
            "claimed_metrics": {"decode_tok_s": 18.7},
            "note": "felt fast",
        },
        headers=_auth(token),
    ).json()
    return {"token": token, "claim": claim}


def test_svg_card_renders_claim_facts(client, database, monkeypatch):
    seeded = _open_claim(client, database, monkeypatch)
    response = client.get(f"/v1/cards/claims/{seeded['claim']['id']}.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    body = response.text
    assert "@ada" in body
    assert "18.7 tok/s claimed" in body
    assert "measured" in body  # pool prior exists for the seeded model
    assert "<script" not in body


def test_svg_card_escapes_hostile_input():
    """Renderer-level guard: hostile strings can never inject SVG markup.

    (Handles themselves cannot contain these characters — the schema CHECK
    blocks them — but notes/display names flow through the same escaper.)
    """
    view = {
        "handle": '"><script>alert(1)</script>',
        "status": "open",
        "model_release_id": "<model&co>",
        "claimed_metrics": {"decode_tok_s": 5},
        "prior_snapshot": None,
        "tally": {},
    }
    svg = render_claim_card_svg(view)
    assert "<script>" not in svg
    assert "<model&co>" not in svg
    assert "&quot;&gt;&lt;script&gt;" in svg
    assert "alert(1)" in svg  # escaped text stays visible, inert


def test_markdown_card_contains_share_links(client, database, monkeypatch):
    seeded = _open_claim(client, database, monkeypatch)
    response = client.get(f"/v1/cards/claims/{seeded['claim']['id']}.md")
    assert response.status_code == 200
    text = response.text
    assert "@ada claims **18.7 tok/s**" in text
    assert f"https://bestmodel.run/claims/{seeded['claim']['id']}" in text


def test_unknown_claim_card_404(client):
    assert client.get("/v1/cards/claims/nope.svg").status_code == 404
    assert client.get("/v1/cards/claims/nope.md").status_code == 404


def test_golden_svg_template_is_stable():
    """Template drift gate: the fixed-fixture SVG must match the committed golden."""
    view = {
        "handle": "ada",
        "status": "open",
        "model_release_id": "model-qwen25-coder-7b",
        "claimed_metrics": {"decode_tok_s": 18.7},
        "prior_snapshot": {
            "pool": {"run_count": 2, "p50_decode_tok_s": 17.4},
            "roofline": None,
        },
        "tally": {"plausible_count": 2, "impossible_count": 1, "margin": 0.2},
    }
    rendered = render_claim_card_svg(view)
    if not GOLDEN.exists():
        GOLDEN.write_text(rendered)
        pytest.fail("golden missing; wrote a new one — inspect then commit it")
    assert rendered == GOLDEN.read_text()


def test_markdown_renderer_unit():
    view = {
        "handle": "grace",
        "id": "c-123",
        "model_release_id": "m",
        "claimed_metrics": {},
        "prior_snapshot": None,
        "tally": {"plausible_count": 0, "impossible_count": 3},
    }
    md = render_claim_card_markdown(view)
    assert "**no metric claimed**" in md
    assert "no data yet" in md
