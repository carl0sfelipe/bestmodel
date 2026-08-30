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
    """Thin data-access interface implemented by Postgres and the fake.
    Lockstep rule (D4): every method here ships with fake + postgres +
    contract-row updates in the same commit — the S25a introspection test
    fails naming the first backend that lags.
    """

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
    def fetch_recipe_by_id(self, recipe_id: str) -> dict[str, Any] | None:
        """Return the recipe row for the given recipe_id or None."""

    @abstractmethod
    def fetch_gpu_by_id(self, gpu_model_id: str) -> dict[str, Any] | None:
        """Return the gpu_model row for the given id or None."""

    # ── S23: per-user signing keys (attribution of submitted runs) ──────────
    # LOAD-BEARING: every method here must exist on BOTH backends — the S25a
    # introspection test (tests/test_session_contract.py) fails naming the
    # first missing one. A new method is: this ABC + PostgresSession +
    # FakeDatabase in the same commit.
    @abstractmethod
    def insert_signing_key(self, record: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def fetch_signing_key_by_id(self, key_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def fetch_signing_keys_by_user(self, app_user_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_contributor_points(self) -> list[dict[str, Any]]:
        """S27: per-contributor validated signed runs, for the Lineup export."""
        raise NotImplementedError

    @abstractmethod
    def revoke_signing_key(self, key_id: str, revoked_at: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_contributor_by_email(self, email: str) -> dict[str, Any] | None:
        """Return the contributor_account row for the given email or None."""

    @abstractmethod
    def find_contributor_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Return the contributor_account row whose token hash matches or None."""

    @abstractmethod
    def insert_contributor(self, record: dict[str, Any]) -> None:
        """Insert a contributor_account row."""

    @abstractmethod
    def count_reported_submissions_since(self, ip_address: str, hours: int) -> int:
        """Count reported_submission_log rows for the IP within the last ``hours``."""

    @abstractmethod
    def insert_reported_submission_log(self, record: dict[str, Any]) -> None:
        """Insert a reported_submission_log row."""

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
    def find_run_by_id(self, run_id: str) -> dict[str, Any] | None:
        """Return the full benchmark_run row for ``run_id`` or None.

        Round-trip read for the S25a parity suite; lockstep: the run-record
        shape (domain-schema ``run_record``), fake and postgres stay in the
        same commit.
        """

    @abstractmethod
    def find_scenario_by_id(self, scenario_id: str) -> dict[str, Any] | None:
        """Return the full benchmark_scenario row for ``scenario_id`` or None."""

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
    def insert_rig(self, record: dict[str, Any]) -> None:
        """Insert a rig row."""

    @abstractmethod
    def find_rig_by_slug(self, slug: str) -> dict[str, Any] | None:
        """Return the rig row for ``slug`` or None."""

    @abstractmethod
    def update_rig(
        self,
        rig_id: str,
        fields: dict[str, Any],
    ) -> int:
        """Update whitelisted rig columns; return affected rows (0/1)."""

    @abstractmethod
    def list_visible_rigs_by_owner(self, owner_id: str, viewer_id: str | None) -> list[dict[str, Any]]:
        """Return rigs of ``owner_id`` visible to ``viewer_id`` (None = anonymous)."""

    @abstractmethod
    def fetch_validated_runs_for_hardware(self, hardware_submission_id: str, limit: int) -> list[dict[str, Any]]:
        """Return validated runs bound to a hardware submission with metric medians."""

    @abstractmethod
    def fetch_reputation_by_user(self, user_id: str) -> dict[str, Any] | None:
        """Return the user_reputation row for ``user_id`` or None."""

    @abstractmethod
    def insert_badge(self, record: dict[str, Any]) -> None:
        """Insert a badge row (unique per user+code)."""

    @abstractmethod
    def fetch_badges_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return badge rows for ``user_id`` ordered by awarded_at."""

    @abstractmethod
    def fetch_all_models(self) -> list[dict[str, Any]]:
        """Return every model_release row."""

    @abstractmethod
    def find_run_claim_by_external_ref(self, external_ref: str) -> dict[str, Any] | None:
        """Imported claim for this external reference (idempotency key)."""

    @abstractmethod
    def fetch_pool_measurements(
        self, model_release_id: str, quantization_profile_id: str | None
    ) -> dict[str, Any]:
        """Return validated-run count + metric medians for the model/quant."""

    @abstractmethod
    def insert_run_claim(self, record: dict[str, Any]) -> None:
        """Insert a run_claim row."""

    @abstractmethod
    def find_run_claim_by_id(self, claim_id: str) -> dict[str, Any] | None:
        """Return the run_claim row or None."""

    @abstractmethod
    def set_run_claim_status(self, claim_id: str, status: str) -> int:
        """Transition claim status; return affected rows (0/1)."""

    @abstractmethod
    def list_run_claims(self, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        """Return run_claims newest-first, optionally filtered by status."""

    @abstractmethod
    def upsert_claim_vote(self, record: dict[str, Any]) -> None:
        """Insert or replace the voter's verdict on a claim."""

    @abstractmethod
    def fetch_votes_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        """Return one row per voter with current verdict and weight."""

    @abstractmethod
    def fetch_badge_context(self, run_id: str) -> dict[str, Any] | None:
        """Validated-run summary for badge rendering (None if not validated)."""

    @abstractmethod
    def count_claims_since(self, user_id: str, since: str) -> int:
        """Claims created by ``user_id`` after ``since``."""

    @abstractmethod
    def count_votes_since(self, user_id: str, since: str) -> int:
        """Votes cast by ``user_id`` after ``since``."""

    @abstractmethod
    def insert_follow(self, record: dict[str, Any]) -> None:
        """Insert a follow edge (unique pair, self-follow blocked)."""

    @abstractmethod
    def delete_follow(self, follower_id: str, followee_id: str) -> int:
        """Remove the edge; return affected rows."""

    @abstractmethod
    def fetch_follow_counts(self, user_id: str) -> dict[str, int]:
        """Return {'followers': n, 'following': n} for ``user_id``."""

    @abstractmethod
    def is_following(self, follower_id: str | None, followee_id: str) -> bool:
        """Whether ``follower_id`` follows ``followee_id`` (False if None)."""

    @abstractmethod
    def list_followee_ids(self, user_id: str) -> list[str]:
        """Return ids of accounts ``user_id`` follows."""

    @abstractmethod
    def insert_notification(self, record: dict[str, Any]) -> None:
        """Insert a notification row."""

    @abstractmethod
    def list_notifications_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return notifications newest-first with read status."""

    @abstractmethod
    def mark_notification_read(self, notification_id: str, recipient_id: str) -> int:
        """Mark one notification read for its recipient; return rows (0/1)."""

    @abstractmethod
    def list_recent_claims_by_users(self, user_ids: list[str] | None, limit: int) -> list[dict[str, Any]]:
        """Recent claims; ``None`` selects every account (global feed)."""

    @abstractmethod
    def list_recent_validated_runs_by_owners(self, owner_ids: list[str] | None, limit: int) -> list[dict[str, Any]]:
        """Validated runs attributed to owners; ``None`` selects all."""

    @abstractmethod
    def bind_claim_to_run(self, claim_id: str, run_id: str) -> int:
        """Link an open claim to an incoming run; return affected rows (0/1)."""

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

    def fetch_recipe_by_id(self, recipe_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM recipe WHERE recipe_id = %s", (recipe_id,))

    def fetch_gpu_by_id(self, gpu_model_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM gpu_model WHERE id = %s", (gpu_model_id,))

    def find_contributor_by_email(self, email: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM contributor_account WHERE email = %s", (email,)
        )

    def find_contributor_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM contributor_account WHERE token_hash = %s", (token_hash,)
        )

    def insert_contributor(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO contributor_account (id, email, token_hash) "
            "VALUES (%(id)s, %(email)s, %(token_hash)s)",
            record,
        )

    def count_reported_submissions_since(self, ip_address: str, hours: int) -> int:
        rows = self._fetchall(
            "SELECT count(*) AS n FROM reported_submission_log "
            "WHERE ip_address = %s AND created_at >= now() - (%s || ' hours')::interval",
            (ip_address, str(hours)),
        )
        return int(rows[0]["n"])

    def insert_reported_submission_log(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO reported_submission_log "
            "(id, contributor_id, benchmark_run_id, ip_address) "
            "VALUES (%(id)s, %(contributor_id)s, %(benchmark_run_id)s, %(ip_address)s)",
            record,
        )

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
            "run.recipe_id, run.source_class, "
            "run.seconds_per_clip, run.it_per_s, run.frames_per_s, "
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

    def find_run_by_id(self, run_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM benchmark_run WHERE id = %s", (run_id,))

    def find_scenario_by_id(self, scenario_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM benchmark_scenario WHERE id = %s", (scenario_id,))

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
            "(id, scenario_kind, prompt_tokens, generated_tokens, context_tokens, "
            "batch_size, tensor_parallel, width, height, frames, steps, cfg, shift, seed) "
            "VALUES (%(id)s, %(scenario_kind)s, %(prompt_tokens)s, %(generated_tokens)s, "
            "%(context_tokens)s, %(batch_size)s, %(tensor_parallel)s, %(width)s, %(height)s, "
            "%(frames)s, %(steps)s, %(cfg)s, %(shift)s, %(seed)s) "
            "ON CONFLICT (id) DO NOTHING",
            record,
        )

    def insert_benchmark_run(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO benchmark_run "
            "(id, hardware_submission_id, model_release_id, quantization_profile_id, "
            "inference_runtime_id, benchmark_scenario_id, status, client_version, "
            "signature, payload_digest, signature_key_id, recipe_id, source_class, "
            "seconds_per_clip, it_per_s, frames_per_s, source_url) "
            "VALUES (%(id)s, %(hardware_submission_id)s, %(model_release_id)s, "
            "%(quantization_profile_id)s, %(inference_runtime_id)s, %(benchmark_scenario_id)s, "
            "%(status)s, %(client_version)s, %(signature)s, %(payload_digest)s, "
            "%(signature_key_id)s, %(recipe_id)s, %(source_class)s, %(seconds_per_clip)s, "
            "%(it_per_s)s, %(frames_per_s)s, %(source_url)s)",
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

    def insert_signing_key(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO signing_key "
            "(id, app_user_id, label, public_key_pem, algorithm, created_at, revoked_at) "
            "VALUES (%(id)s, %(app_user_id)s, %(label)s, %(public_key_pem)s, "
            "%(algorithm)s, %(created_at)s, %(revoked_at)s)",
            record,
        )

    def fetch_signing_key_by_id(self, key_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM signing_key WHERE id = %s", (key_id,))

    def fetch_signing_keys_by_user(self, app_user_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT k.*, "
            "(SELECT count(*) FROM benchmark_run r "
            " WHERE r.signature_key_id = k.id) AS run_count "
            "FROM signing_key k WHERE k.app_user_id = %s ORDER BY k.created_at",
            (app_user_id,),
        )

    def fetch_contributor_points(self) -> list[dict[str, Any]]:
        """S27: validated signed runs per contributor (points = runs x 2)."""
        rows = self._fetchall(
            "SELECT u.handle AS handle, "
            "COUNT(r.id) AS validated_runs, "
            "COUNT(r.id) * 2 AS points "
            "FROM app_user u "
            "JOIN signing_key k ON k.app_user_id = u.id "
            "JOIN benchmark_run r ON r.signature_key_id = k.id "
            "WHERE r.status = %(status)s "
            "GROUP BY u.handle "
            "ORDER BY points DESC, u.handle",
            {"status": "validated"},
        )
        return [
            {"handle": str(r["handle"]), "points": int(r["points"]), "validated_runs": int(r["validated_runs"])}
            for r in rows
        ]

    def revoke_signing_key(self, key_id: str, revoked_at: str) -> None:
        self._connection.execute(
            "UPDATE signing_key SET revoked_at = %(revoked_at)s WHERE id = %(key_id)s",
            {"key_id": key_id, "revoked_at": revoked_at},
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

    def insert_rig(self, record: dict[str, Any]) -> None:
        record = dict(record)
        record["topology"] = Json(record.get("topology") or {})
        self._connection.execute(
            "INSERT INTO rig (id, owner_id, nickname, slug, topology, is_public, "
            "hardware_submission_id, created_at, updated_at) "
            "VALUES (%(id)s, %(owner_id)s, %(nickname)s, %(slug)s, %(topology)s, "
            "%(is_public)s, %(hardware_submission_id)s, %(created_at)s, %(updated_at)s)",
            record,
        )

    def find_rig_by_slug(self, slug: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM rig WHERE slug = %s", (slug,))

    def update_rig(self, rig_id: str, fields: dict[str, Any]) -> int:
        allowed = {"nickname", "topology", "is_public", "hardware_submission_id"}
        assignments = []
        params: dict[str, Any] = {"rig_id": rig_id}
        for key in sorted(set(fields) & allowed):
            value = fields[key]
            if key == "topology":
                value = Json(value or {})
            assignments.append(f"{key} = %({key})s")
            params[key] = value
        if not assignments:
            return 0
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE rig SET {', '.join(assignments)}, updated_at = now() "
                "WHERE id = %(rig_id)s",
                params,
            )
            return cursor.rowcount

    def list_visible_rigs_by_owner(self, owner_id: str, viewer_id: str | None) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM rig WHERE owner_id = %s AND "
            "(is_public OR (%s::uuid IS NOT NULL AND owner_id = %s::uuid)) "
            "ORDER BY created_at",
            (owner_id, viewer_id, viewer_id),
        )

    def fetch_validated_runs_for_hardware(self, hardware_submission_id: str, limit: int) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT run.id AS run_id, run.model_release_id, run.quantization_profile_id, "
            "run.inference_runtime_id, run.submitted_at, "
            "m_decode.p50_value AS decode_tok_s, "
            "m_prefill.p50_value AS prefill_tok_s, "
            "m_ttft.p50_value AS ttft_ms, "
            "m_vram.p50_value AS peak_vram_mib "
            "FROM benchmark_run run "
            "LEFT JOIN benchmark_metric m_decode ON m_decode.benchmark_run_id = run.id "
            "AND m_decode.kind = 'decode_tok_s' "
            "LEFT JOIN benchmark_metric m_prefill ON m_prefill.benchmark_run_id = run.id "
            "AND m_prefill.kind = 'prefill_tok_s' "
            "LEFT JOIN benchmark_metric m_ttft ON m_ttft.benchmark_run_id = run.id "
            "AND m_ttft.kind = 'ttft_ms' "
            "LEFT JOIN benchmark_metric m_vram ON m_vram.benchmark_run_id = run.id "
            "AND m_vram.kind = 'peak_vram_mib' "
            "WHERE run.hardware_submission_id = %s AND run.status = 'validated' "
            "ORDER BY run.submitted_at DESC LIMIT %s",
            (hardware_submission_id, limit),
        )

    def fetch_reputation_by_user(self, user_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT points, tier, updated_at FROM user_reputation WHERE app_user_id = %s",
            (user_id,),
        )

    def insert_badge(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO badge (id, app_user_id, code) VALUES (%(id)s, %(app_user_id)s, %(code)s) "
            "ON CONFLICT (app_user_id, code) DO NOTHING",
            record,
        )

    def fetch_badges_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT code, awarded_at FROM badge WHERE app_user_id = %s ORDER BY awarded_at",
            (user_id,),
        )

    def fetch_all_models(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM model_release ORDER BY id")

    def find_run_claim_by_external_ref(self, external_ref: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT * FROM run_claim WHERE external_ref = %s", (external_ref,)
        )

    def fetch_pool_measurements(
        self, model_release_id: str, quantization_profile_id: str | None
    ) -> dict[str, Any]:
        return self._fetchone(
            """
            SELECT
              (SELECT COUNT(*) FROM benchmark_run
                WHERE status = 'validated' AND model_release_id = %s
                  AND (%s::text IS NULL OR quantization_profile_id = %s::text)) AS run_count,
              (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY m.p50_value)
                FROM benchmark_metric m
                JOIN benchmark_run r ON r.id = m.benchmark_run_id
                WHERE r.status = 'validated' AND r.model_release_id = %s
                  AND (%s::text IS NULL OR r.quantization_profile_id = %s::text)
                  AND m.kind = 'decode_tok_s') AS p50_decode_tok_s,
              (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY m.p50_value)
                FROM benchmark_metric m
                JOIN benchmark_run r ON r.id = m.benchmark_run_id
                WHERE r.status = 'validated' AND r.model_release_id = %s
                  AND (%s::text IS NULL OR r.quantization_profile_id = %s::text)
                  AND m.kind = 'prefill_tok_s') AS p50_prefill_tok_s
            """,
            (
                model_release_id,
                quantization_profile_id,
                quantization_profile_id,
                model_release_id,
                quantization_profile_id,
                quantization_profile_id,
                model_release_id,
                quantization_profile_id,
                quantization_profile_id,
            ),
        )

    def insert_run_claim(self, record: dict[str, Any]) -> None:
        record = dict(record)
        record["claimed_metrics"] = Json(record["claimed_metrics"])
        record["prior_snapshot"] = Json(record["prior_snapshot"])
        record.setdefault("claimant_id", None)
        record.setdefault("source", None)
        record.setdefault("external_ref", None)
        self._connection.execute(
            "INSERT INTO run_claim (id, claimant_id, rig_id, model_release_id, "
            "quantization_profile_id, inference_runtime_id, gpu_model_id, context_tokens, "
            "claimed_metrics, note, status, prior_snapshot, source, external_ref, "
            "created_at, updated_at) "
            "VALUES (%(id)s, %(claimant_id)s, %(rig_id)s, %(model_release_id)s, "
            "%(quantization_profile_id)s, %(inference_runtime_id)s, %(gpu_model_id)s, "
            "%(context_tokens)s, %(claimed_metrics)s, %(note)s, %(status)s, "
            "%(prior_snapshot)s, %(source)s, %(external_ref)s, "
            "%(created_at)s, %(updated_at)s)",
            record,
        )

    def find_run_claim_by_id(self, claim_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM run_claim WHERE id = %s", (claim_id,))

    def set_run_claim_status(self, claim_id: str, status: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE run_claim SET status = %s, updated_at = now() "
                "WHERE id = %s",
                (status, claim_id),
            )
            return cursor.rowcount

    def list_run_claims(self, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        base_sql = (
            "SELECT c.*, COALESCE(u.handle, 'localmaxxing pool') AS claimant_handle "
            "FROM run_claim c LEFT JOIN app_user u ON u.id = c.claimant_id "
        )
        if status is not None:
            return self._fetchall(
                base_sql + "WHERE c.status = %s ORDER BY c.created_at DESC LIMIT %s OFFSET %s",
                (status, limit, offset),
            )
        return self._fetchall(
            base_sql + "ORDER BY c.created_at DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )

    def upsert_claim_vote(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO claim_vote (id, run_claim_id, voter_id, verdict, weight, created_at, updated_at) "
            "VALUES (%(id)s, %(run_claim_id)s, %(voter_id)s, %(verdict)s, %(weight)s, "
            "%(created_at)s, %(created_at)s) "
            "ON CONFLICT (run_claim_id, voter_id) DO UPDATE SET "
            "verdict = EXCLUDED.verdict, weight = EXCLUDED.weight, updated_at = now()",
            record,
        )

    def fetch_votes_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT voter_id, verdict, weight FROM claim_vote WHERE run_claim_id = %s "
            "ORDER BY created_at",
            (claim_id,),
        )

    def fetch_badge_context(self, run_id: str) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT r.id AS run_id, r.status, r.model_release_id, "
            "m.p50_value AS decode_tok_s, g.marketing_name AS gpu_marketing_name "
            "FROM benchmark_run r "
            "JOIN hardware_submission hs ON hs.id = r.hardware_submission_id "
            "LEFT JOIN gpu_model g ON g.id = hs.gpu_model_id "
            "LEFT JOIN LATERAL (SELECT p50_value FROM benchmark_metric mm "
            "  WHERE mm.benchmark_run_id = r.id AND mm.kind = 'decode_tok_s') m ON true "
            "WHERE r.id = %s",
            (run_id,),
        )

    def count_claims_since(self, user_id: str, since: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS n FROM run_claim WHERE claimant_id = %s AND created_at > %s",
            (user_id, since),
        )
        return int(row["n"])

    def count_votes_since(self, user_id: str, since: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS n FROM claim_vote WHERE voter_id = %s AND created_at > %s",
            (user_id, since),
        )
        return int(row["n"])

    def insert_follow(self, record: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO follow (id, follower_id, followee_id) "
            "VALUES (%(id)s, %(follower_id)s, %(followee_id)s)",
            record,
        )

    def delete_follow(self, follower_id: str, followee_id: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM follow WHERE follower_id = %s AND followee_id = %s",
                (follower_id, followee_id),
            )
            return cursor.rowcount

    def fetch_follow_counts(self, user_id: str) -> dict[str, int]:
        row = self._fetchone(
            "SELECT "
            "(SELECT COUNT(*) FROM follow WHERE followee_id = %s) AS followers, "
            "(SELECT COUNT(*) FROM follow WHERE follower_id = %s) AS following",
            (user_id, user_id),
        )
        return {"followers": int(row["followers"]), "following": int(row["following"])}

    def is_following(self, follower_id: str | None, followee_id: str) -> bool:
        if follower_id is None:
            return False
        row = self._fetchone(
            "SELECT 1 AS one FROM follow WHERE follower_id = %s AND followee_id = %s",
            (follower_id, followee_id),
        )
        return row is not None

    def list_followee_ids(self, user_id: str) -> list[str]:
        rows = self._fetchall(
            "SELECT followee_id FROM follow WHERE follower_id = %s", (user_id,)
        )
        return [row["followee_id"] for row in rows]

    def insert_notification(self, record: dict[str, Any]) -> None:
        record = dict(record)
        record["payload"] = Json(record.get("payload") or {})
        self._connection.execute(
            "INSERT INTO notification (id, recipient_id, kind, payload, read_at, created_at) "
            "VALUES (%(id)s, %(recipient_id)s, %(kind)s, %(payload)s, NULL, %(created_at)s)",
            record,
        )

    def list_notifications_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT id, kind, payload, read_at, created_at FROM notification "
            "WHERE recipient_id = %s ORDER BY created_at DESC LIMIT 100",
            (user_id,),
        )

    def mark_notification_read(self, notification_id: str, recipient_id: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE notification SET read_at = now() "
                "WHERE id = %s AND recipient_id = %s AND read_at IS NULL",
                (notification_id, recipient_id),
            )
            return cursor.rowcount

    def list_recent_claims_by_users(self, user_ids: list[str] | None, limit: int) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT c.*, COALESCE(u.handle, 'localmaxxing pool') AS claimant_handle "
            "FROM run_claim c "
            "LEFT JOIN app_user u ON u.id = c.claimant_id "
            "WHERE %s::uuid[] IS NULL OR c.claimant_id = ANY(%s::uuid[]) "
            "ORDER BY c.created_at DESC LIMIT %s",
            (user_ids, user_ids, limit),
        )

    def list_recent_validated_runs_by_owners(self, owner_ids: list[str] | None, limit: int) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT r.id AS run_id, r.model_release_id, r.quantization_profile_id, "
            "r.inference_runtime_id, hs.owner_account_id AS owner_account_id, "
            "r.submitted_at, m.p50_value AS decode_tok_s "
            "FROM benchmark_run r "
            "JOIN hardware_submission hs ON hs.id = r.hardware_submission_id "
            "LEFT JOIN LATERAL (SELECT p50_value FROM benchmark_metric mm "
            "  WHERE mm.benchmark_run_id = r.id AND mm.kind = 'decode_tok_s') m ON true "
            "WHERE r.status = 'validated' "
            "AND (%s::uuid[] IS NULL OR hs.owner_account_id = ANY(%s::uuid[])) "
            "ORDER BY r.submitted_at DESC LIMIT %s",
            (owner_ids, owner_ids, limit),
        )

    def bind_claim_to_run(self, claim_id: str, run_id: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE run_claim SET benchmark_run_id = %s, updated_at = now() "
                "WHERE id = %s AND status = 'open' AND benchmark_run_id IS NULL",
                (run_id, claim_id),
            )
            return cursor.rowcount

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
