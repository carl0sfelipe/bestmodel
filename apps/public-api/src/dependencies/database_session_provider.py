"""Database session provider (plan decision 11).

Defines the ``DatabaseSession`` interface shared by the query and submission
services, a psycopg-backed implementation for PostgreSQL, and the FastAPI
dependency that yields one session per request. Tests override the dependency
with the fake-adapters ``FakeDatabase``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator, Sequence

import psycopg
from fastapi import Request
from psycopg.rows import dict_row
from psycopg.types.json import Json


class DatabaseSession(ABC):
    """Thin data-access interface implemented by Postgres and the fake."""

    @abstractmethod
    def fetch_gpus_by_ids(self, ids: Sequence[str]) -> list[dict[str, Any]]:
        """Return gpu_model rows whose id is in ``ids``."""

    @abstractmethod
    def fetch_all_gpus(self) -> list[dict[str, Any]]:
        """Return every gpu_model row."""

    @abstractmethod
    def fetch_models_by_family(self, family: str) -> list[dict[str, Any]]:
        """Return model_release rows whose family equals ``family``."""

    @abstractmethod
    def fetch_model_by_id(self, model_release_id: str) -> dict[str, Any] | None:
        """Return the model_release row for ``model_release_id`` or None."""

    @abstractmethod
    def fetch_quantization_profiles(self) -> list[dict[str, Any]]:
        """Return every quantization_profile row."""

    @abstractmethod
    def fetch_quantization_profile_by_id(self, quantization_profile_id: str) -> dict[str, Any] | None:
        """Return the quantization_profile row for the given id or None."""

    @abstractmethod
    def fetch_inference_runtimes(self) -> list[dict[str, Any]]:
        """Return every inference_runtime row."""

    @abstractmethod
    def fetch_runtime_by_engine(self, engine: str) -> dict[str, Any] | None:
        """Return the inference_runtime row for the given engine or None."""

    @abstractmethod
    def fetch_runtime_by_id(self, runtime_id: str) -> dict[str, Any] | None:
        """Return the inference_runtime row for the given id or None."""

    @abstractmethod
    def fetch_first_model_release_id(self) -> str:
        """Return a deterministic model_release id used as a Phase 0 fallback."""

    @abstractmethod
    def fetch_validated_runs(self, limit: int, offset: int) -> list[dict[str, Any]]:
        """Return validated benchmark runs ordered by submitted_at descending."""

    @abstractmethod
    def fetch_leaderboard_entries(self) -> list[dict[str, Any]]:
        """Return validated runs joined with metrics, scenario, quant and trust
        columns used for ranking."""

    @abstractmethod
    def find_run_by_lookup(
        self,
        hardware_submission_id: str,
        model_release_id: str,
        quantization_profile_id: str,
        inference_runtime_id: str,
        benchmark_scenario_id: str,
    ) -> dict[str, Any] | None:
        """Return an existing run matching the dedupe dimensions or None."""

    @abstractmethod
    def find_hardware_submission(self, hardware_submission_id: str) -> dict[str, Any] | None:
        """Return the hardware_submission row for the given id or None."""

    @abstractmethod
    def insert_hardware_submission(self, record: dict[str, Any]) -> None:
        """Insert a hardware_submission row, ignoring id collisions."""

    @abstractmethod
    def insert_scenario(self, record: dict[str, Any]) -> None:
        """Insert a benchmark_scenario row, ignoring id collisions."""

    @abstractmethod
    def insert_benchmark_run(self, record: dict[str, Any]) -> None:
        """Insert a benchmark_run row."""

    @abstractmethod
    def insert_benchmark_metric(self, record: dict[str, Any]) -> None:
        """Insert a benchmark_metric row."""

    @abstractmethod
    def insert_benchmark_artifact(self, record: dict[str, Any]) -> None:
        """Insert a benchmark_artifact row."""

    @abstractmethod
    def find_app_user_by_handle(self, handle: str) -> dict[str, Any] | None:
        """Return the app_user row for ``handle`` or None."""

    @abstractmethod
    def find_app_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Return the app_user row for ``user_id`` or None."""

    @abstractmethod
    def insert_app_user(self, record: dict[str, Any]) -> None:
        """Insert an app_user row plus its zeroed user_reputation row."""

    @abstractmethod
    def insert_auth_challenge(self, record: dict[str, Any]) -> None:
        """Insert an auth_challenge row (upsert on challenge)."""

    @abstractmethod
    def fetch_auth_challenge(self, challenge: str) -> dict[str, Any] | None:
        """Return a non-expired auth_challenge row or None."""

    @abstractmethod
    def delete_auth_challenge(self, challenge: str) -> None:
        """Delete the auth_challenge row with the given challenge value."""

    @abstractmethod
    def insert_webauthn_credential(self, record: dict[str, Any]) -> None:
        """Insert a webauthn_credential row."""

    @abstractmethod
    def fetch_webauthn_credentials_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return every webauthn_credential row for ``user_id``."""

    @abstractmethod
    def update_webauthn_credential_sign_count(
        self, credential_id: bytes, sign_count: int, last_used_at: str
    ) -> None:
        """Persist the new signature counter after a successful assertion."""

    @abstractmethod
    def insert_auth_token(self, record: dict[str, Any]) -> None:
        """Insert an auth_token row."""

    @abstractmethod
    def fetch_auth_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Return the auth_token row for ``token_hash`` or None."""

    @abstractmethod
    def list_auth_tokens_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return non-revoked auth_token metadata rows for ``user_id``."""

    @abstractmethod
    def revoke_owned_auth_token(self, user_id: str, token_id: str, revoked_at: str) -> int:
        """Revoke a token owned by ``user_id``; return affected rows (0/1)."""

    @abstractmethod
    def touch_auth_token_last_used(self, token_id: str, last_used_at: str) -> None:
        """Update ``last_used_at`` for the token."""

    @abstractmethod
    def commit(self) -> None:
        """Persist pending writes."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying connection."""


