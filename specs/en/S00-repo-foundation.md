# S00 Repo Foundation (Monorepo Skeleton)

## Objective

Set up the monorepo skeleton required by Section 15 of the plan, serving as the foundation for all subsequent stories: directory structure (`apps/`, `packages/`, `cli/`, `infra/`, `docs/`, `tests/`), unified test entry point (`make test`), root-level Python / pnpm / Cargo workspace configuration, and local infrastructure orchestration (Postgres + TimescaleDB + pgvector, Redis, MinIO, Meilisearch) along with a CI skeleton.

## Dependencies

- None (Wave 0 bootstrap, depends on no other story)

## Wave

W0

## Deliverables

| Path | Content |
|---|---|
| `Makefile` | Top-level build / test entry point, including a `test` target |
| `pyproject.toml` | Root-level Python project (managed by uv) |
| `pnpm-workspace.yaml` | Frontend workspace |
| `Cargo.toml` | Top-level Cargo workspace |
| `apps/` | Placeholder directory (web-console, public-api, intake-worker to be created) |
| `packages/` | Placeholder directory (domain-schema to be created) |
| `cli/` | Placeholder directory (benchmark-probe to be created) |
| `infra/docker/docker-compose.yml` | Postgres 16 + TimescaleDB + pgvector, Redis, MinIO, Meilisearch |
| `infra/docker/postgres.Dockerfile` | Postgres 16 image with TimescaleDB and pgvector extensions enabled |
| `infra/ci/github-actions.yml` | CI skeleton (runs `make test`) |
| `docs/`, `tests/` | Placeholder directories |

## Requirements

- **R-1** The directory structure must follow the monorepo layout from Section 15 of the plan (`apps/`, `packages/`, `cli/`, `infra/`, `docs/`, `tests/`).
- **R-2** The `Makefile` provides the single `make test` command to trigger unit tests (Section 15 "Engineering standards rollout").
- **R-3** The root-level `pyproject.toml` is managed by uv; `uv run pytest` must work from the repo root.
- **R-4** `pnpm-workspace.yaml` declares the `apps/*` workspace.
- **R-5** `Cargo.toml` declares workspace members (reserving `cli/benchmark-probe`).
- **R-6** `infra/docker/docker-compose.yml` provides a Postgres 16 service whose image enables TimescaleDB and pgvector extensions (corresponding to the Section 10 time-series telemetry and vector retrieval requirements).
- **R-7** docker-compose includes Redis, MinIO, and Meilisearch services.
- **R-8** `infra/ci/github-actions.yml` is a CI skeleton that at minimum runs `make test`.
- **R-9** Engineering standards reference Section 15: no single file over 500 lines, functions kept at 4–20 lines, no ambiguous names (`data`, `handler`, `Manager`).

## Acceptance Criteria

- [ ] `make test` passes (including one no-op test).
- [ ] `docker compose -f infra/docker/docker-compose.yml config` returns a valid configuration (exit 0).
- [ ] `uv run pytest` runs successfully from the repo root.
- [ ] Directory structure matches Section 15 of the plan.

## Language Note

Code, comments, identifiers, and commit messages must all be in English; this Spec is written in Chinese and serves only as planning context.
