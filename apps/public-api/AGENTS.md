# apps/public-api — Map

FastAPI service (REST/JSON + multipart intake). Layered: routes → services →
dependencies (providers). `main.py` builds the app (`create_app`), wiring state
from env vars (e.g. `DATABASE_URL`, `REDIS_URL`, `TRUSTED_ED25519_PUBLIC_KEY_PATH`, `ARTIFACT_VAULT_DIR`).

| Dir/File | Content |
|---|---|
| `routes/hardware_match_route.py` | `POST /v1/match/hardware-to-models` (§9.4 contract, field names frozen) |
| `routes/model_match_route.py` | `POST /v1/match/model-to-hardware` (minimum/recommended/cost_efficient roles) |
| `routes/benchmark_submission_route.py` | `POST /v1/submissions` (multipart) + `GET /v1/submissions/nonce` |
| `routes/leaderboard_route.py` | `GET /v1/leaderboard` with hardware/model/runtime/quant/context filters |
| `routes/auth_route.py` | `/v1/auth/passkey/{register,login}/{options,verify}` + `/v1/auth/tokens` CRUD (S13) |
| `routes/rig_route.py` | `POST /v1/rigs`, `GET/PATCH /v1/rigs/{slug}`, `POST /v1/rigs/{slug}/bind` (S14) |
| `routes/user_route.py` | `GET /v1/users/{handle}` public profile (S14) |
| `services/submit_benchmark_run.py` | intake pipeline: schema → digest → signature (Ed25519, env `TRUSTED_ED25519_PUBLIC_KEY_PATH`) → artifact digests → dedupe → insert → enqueue |
| `services/query_hardware_match.py` / `query_model_match.py` | match logic over catalog + roofline kernel |
| `services/query_leaderboard.py` | filters + Decimal→float coercion + recommendation-engine ranking |
| `services/register_passkey.py` / `authenticate_passkey.py` | WebAuthn ceremonies; challenge store + credential persistence (S13) |
| `services/auth_common.py` / `manage_auth_tokens.py` | AuthError, token issuance (SHA-256 at rest), agent-token CRUD (S13) |
| `services/create_rig.py` / `update_rig.py` / `rig_common.py` | rig CRUD + hardware binding; slugify + ownership checks (S14) |
| `services/query_rig_profile.py` / `query_user_profile.py` | rig detail with validated runs; profile payload (reputation/badges/visible rigs) (S14) |
| `dependencies/auth_provider.py` | `WebAuthnConfig` (env `AUTH_RP_ID`, `AUTH_RP_NAME`, `AUTH_EXPECTED_ORIGIN`), `get_current_user` bearer resolver (401 on missing/revoked/expired) + `get_optional_user` (degrades to anonymous) |
| `dependencies/database_session_provider.py` | `DatabaseSession` ABC + PostgresSession; jsonb via `Json()` (finding B2) |
| `dependencies/artifact_vault_provider.py` | LocalArtifactVault (filesystem under `ARTIFACT_VAULT_DIR`) |
| `dependencies/redis_queue_provider.py` | RedisStreamQueue, lazy connect, stream `benchmark_runs` |
| `schemas/` | Pydantic request/form models (SubmissionForm carries optional catalog binding overrides) |

Tests: `tests/` use fake-adapters via `conftest.py` (`client`, `leaderboard_client`
fixtures). Known limits: gpu-bound filtering needs bound hardware rows; community
submissions create anonymous hardware rows (S09 design note; Phase 1 accounts fix).
