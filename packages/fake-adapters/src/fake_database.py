"""In-memory database session used by tests (fake adapter, no external services).

Implements the same ``DatabaseSession`` interface as the psycopg-backed
``PostgresSession`` and is pre-loaded with the seed catalog so match queries
behave realistically without a database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from src.dependencies.database_session_provider import DatabaseSession

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SEED_DIR = _REPO_ROOT / "infra" / "seed"


def _load_seed(filename: str) -> list[dict[str, Any]]:
    return json.loads((_SEED_DIR / filename).read_text(encoding="utf-8"))


class FakeDatabase(DatabaseSession):
    def __init__(self) -> None:
        self._gpus = _load_seed("gpu_models.json")
        self._models = _load_seed("model_releases.json")
        self._quants = _load_seed("quantization_profiles.json")
        self._runtimes = _load_seed("inference_runtimes.json")
        self._runs = []
        self._hardware_submissions = []
        self._scenarios = []
        self._metrics = []
        self._artifacts = []
        self._leaderboard_entries = []
        self._seed_validated_runs()

    def _seed_validated_runs(self) -> None:
        self._runs.append(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "hardware_submission_id": "00000000-0000-0000-0000-000000000010",
                "model_release_id": "model-qwen25-coder-32b",
                "quantization_profile_id": "q-exl2-4.0bpw",
                "inference_runtime_id": "exllamav2",
                "benchmark_scenario_id": "00000000-0000-0000-0000-000000000011",
                "status": "validated",
                "client_version": "0.1.0",
                "signature": "sig",
                "payload_digest": "digest",
                "submitted_at": "2026-07-01T10:00:00Z",
            }
        )
        self._runs.append(
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "hardware_submission_id": "00000000-0000-0000-0000-000000000020",
                "model_release_id": "model-qwen25-coder-7b",
                "quantization_profile_id": "q-gguf-q4-k-m",
                "inference_runtime_id": "llama-cpp",
                "benchmark_scenario_id": "00000000-0000-0000-0000-000000000021",
                "status": "validated",
                "client_version": "0.1.0",
                "signature": "sig",
                "payload_digest": "digest",
                "submitted_at": "2026-07-02T10:00:00Z",
            }
        )

    def fetch_gpus_by_ids(self, ids: Sequence[str]) -> list[dict[str, Any]]:
        wanted = set(ids)
        return [row for row in self._gpus if row["id"] in wanted]

    def fetch_all_gpus(self) -> list[dict[str, Any]]:
        return list(self._gpus)

    def fetch_models_by_family(self, family: str) -> list[dict[str, Any]]:
        return [row for row in self._models if row["family"] == family]

    def fetch_model_by_id(self, model_release_id: str) -> dict[str, Any] | None:
        return next((row for row in self._models if row["id"] == model_release_id), None)

    def fetch_quantization_profiles(self) -> list[dict[str, Any]]:
        return list(self._quants)

    def fetch_quantization_profile_by_id(self, quantization_profile_id: str) -> dict[str, Any] | None:
        return next((row for row in self._quants if row["id"] == quantization_profile_id), None)

    def fetch_inference_runtimes(self) -> list[dict[str, Any]]:
        return list(self._runtimes)

    def fetch_runtime_by_engine(self, engine: str) -> dict[str, Any] | None:
        return next((row for row in self._runtimes if row["engine"] == engine), None)

    def fetch_runtime_by_id(self, runtime_id: str) -> dict[str, Any] | None:
        return next((row for row in self._runtimes if row["id"] == runtime_id), None)

    def fetch_first_model_release_id(self) -> str:
        return self._models[0]["id"]

    def fetch_validated_runs(self, limit: int, offset: int) -> list[dict[str, Any]]:
        validated = [run for run in self._runs if run["status"] == "validated"]
        validated.sort(key=lambda run: run["submitted_at"], reverse=True)
        return validated[offset : offset + limit]

    def add_leaderboard_entry(self, entry: dict[str, Any]) -> None:
        self._leaderboard_entries.append(dict(entry))

    def fetch_leaderboard_entries(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._leaderboard_entries]

    def find_run_by_lookup(
        self,
        hardware_submission_id: str,
        model_release_id: str,
        quantization_profile_id: str,
        inference_runtime_id: str,
        benchmark_scenario_id: str,
    ) -> dict[str, Any] | None:
        for run in self._runs:
            if (
                run["hardware_submission_id"] == hardware_submission_id
                and run["model_release_id"] == model_release_id
                and run["quantization_profile_id"] == quantization_profile_id
                and run["inference_runtime_id"] == inference_runtime_id
                and run["benchmark_scenario_id"] == benchmark_scenario_id
            ):
                return run
        return None

    def find_hardware_submission(self, hardware_submission_id: str) -> dict[str, Any] | None:
        return next(
            (row for row in self._hardware_submissions if row["id"] == hardware_submission_id),
            None,
        )

    def insert_hardware_submission(self, record: dict[str, Any]) -> None:
        if not self.find_hardware_submission(record["id"]):
            self._hardware_submissions.append(dict(record))

    def insert_scenario(self, record: dict[str, Any]) -> None:
        if not any(scenario["id"] == record["id"] for scenario in self._scenarios):
            self._scenarios.append(dict(record))

    def insert_benchmark_run(self, record: dict[str, Any]) -> None:
        self._runs.append(dict(record))

    def insert_benchmark_metric(self, record: dict[str, Any]) -> None:
        self._metrics.append(dict(record))

    def insert_benchmark_artifact(self, record: dict[str, Any]) -> None:
        self._artifacts.append(dict(record))

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass
