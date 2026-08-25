"""Leaderboard filter tests (S11): hardware/model/runtime/quant/context."""

from __future__ import annotations

from conftest import make_leaderboard_entry, seed_leaderboard_fixtures
from src.dependencies.database_session_provider import DatabaseSession
from src.services.query_leaderboard import query_leaderboard


def run_ids(response) -> set:
    return {run["run_id"] for run in response.json()["runs"]}


def test_filter_by_model_release_id(leaderboard_client):
    response = leaderboard_client.get(
        "/v1/leaderboard", params={"model_release_id": "model-alpha"}
    )
    assert run_ids(response) == {"run-lb-1", "run-lb-2"}


def test_filter_by_gpu_model_id(leaderboard_client):
    response = leaderboard_client.get("/v1/leaderboard", params={"gpu_model_id": "gpu-b"})
    assert run_ids(response) == {"run-lb-3"}


def test_combined_gpu_and_runtime_filter(leaderboard_client):
    response = leaderboard_client.get(
        "/v1/leaderboard", params={"gpu_model_id": "gpu-b", "runtime_engine": "llama_cpp"}
    )
    assert run_ids(response) == {"run-lb-3"}
    response = leaderboard_client.get(
        "/v1/leaderboard", params={"gpu_model_id": "gpu-b", "runtime_engine": "vllm"}
    )
    assert run_ids(response) == set()


def test_filter_by_runtime_engine(leaderboard_client):
    response = leaderboard_client.get("/v1/leaderboard", params={"runtime_engine": "vllm"})
    assert run_ids(response) == {"run-lb-2"}


def test_filter_by_quantization_profile_and_format(leaderboard_client):
    by_profile = leaderboard_client.get(
        "/v1/leaderboard", params={"quantization_profile_id": "q-fp16"}
    )
    assert run_ids(by_profile) == {"run-lb-2"}
    by_format = leaderboard_client.get("/v1/leaderboard", params={"quant_format": "gguf_q4"})
    assert run_ids(by_format) == {"run-lb-1", "run-lb-3"}


def test_filter_by_context_bounds(leaderboard_client):
    wide = leaderboard_client.get("/v1/leaderboard", params={"context_tokens_min": 10000})
    assert run_ids(wide) == {"run-lb-2", "run-lb-3"}
    narrow = leaderboard_client.get("/v1/leaderboard", params={"context_tokens_max": 8192})
    assert run_ids(narrow) == {"run-lb-1"}
    window = leaderboard_client.get(
        "/v1/leaderboard",
        params={"context_tokens_min": 8192, "context_tokens_max": 16384},
    )
    assert run_ids(window) == {"run-lb-1", "run-lb-2"}


def test_batch_size_filter(leaderboard_client):
    response = leaderboard_client.get("/v1/leaderboard", params={"batch_size": 1})
    assert len(response.json()["runs"]) == 3
    response = leaderboard_client.get("/v1/leaderboard", params={"batch_size": 8})
    assert response.json()["runs"] == []


def test_infeasible_entry_is_hidden_and_scores_zero():
    from fake_database import FakeDatabase

    database: DatabaseSession = seed_leaderboard_fixtures(FakeDatabase())
    outcome = query_leaderboard(database, {}, None, None, None)
    assert all(run["run_id"] != "run-lb-4-infeasible" for run in outcome["runs"])

    entries = database.fetch_leaderboard_entries()
    infeasible = next(e for e in entries if e["run_id"] == "run-lb-4-infeasible")
    assert infeasible["peak_vram_mib"] > infeasible["vram_capacity_mib"] * 0.95


def test_unknown_filter_value_returns_empty(leaderboard_client):
    response = leaderboard_client.get(
        "/v1/leaderboard", params={"model_release_id": "model-nonexistent"}
    )
    assert response.json() == {"runs": []}


def test_entry_fields_include_ranking_data(leaderboard_client):
    runs = leaderboard_client.get("/v1/leaderboard").json()["runs"]
    top = runs[0]
    for field in (
        "run_id",
        "gpu_model_id",
        "model_release_id",
        "runtime_engine",
        "quantization_profile_id",
        "context_tokens",
        "decode_tok_s",
        "prefill_tok_s",
        "peak_vram_mib",
        "trust_score",
        "rank_score",
        "feasible",
    ):
        assert field in top, field
