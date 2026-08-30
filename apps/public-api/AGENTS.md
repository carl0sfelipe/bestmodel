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
| `routes/claim_route.py` | `POST /v1/claims`, `GET /v1/claims[?status&sort]`, `GET /v1/claims/{id}`, `POST .../votes`, `POST .../retract` (S15) |
| `routes/card_route.py` | `GET /v1/cards/claims/{id}.svg|.md` share cards (S18) |
| `routes/badge_route.py` | `GET /v1/badges/runs/{run_id}.svg` embeddable badge, validated runs only (S20) |
| `routes/social_route.py` | follow/unfollow, `/v1/notifications` (+read), `/v1/feed` — registered before user_route (S17) |
| `services/rate_limit_policy.py` | reputation-scaled ceilings: claims 2–50/24h, votes 5–250/h (L0→L4); enforced in claim create + vote services |
| `services/render_claim_card.py` / `render_run_badge.py` | deterministic SVG/markdown renderers; XML-escape everything user-controlled; golden-file gate for the card template |
| `services/submit_benchmark_run.py` | intake pipeline: schema → digest → signature (Ed25519, env `TRUSTED_ED25519_PUBLIC_KEY_PATH`) → artifact digests → dedupe → insert → enqueue |
| `services/query_hardware_match.py` / `query_model_match.py` | match logic over catalog + roofline kernel |
| `services/query_leaderboard.py` | filters + Decimal→float coercion + recommendation-engine ranking |
| `services/register_passkey.py` / `authenticate_passkey.py` | WebAuthn ceremonies; challenge store + credential persistence (S13) |
| `services/auth_common.py` / `manage_auth_tokens.py` | AuthError, token issuance (SHA-256 at rest), agent-token CRUD (S13) |
| `services/create_rig.py` / `update_rig.py` / `rig_common.py` | rig CRUD + hardware binding; slugify + ownership checks (S14) |
| `services/query_rig_profile.py` / `query_user_profile.py` | rig detail with validated runs; profile payload (reputation/badges/visible rigs) (S14) |
| `services/compute_vote_tally.py` | PURE margin math; tier→weight map bounded to [0.2, 1.0] (whale bound) — property-tested, do not move to DB |
| `services/compute_claim_prior.py` | frozen prior: pool medians + roofline range at creation time, never recomputed (S15) |
| `services/create_run_claim.py` / `vote_on_claim.py` / `query_run_claims.py` | claim lifecycle: create w/ prior, vote upsert (no self-votes), retract, list+sorts recent/controversial/strongest (S15) |
| `dependencies/auth_provider.py` | `WebAuthnConfig` (env `AUTH_RP_ID`, `AUTH_RP_NAME`, `AUTH_EXPECTED_ORIGIN`), `get_current_user` bearer resolver (401 on missing/revoked/expired) + `get_optional_user` (degrades to anonymous) |
| `dependencies/database_session_provider.py` | `DatabaseSession` ABC + PostgresSession; jsonb via `Json()` (finding B2) |
| `dependencies/artifact_vault_provider.py` | LocalArtifactVault (filesystem under `ARTIFACT_VAULT_DIR`) |
| `dependencies/redis_queue_provider.py` | RedisStreamQueue, lazy connect, stream `benchmark_runs` |
| `schemas/` | Pydantic request/form models (SubmissionForm carries optional catalog binding overrides) |

Tests: `tests/` use fake-adapters via `conftest.py` (`client`, `leaderboard_client`
fixtures). Known limits: gpu-bound filtering needs bound hardware rows; community
submissions create anonymous hardware rows (S09 design note; Phase 1 accounts fix).

## Change checklist

- Coluna nova em `benchmark_run`/`benchmark_scenario`: migration append-only +
  `PostgresSession` (INSERT e o SELECT de leitura) + `run_record.py` no
  domain-schema + round-trip `tests/test_session_video_roundtrip.py` — mesma
  commit, `make test` verde antes.
- `fetch_leaderboard_entries` (SELECT) e `query_leaderboard` (filtros +
  `_NUMERIC_FIELDS`) andam JUNTOS: campo novo precisa estar no SELECT e na
  coerção Decimal→float, senão o filtro silenciosamente derruba a linha
  (mode de falha observado: "filter silently drops everything").
- `METRIC_UNITS` em `submit_benchmark_run.py`: chave de métrica sem unidade é
  descartada do insert — chave nova de métrica = unidade nova aqui.
- `source_class` vazio nunca renderiza na leaderboard (`query_leaderboard`);
  todo caminho de insert de run precisa preenchê-lo.
- `find_run_by_id`/`find_scenario_by_id` são a leitura de round-trip do S25a —
  mudança de coluna sem atualizá-los quebra a suíte de paridade, não "o gate".
