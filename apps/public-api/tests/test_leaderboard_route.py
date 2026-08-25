"""Route tests for GET /v1/leaderboard (basic contract)."""

from __future__ import annotations


def test_returns_feasible_validated_runs_with_scores(leaderboard_client):
    response = leaderboard_client.get("/v1/leaderboard")
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert len(runs) == 3
    for run in runs:
        assert run["feasible"] is True
        assert 0.0 <= run["rank_score"] <= 1.0
        assert run["run_id"] != "run-lb-4-infeasible"


def test_default_order_is_rank_score_descending(leaderboard_client):
    runs = leaderboard_client.get("/v1/leaderboard").json()["runs"]
    scores = [run["rank_score"] for run in runs]
    assert scores == sorted(scores, reverse=True)


def test_sort_by_submitted_at(leaderboard_client):
    runs = leaderboard_client.get(
        "/v1/leaderboard", params={"sort": "submitted_at"}
    ).json()["runs"]
    submitted_at = [run["submitted_at"] for run in runs]
    assert submitted_at == sorted(submitted_at, reverse=True)


def test_pagination_limit_and_offset(leaderboard_client):
    first_page = leaderboard_client.get(
        "/v1/leaderboard", params={"limit": 2}
    ).json()["runs"]
    second_page = leaderboard_client.get(
        "/v1/leaderboard", params={"limit": 2, "offset": 2}
    ).json()["runs"]
    assert len(first_page) == 2
    assert len(second_page) == 1
    seen = {run["run_id"] for run in first_page + second_page}
    assert len(seen) == 3


def test_pagination_beyond_data_returns_empty_list(leaderboard_client):
    response = leaderboard_client.get("/v1/leaderboard", params={"limit": 10, "offset": 100})
    assert response.status_code == 200
    assert response.json() == {"runs": []}
