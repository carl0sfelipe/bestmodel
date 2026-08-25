"""PostgreSQL-backed repository for the intake worker.

Hydrates queued run events from the database (and the artifact vault) and
persists the pipeline outcomes: status transitions, trust assessments and
ranking update notifications.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

DEFAULT_DATABASE_URL = "postgresql://bestmodel:bestmodel@localhost:5434/bestmodel"
UNBOUND_HARDWARE = "unbound-hardware"
RANKING_STREAM_KEY = "ranking_updates"

_GROUP_JOIN = (
    "FROM benchmark_run r "
    "JOIN benchmark_scenario s ON s.id = r.benchmark_scenario_id "
    "JOIN inference_runtime rt ON rt.id = r.inference_runtime_id "
    "LEFT JOIN hardware_submission hs ON hs.id = r.hardware_submission_id "
)


def _group_where(dimension: Any, exclude_run_id: str) -> tuple[str, list[Any]]:
    clauses = [
        "r.model_release_id = %s",
        "r.quantization_profile_id = %s",
        "rt.engine = %s",
        "s.context_tokens = %s",
        "s.batch_size = %s",
        "r.id <> %s",
    ]
    params: list[Any] = [
        dimension.model_release_id,
        dimension.quantization_profile_id,
        dimension.runtime_engine,
        dimension.context_tokens,
        dimension.batch_size,
        exclude_run_id,
    ]
    if dimension.hardware_model_id == UNBOUND_HARDWARE:
        clauses.append("hs.gpu_model_id IS NULL")
    else:
        clauses.append("hs.gpu_model_id = %s")
        params.append(dimension.hardware_model_id)
    return " AND ".join(clauses), params


class PostgresIntakeRepository:
    def __init__(
        self,
        database_url: str | None = None,
        vault_dir: str | Path | None = None,
        redis_client: Any = None,
    ) -> None:
        self._dsn = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._vault_dir = Path(vault_dir or os.environ.get("ARTIFACT_VAULT_DIR", "./artifacts"))
        self._redis = redis_client

    def _connect(self):
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def find_existing_run_in_group(
        self, dimension: Any, exclude_run_id: str, statuses: tuple[str, ...]
    ) -> bool:
        where, params = _group_where(dimension, exclude_run_id)
        sql = f"SELECT 1 {_GROUP_JOIN} WHERE {where} AND r.status = ANY(%s) LIMIT 1"
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, (*params, list(statuses)))
            return cursor.fetchone() is not None

    def fetch_peer_decode_values(self, dimension: Any, exclude_run_id: str) -> list[float]:
        where, params = _group_where(dimension, exclude_run_id)
        sql = (
            "SELECT m.p50_value FROM benchmark_metric m "
            "JOIN benchmark_run r ON m.benchmark_run_id = r.id "
            "JOIN benchmark_scenario s ON s.id = r.benchmark_scenario_id "
            "JOIN inference_runtime rt ON rt.id = r.inference_runtime_id "
            "LEFT JOIN hardware_submission hs ON hs.id = r.hardware_submission_id "
            f"WHERE {where} AND r.status = 'validated' AND m.kind = 'decode_tok_s'"
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [float(row["p50_value"]) for row in cursor.fetchall()]

    def count_peers(self, dimension: Any) -> int:
        where, params = _group_where(dimension, "00000000-0000-0000-0000-000000000000")
        sql = (
            "SELECT count(*) AS peers "
            + _GROUP_JOIN
            + f" WHERE {where} AND r.status IN ('validated', 'quarantined')"
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params)
            return int(cursor.fetchone()["peers"])

    def record_trust_assessment(self, run_id: str, assessment: dict[str, float]) -> None:
        sql = (
            "INSERT INTO trust_assessment (benchmark_run_id, environment_completeness, "
            "statistical_plausibility, reproducibility_score, account_maturity, "
            "peer_corroboration, final_score, outlier_flags) "
            "VALUES (%(run_id)s, %(environment_completeness)s, %(statistical_plausibility)s, "
            "%(reproducibility_score)s, %(account_maturity)s, %(peer_corroboration)s, "
            "%(final_score)s, %(outlier_flags)s) "
            "ON CONFLICT (benchmark_run_id) DO UPDATE SET "
            "environment_completeness = EXCLUDED.environment_completeness, "
            "statistical_plausibility = EXCLUDED.statistical_plausibility, "
            "reproducibility_score = EXCLUDED.reproducibility_score, "
            "account_maturity = EXCLUDED.account_maturity, "
            "peer_corroboration = EXCLUDED.peer_corroboration, "
            "final_score = EXCLUDED.final_score, outlier_flags = EXCLUDED.outlier_flags, "
            "assessed_at = now()"
        )
        record = dict(assessment)
        record["run_id"] = run_id
        record.setdefault("outlier_flags", [])
        with self._connect() as connection:
            connection.execute(sql, record)
            connection.commit()

    def set_run_status(self, run_id: str, status: str, trust_score: float) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE benchmark_run SET status = %s, trust_score = %s WHERE id = %s",
                (status, trust_score, run_id),
            )
            connection.commit()

    def publish_ranking_update(self, event: dict[str, Any]) -> None:
        if self._redis is None:
            return
        fields = {key: str(value) for key, value in event.items()}
        self._redis.xadd(RANKING_STREAM_KEY, fields)

    def fetch_run_payload(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT r.id, r.model_release_id, r.quantization_profile_id, "
                "rt.engine AS runtime_engine, rt.version AS runtime_version, "
                "s.prompt_tokens, s.generated_tokens, s.batch_size, s.context_tokens, "
                "hs.gpu_model_id, hs.environment_snapshot "
                "FROM benchmark_run r "
                "JOIN benchmark_scenario s ON s.id = r.benchmark_scenario_id "
                "JOIN inference_runtime rt ON rt.id = r.inference_runtime_id "
                "JOIN hardware_submission hs ON hs.id = r.hardware_submission_id "
                "WHERE r.id = %s",
                (run_id,),
            )
            run_row = cursor.fetchone()
            if run_row is None:
                return None
            cursor.execute(
                "SELECT kind, p50_value FROM benchmark_metric WHERE benchmark_run_id = %s",
                (run_id,),
            )
            metrics = {row["kind"]: float(row["p50_value"]) for row in cursor.fetchall()}
            cursor.execute(
                "SELECT artifact_kind, sha256_digest, storage_key "
                "FROM benchmark_artifact WHERE benchmark_run_id = %s ORDER BY storage_key",
                (run_id,),
            )
            artifacts = [
                {
                    "artifact_kind": row["artifact_kind"],
                    "declared_sha256": row["sha256_digest"],
                    "content": self._read_vault_text(row["storage_key"]),
                }
                for row in cursor.fetchall()
            ]
            hardware = self._fetch_gpu_row(cursor, run_row["gpu_model_id"])
            model = self._fetch_row(cursor, "model_release", run_row["model_release_id"])
            quant = self._fetch_row(
                cursor, "quantization_profile", run_row["quantization_profile_id"]
            )
        return _assemble_payload(run_row, metrics, artifacts, hardware, model, quant)

    def _fetch_gpu_row(self, cursor, gpu_model_id: Optional[str]) -> dict[str, Any]:
        if gpu_model_id is None:
            return {}
        return self._fetch_row(cursor, "gpu_model", gpu_model_id) or {}

    @staticmethod
    def _fetch_row(cursor, table: str, record_id: str) -> Optional[dict[str, Any]]:
        cursor.execute(f"SELECT * FROM {table} WHERE id = %s", (record_id,))
        return cursor.fetchone()

    def _read_vault_text(self, storage_key: str) -> str:
        path = self._vault_dir / storage_key
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")


def _assemble_payload(
    run_row: dict[str, Any],
    metrics: dict[str, float],
    artifacts: list[dict[str, Any]],
    hardware: dict[str, Any],
    model: Optional[dict[str, Any]],
    quant: Optional[dict[str, Any]],
) -> dict[str, Any]:
    snapshot = run_row["environment_snapshot"] or {}
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    decode_tok_s = metrics.get("decode_tok_s", 0.0)
    generated = run_row["generated_tokens"]
    duration_seconds = metrics.get("ttft_ms", 0.0) / 1000.0
    if decode_tok_s > 0:
        duration_seconds += generated / decode_tok_s
    gpu_model_id = run_row["gpu_model_id"] or UNBOUND_HARDWARE
    return {
        "run_id": str(run_row["id"]),
        "schema_version": "0.9.0",
        "runtime_version": run_row["runtime_version"],
        "runtime_engine": run_row["runtime_engine"],
        "hardware_fingerprint": snapshot.get("hardware_fingerprint", "sha256:" + "0" * 64),
        "signature_valid": True,
        "duration_seconds": duration_seconds,
        "hardware": hardware,
        "model": model or {},
        "quant": quant or {},
        "scenario": {
            "prompt_tokens": run_row["prompt_tokens"],
            "generated_tokens": generated,
            "batch_size": run_row["batch_size"],
            "context_tokens": run_row["context_tokens"],
        },
        "metrics": metrics,
        "dimension": {
            "hardware_model_id": gpu_model_id,
            "model_release_id": run_row["model_release_id"],
            "quantization_profile_id": run_row["quantization_profile_id"],
            "runtime_engine": run_row["runtime_engine"],
            "context_tokens": run_row["context_tokens"],
            "batch_size": run_row["batch_size"],
        },
        "artifacts": artifacts,
    }
