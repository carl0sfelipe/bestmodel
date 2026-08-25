# infra/ — Map

Everything that runs outside application code: container stack, schema
migrations, seed data, operational scripts, the integration gate.

| Path | What it is |
|---|---|
| `docker/docker-compose.yml` | postgres(timescale+pgvector)/redis/minio/meilisearch; host ports remapped to 5434/6380/9002-9003/7701 |
| `docker/postgres.Dockerfile` + `postgres-init.sql` | Postgres 16 image enabling timescaledb + vector |
| `migrations/0001–0004_*.sql` | canonical schema; applied by `scripts/migrate.py` via `make migrate` |
| `seed/*.json` + `seed/load_seed.py` | seed catalogs; `make seed`; extend JSON + re-run (idempotent) |
| `scripts/migrate.py` | versioned runner (`meta.schema_migrations`) |
| `scripts/check_host_ports.py` | guard: fail if compose would publish reserved ports |
| `scripts/e2e_gate.sh` | the Phase 0 gate (driven by `make gate`); also the reference for local end-to-end runs |
| `scripts/import_lab_export.py` | historical one-off: ingested the owner's 3090 lab zip (do not extend; superseded by CLI v2) |
| `ci/github-actions.yml` + `.github/workflows/ci.yml` | CI running `make test` |

Rules:
- Port changes MUST pass `make check-ports`; reserved ports are absolute.
- Migrations are append-only files; never edit applied ones, add a new number.
- Seed ids are deterministic (e.g. `gpu-rtx-4090`, `model-qwen25-coder-32b`) and
  referenced by tests/fixtures — keep stable, add rather than rename.
