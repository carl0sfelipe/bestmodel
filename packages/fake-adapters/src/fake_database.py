"""In-memory database session used by tests (fake adapter, no external services).

Implements the same ``DatabaseSession`` interface as the psycopg-backed
``PostgresSession`` and is pre-loaded with the seed catalog so match queries
behave realistically without a database.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.dependencies.database_session_provider import DatabaseSession

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SEED_DIR = _REPO_ROOT / "infra" / "seed"


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


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
        self._users: list[dict[str, Any]] = []
        self._reputations: list[dict[str, Any]] = []
        self._credentials: list[dict[str, Any]] = []
        self._challenges: list[dict[str, Any]] = []
        self._tokens: list[dict[str, Any]] = []
        self._rigs: list[dict[str, Any]] = []
        self._badges: list[dict[str, Any]] = []
        self._claims: list[dict[str, Any]] = []
        self._votes: list[dict[str, Any]] = []
        self._reputation_events: list[dict[str, Any]] = []
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

    def find_app_user_by_handle(self, handle: str) -> dict[str, Any] | None:
        return next((row for row in self._users if row["handle"] == handle), None)

    def find_app_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return next((row for row in self._users if row["id"] == user_id), None)

    def insert_app_user(self, record: dict[str, Any]) -> None:
        if any(row["handle"] == record["handle"] for row in self._users):
            raise ValueError(f"duplicate handle: {record['handle']}")
        self._users.append(dict(record))
        self._reputations.append({"app_user_id": record["id"], "points": 0, "tier": "L0"})

    def insert_auth_challenge(self, record: dict[str, Any]) -> None:
        stored = dict(record)
        self._challenges = [c for c in self._challenges if c["challenge"] != stored["challenge"]]
        self._challenges.append(stored)

    def fetch_auth_challenge(self, challenge: str) -> dict[str, Any] | None:
        for row in self._challenges:
            if row["challenge"] != challenge:
                continue
            if _parse_ts(row["expires_at"]) <= datetime.now(timezone.utc):
                continue
            return dict(row)
        return None

    def delete_auth_challenge(self, challenge: str) -> None:
        self._challenges = [c for c in self._challenges if c["challenge"] != challenge]

    def insert_webauthn_credential(self, record: dict[str, Any]) -> None:
        self._credentials.append(dict(record))

    def fetch_webauthn_credentials_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in sorted(
                (c for c in self._credentials if c["app_user_id"] == user_id),
                key=lambda c: c["created_at"],
            )
        ]

    def update_webauthn_credential_sign_count(
        self, credential_id: bytes, sign_count: int, last_used_at: str
    ) -> None:
        for row in self._credentials:
            if bytes(row["credential_id"]) == bytes(credential_id):
                row["sign_count"] = sign_count
                row["last_used_at"] = last_used_at

    def insert_auth_token(self, record: dict[str, Any]) -> None:
        self._tokens.append(dict(record))

    def fetch_auth_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        return next(
            (dict(row) for row in self._tokens if row["token_hash"] == token_hash),
            None,
        )

    def list_auth_tokens_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = [
            {k: row[k] for k in ("id", "kind", "name", "expires_at", "revoked_at", "created_at", "last_used_at")}
            for row in self._tokens
            if row["app_user_id"] == user_id and row.get("revoked_at") is None
        ]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def revoke_owned_auth_token(self, user_id: str, token_id: str, revoked_at: str) -> int:
        affected = 0
        for row in self._tokens:
            if row["id"] == token_id and row["app_user_id"] == user_id and row.get("revoked_at") is None:
                row["revoked_at"] = revoked_at
                affected += 1
        return affected

    def touch_auth_token_last_used(self, token_id: str, last_used_at: str) -> None:
        for row in self._tokens:
            if row["id"] == token_id:
                row["last_used_at"] = last_used_at

    def insert_rig(self, record: dict[str, Any]) -> None:
        if any(row["slug"] == record["slug"] for row in self._rigs):
            raise ValueError(f"duplicate slug: {record['slug']}")
        self._rigs.append(dict(record))

    def find_rig_by_slug(self, slug: str) -> dict[str, Any] | None:
        return next((row for row in self._rigs if row["slug"] == slug), None)

    def update_rig(self, rig_id: str, fields: dict[str, Any]) -> int:
        allowed = {"nickname", "topology", "is_public", "hardware_submission_id"}
        affected = 0
        for row in self._rigs:
            if row["id"] != rig_id:
                continue
            for key in set(fields) & allowed:
                row[key] = fields[key]
            row["updated_at"] = _parse_ts("2026-01-01T00:00:00+00:00")
            affected += 1
        return affected

    def list_visible_rigs_by_owner(self, owner_id: str, viewer_id: str | None) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self._rigs
            if row["owner_id"] == owner_id and (row.get("is_public") or viewer_id == owner_id)
        ]

    def fetch_validated_runs_for_hardware(self, hardware_submission_id: str, limit: int) -> list[dict[str, Any]]:
        runs = sorted(
            (
                run
                for run in self._runs
                if run["hardware_submission_id"] == hardware_submission_id
                and run["status"] == "validated"
            ),
            key=lambda r: r["submitted_at"],
            reverse=True,
        )[:limit]
        return [self._run_with_metrics(run) for run in runs]

    def _run_with_metrics(self, run: dict[str, Any]) -> dict[str, Any]:
        medians = {}
        for kind in ("decode_tok_s", "prefill_tok_s", "ttft_ms", "peak_vram_mib"):
            values = sorted(
                m["p50_value"] for m in self._metrics
                if m["benchmark_run_id"] == run["id"] and m["kind"] == kind
            )
            medians[kind] = values[len(values) // 2] if values else None
        return {
            "run_id": run["id"],
            "model_release_id": run["model_release_id"],
            "quantization_profile_id": run["quantization_profile_id"],
            "inference_runtime_id": run["inference_runtime_id"],
            "submitted_at": run["submitted_at"],
            **medians,
        }

    def fetch_reputation_by_user(self, user_id: str) -> dict[str, Any] | None:
        return next(
            (
                {
                    "points": row["points"],
                    "tier": row["tier"],
                    "updated_at": row.get("updated_at"),
                }
                for row in self._reputations
                if row["app_user_id"] == user_id
            ),
            None,
        )

    def insert_badge(self, record: dict[str, Any]) -> None:
        duplicate = any(
            b["app_user_id"] == record["app_user_id"] and b["code"] == record["code"]
            for b in self._badges
        )
        if not duplicate:
            stored = dict(record)
            stored.setdefault("awarded_at", datetime.now(timezone.utc).isoformat())
            self._badges.append(stored)

    def fetch_badges_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {"code": b["code"], "awarded_at": b["awarded_at"]}
            for b in sorted(
                (b for b in self._badges if b["app_user_id"] == user_id),
                key=lambda b: str(b["awarded_at"]),
            )
        ]

    def fetch_pool_measurements(
        self, model_release_id: str, quantization_profile_id: str | None
    ) -> dict[str, Any]:
        runs = [
            run
            for run in self._runs
            if run["status"] == "validated"
            and run["model_release_id"] == model_release_id
            and (quantization_profile_id is None or run["quantization_profile_id"] == quantization_profile_id)
        ]

        def median(kind: str):
            values = sorted(
                m["p50_value"]
                for run in runs
                for m in self._metrics
                if m["benchmark_run_id"] == run["id"] and m["kind"] == kind
            )
            return values[len(values) // 2] if values else None

        return {
            "run_count": len(runs),
            "p50_decode_tok_s": median("decode_tok_s"),
            "p50_prefill_tok_s": median("prefill_tok_s"),
        }

    def insert_run_claim(self, record: dict[str, Any]) -> None:
        self._claims.append(dict(record))

    def find_run_claim_by_id(self, claim_id: str) -> dict[str, Any] | None:
        return next((row for row in self._claims if row["id"] == claim_id), None)

    def set_run_claim_status(self, claim_id: str, status: str) -> int:
        affected = 0
        for row in self._claims:
            if row["id"] == claim_id:
                row["status"] = status
                affected += 1
        return affected

    def list_run_claims(self, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        rows = [row for row in self._claims if status is None or row["status"] == status]
        rows.sort(key=lambda r: str(r["created_at"]), reverse=True)
        return [dict(row) for row in rows[offset : offset + limit]]

    def upsert_claim_vote(self, record: dict[str, Any]) -> None:
        for row in self._votes:
            if row["run_claim_id"] == record["run_claim_id"] and row["voter_id"] == record["voter_id"]:
                row["verdict"] = record["verdict"]
                row["weight"] = record["weight"]
                row["updated_at"] = record["created_at"]
                return
        self._votes.append(dict(record))

    def bind_claim_to_run(self, claim_id: str, run_id: str) -> int:
        affected = 0
        for row in self._claims:
            if (
                row["id"] == claim_id
                and row["status"] == "open"
                and row.get("benchmark_run_id") is None
            ):
                row["benchmark_run_id"] = run_id
                affected += 1
        return affected

    def fetch_settlement_context(self, run_id: str) -> dict[str, Any] | None:
        for row in self._claims:
            if row.get("benchmark_run_id") != run_id or row["status"] != "open":
                continue
            margin = sum(
                float(v["weight"]) * (1 if v["verdict"] == "plausible" else -1)
                for v in self._votes
                if v["run_claim_id"] == row["id"]
            )
            rep = self.fetch_reputation_by_user(row["claimant_id"]) or {"points": 0}
            return {
                "claim_id": row["id"],
                "claimant_id": row["claimant_id"],
                "margin": margin,
                "points": int(rep["points"]),
            }
        return None

    def complete_claim_settlement(
        self,
        claim_id: str,
        claimant_id: str,
        events: list[tuple[str, int]],
        new_points: int,
        new_tier: str,
    ) -> None:
        from src.services.auth_common import utcnow_iso

        for row in self._claims:
            if row["id"] == claim_id and row["status"] == "open":
                row["status"] = "settled_verified"
        for reason, delta in events:
            self._reputation_events.append(
                {
                    "id": str(len(self._reputation_events)),
                    "app_user_id": claimant_id,
                    "reason": reason,
                    "delta": delta,
                    "created_at": utcnow_iso(),
                }
            )
        for row in self._reputations:
            if row["app_user_id"] == claimant_id:
                row["points"] = new_points
                row["tier"] = new_tier
                row["updated_at"] = utcnow_iso()

    def fetch_votes_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        return [
            {"voter_id": row["voter_id"], "verdict": row["verdict"], "weight": row["weight"]}
            for row in sorted(
                (v for v in self._votes if v["run_claim_id"] == claim_id),
                key=lambda v: str(v["created_at"]),
            )
        ]

    # -- test helpers ----------------------------------------------------

    def expire_challenge(self, challenge: str) -> None:
        """Force an existing auth_challenge row into the past (test-only)."""
        for row in self._challenges:
            if row["challenge"] == challenge:
                row["expires_at"] = "2000-01-01T00:00:00+00:00"

    def add_expired_token(self, record: dict[str, Any]) -> None:
        self._tokens.append(dict(record))

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass
