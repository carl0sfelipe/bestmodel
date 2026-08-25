# apps/pool-backend/ — Map

Executable prompt pack (pre-plan) for the local backend that industrializes
the website data: syncs localmaxxing's public pool into SQLite, applies
roofline plausibility curation, exports the derived JSONs consumed by
`../bestmodel-web`, and serves the match/decision API on port 8790.
No product code exists until the executor sessions run.

- Read order: `README.md` -> `CONTRATO-GLOBAL.md` (incorporates web contract
  §3-§6 by reference) -> `ESTADO.md` -> `specs/`.
- Executor protocol: `PROMPT-EXECUTOR.md` (one session, one oracle, one
  commit `feat(backend-S<n>)`).
- Own uv project + SQLite by design — deliberately NOT wired to the Phase-0
  Postgres/Redis/gate; do not touch apps/, packages/, infra/.
- Shared-machine port rules apply (see CONTRATO §3); only port 8790.
