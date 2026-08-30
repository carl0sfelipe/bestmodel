"""Route tests for GET /v1/leaderboard (basic contract)."""

from __future__ import annotations

from conftest import make_leaderboard_entry, seed_leaderboard_run


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


def test_entries_without_source_class_never_render(leaderboard_client, seeded_database):
    seed_leaderboard_run(seeded_database, run_id="run-no-class", source_class=None)
    response = leaderboard_client.get("/v1/leaderboard", params={"limit": 100})
    run_ids = [run["run_id"] for run in response.json()["runs"]]
    assert "run-no-class" not in run_ids
    assert run_ids  # the classified cells still render


def test_source_class_and_video_metrics_surface_on_entries(leaderboard_client, seeded_database):
    seed_leaderboard_run(
        seeded_database,
        run_id="run-video-1",
        runtime_engine="comfyui",
        recipe_id="wan22-flf2v-720p-81f-v1",
        seconds_per_clip=123.4,
        it_per_s=10.0,
        frames_per_s=0.66,
        decode_tok_s=None,
        source_class="measured_signed",
    )
    response = leaderboard_client.get(
        "/v1/leaderboard", params={"source_class": "measured_signed", "recipe_id": "wan22-flf2v-720p-81f-v1", "limit": 100}
    )
    runs = response.json()["runs"]
    video = next(run for run in runs if run["run_id"] == "run-video-1")
    assert video["source_class"] == "measured_signed"
    assert video["recipe_id"] == "wan22-flf2v-720p-81f-v1"
    assert video["seconds_per_clip"] == 123.4
    assert video["frames_per_s"] == 0.66


def test_source_class_filter_excludes_other_classes(leaderboard_client, seeded_database):
    seed_leaderboard_run(seeded_database, run_id="run-harvest", source_class="harvested")
    response = leaderboard_client.get("/v1/leaderboard", params={"source_class": "harvested", "limit": 100})
    run_ids = [run["run_id"] for run in response.json()["runs"]]
    assert run_ids == ["run-harvest"]