class PostgresSession(DatabaseSession):
    """DatabaseSession backed by a psycopg connection to PostgreSQL."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def _fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self._fetchall(sql, params)
        return rows[0] if rows else None

    def fetch_gpus_by_ids(self, ids: Sequence[str]) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM gpu_model WHERE id = ANY(%s) ORDER BY id", (list(ids),)
        )

    def fetch_all_gpus(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM gpu_model ORDER BY id")

    def fetch_models_by_family(self, family: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM model_release WHERE family = %s ORDER BY id", (family,)
        )

    def fetch_model_by_id(self, model_release_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM model_release WHERE id = %s", (model_release_id,))

    def fetch_quantization_profiles(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM quantization_profile ORDER BY id")

    def fetch_quantization_profile_by_id(self, quantization_profile_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM quantization_profile WHERE id = %s", (quantization_profile_id,)
        )

    def fetch_inference_runtimes(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM inference_runtime ORDER BY id")

    def fetch_runtime_by_engine(self, engine: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM inference_runtime WHERE engine = %s", (engine,))

    def fetch_runtime_by_id(self, runtime_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM inference_runtime WHERE id = %s", (runtime_id,))

    def fetch_first_model_release_id(self) -> str:
        row = self._fetchone("SELECT id FROM model_release ORDER BY id LIMIT 1")
        return row["id"]

    def fetch_validated_runs(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT id, hardware_submission_id, model_release_id, quantization_profile_id, "
            "inference_runtime_id, benchmark_scenario_id, status, submitted_at "
            "FROM benchmark_run WHERE status = 'validated' "
            "ORDER BY submitted_at DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )

    def fetch_leaderboard_entries(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT run.id AS run_id, hardware.gpu_model_id AS gpu_model_id, "
            "run.model_release_id, run.quantization_profile_id, "
            "quant.weight_format AS quant_format, "
            "quant.expected_quality_retention AS quality_retention_estimate, "
            "runtime.engine AS runtime_engine, "
            "scenario.context_tokens, scenario.batch_size, "
            "run.trust_score, run.submitted_at, "
            "gpu.vram_mib AS vram_capacity_mib, "
            "m_decode.p50_value AS decode_tok_s, "
            "m_prefill.p50_value AS prefill_tok_s, "
            "m_ttft.p50_value AS ttft_ms, "
            "m_vram.p50_value AS peak_vram_mib, "
            "m_power.p50_value AS power_watt_avg "
            "FROM benchmark_run run "
            "JOIN benchmark_scenario scenario ON scenario.id = run.benchmark_scenario_id "
            "JOIN quantization_profile quant ON quant.id = run.quantization_profile_id "
            "JOIN inference_runtime runtime ON runtime.id = run.inference_runtime_id "
            "LEFT JOIN hardware_submission hardware ON hardware.id = run.hardware_submission_id "
            "LEFT JOIN gpu_model gpu ON gpu.id = hardware.gpu_model_id "
            "LEFT JOIN benchmark_metric m_decode ON m_decode.benchmark_run_id = run.id "
            "AND m_decode.kind = 'decode_tok_s' "
            "LEFT JOIN benchmark_metric m_prefill ON m_prefill.benchmark_run_id = run.id "
            "AND m_prefill.kind = 'prefill_tok_s' "
            "LEFT JOIN benchmark_metric m_ttft ON m_ttft.benchmark_run_id = run.id "
            "AND m_ttft.kind = 'ttft_ms' "
            "LEFT JOIN benchmark_metric m_vram ON m_vram.benchmark_run_id = run.id "
            "AND m_vram.kind = 'peak_vram_mib' "
            "LEFT JOIN benchmark_metric m_power ON m_power.benchmark_run_id = run.id "
            "AND m_power.kind = 'power_watt_avg' "
            "WHERE run.status = 'validated' ORDER BY run.submitted_at DESC"
        )

    def find_run_by_lookup(
        self,
        hardware_submission_id: str,
        model_release_id: str,
        quantization_profile_id: str,
        inference_runtime_id: str,
        benchmark_scenario_id: str,
    ) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT id FROM benchmark_run WHERE hardware_submission_id = %s "
            "AND model_release_id = %s AND quantization_profile_id = %s "
            "AND inference_runtime_id = %s AND benchmark_scenario_id = %s LIMIT 1",
            (
                hardware_submission_id,
                model_release_id,
                quantization_profile_id,
                inference_runtime_id,
                benchmark_scenario_id,
            ),
        )

    def find_hardware_submission(self, hardware_submission_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT id FROM hardware_submission WHERE id = %s", (hardware_submission_id,)
        )

    def insert_hardware_submission(self, record: dict[str, Any]) -> None:
        record = dict(record)
        record["environment_snapshot"] = Json(record["environment_snapshot"])
        self._connection.execute(
            "INSERT INTO hardware_submission "
            "(id, owner_account_id, gpu_model_id, cpu_model_id, gpu_count, ram_gib, "
            "os_name, os_version, environment_snapshot) "
            "VALUES (%(id)s, %(owner_account_id)s, %(gpu_model_id)s, %(cpu_model_id)s, "
            "%(gpu_count)s, %(ram_gib)s, %(os_name)s, %(os_version)s, %(environment_snapshot)s) "
            "ON CONFLICT (id) DO NOTHING",
            record,
        )

    def insert_scenario(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO benchmark_scenario "
            "(id, prompt_tokens, generated_tokens, context_tokens, batch_size, tensor_parallel) "
            "VALUES (%(id)s, %(prompt_tokens)s, %(generated_tokens)s, %(context_tokens)s, "
            "%(batch_size)s, %(tensor_parallel)s) ON CONFLICT (id) DO NOTHING",
            record,
        )

    def insert_benchmark_run(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO benchmark_run "
            "(id, hardware_submission_id, model_release_id, quantization_profile_id, "
            "inference_runtime_id, benchmark_scenario_id, status, client_version, "
            "signature, payload_digest) "
            "VALUES (%(id)s, %(hardware_submission_id)s, %(model_release_id)s, "
            "%(quantization_profile_id)s, %(inference_runtime_id)s, %(benchmark_scenario_id)s, "
            "%(status)s, %(client_version)s, %(signature)s, %(payload_digest)s)",
            record,
        )

    def insert_benchmark_metric(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO benchmark_metric (benchmark_run_id, kind, p50_value, unit) "
            "VALUES (%(benchmark_run_id)s, %(kind)s, %(p50_value)s, %(unit)s)",
            record,
        )

    def insert_benchmark_artifact(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO benchmark_artifact "
            "(id, benchmark_run_id, artifact_kind, sha256_digest, storage_key, size_bytes) "
            "VALUES (%(id)s, %(benchmark_run_id)s, %(artifact_kind)s, %(sha256_digest)s, "
            "%(storage_key)s, %(size_bytes)s)",
            record,
        )

    def find_app_user_by_handle(self, handle: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM app_user WHERE handle = %s", (handle,))

    def find_app_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM app_user WHERE id = %s", (user_id,))

    def insert_app_user(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO app_user (id, handle, display_name) "
            "VALUES (%(id)s, %(handle)s, %(display_name)s)",
            record,
        )
        self._connection.execute(
            "INSERT INTO user_reputation (app_user_id) VALUES (%(app_user_id)s)",
            {"app_user_id": record["id"]},
        )

    def insert_auth_challenge(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO auth_challenge (challenge, purpose, app_user_id, expires_at) "
            "VALUES (%(challenge)s, %(purpose)s, %(app_user_id)s, %(expires_at)s) "
            "ON CONFLICT (challenge) DO UPDATE SET purpose = EXCLUDED.purpose, "
            "app_user_id = EXCLUDED.app_user_id, expires_at = EXCLUDED.expires_at",
            record,
        )

    def fetch_auth_challenge(self, challenge: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM auth_challenge "
            "WHERE challenge = %s AND expires_at > now()",
            (challenge,),
        )

    def delete_auth_challenge(self, challenge: str) -> None:
        self._connection.execute(
            "DELETE FROM auth_challenge WHERE challenge = %s", (challenge,)
        )

    def insert_webauthn_credential(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO webauthn_credential "
            "(id, app_user_id, credential_id, public_key, sign_count, transports) "
            "VALUES (%(id)s, %(app_user_id)s, %(credential_id)s, %(public_key)s, "
            "%(sign_count)s, %(transports)s)",
            record,
        )

    def fetch_webauthn_credentials_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM webauthn_credential WHERE app_user_id = %s ORDER BY created_at",
            (user_id,),
        )

    def update_webauthn_credential_sign_count(
        self, credential_id: bytes, sign_count: int, last_used_at: str
    ) -> None:
        self._connection.execute(
            "UPDATE webauthn_credential SET sign_count = %s, last_used_at = %s "
            "WHERE credential_id = %s",
            (sign_count, last_used_at, psycopg.Binary(credential_id)),
        )

    def insert_auth_token(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO auth_token (id, app_user_id, kind, token_hash, name, expires_at) "
            "VALUES (%(id)s, %(app_user_id)s, %(kind)s, %(token_hash)s, %(name)s, %(expires_at)s)",
            record,
        )

    def fetch_auth_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM auth_token WHERE token_hash = %s", (token_hash,)
        )

    def list_auth_tokens_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT id, kind, name, expires_at, revoked_at, created_at, last_used_at "
            "FROM auth_token WHERE app_user_id = %s AND revoked_at IS NULL "
            "ORDER BY created_at DESC",
            (user_id,),
        )

    def revoke_owned_auth_token(self, user_id: str, token_id: str, revoked_at: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE auth_token SET revoked_at = %s "
                "WHERE id = %s AND app_user_id = %s AND revoked_at IS NULL",
                (revoked_at, token_id, user_id),
            )
            return cursor.rowcount

    def touch_auth_token_last_used(self, token_id: str, last_used_at: str) -> None:
        self._connection.execute(
            "UPDATE auth_token SET last_used_at = %s WHERE id = %s",
            (last_used_at, token_id),
        )

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


class DatabaseSessionProvider:
    """Creates a Postgres-backed session per request."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def create_session(self) -> DatabaseSession:
        return PostgresSession(psycopg.connect(self._dsn, row_factory=dict_row))


def get_database_session(request: Request) -> Iterator[DatabaseSession]:
    """FastAPI dependency yielding a session that closes after the request."""
    provider: DatabaseSessionProvider = request.app.state.database_provider
    session = provider.create_session()
    try:
        yield session
    finally:
        session.close()
