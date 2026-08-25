# apps/pool-backend — pool sync, plausibility curation, local match API

Standalone data backend for bestmodel.run: syncs the public community
measurement pool (localmaxxing.com public API) into a local SQLite database,
applies physics-based (roofline) plausibility curation to every run, exports
the derived JSONs consumed by `apps/web`, and serves the decision engine as a
local API on port 8790:

- `hardware → models` and `model → hardware` matching

## Operation

Full cycle (sync → plausibility → derived → publish):

```bash
bash scripts/sync-all.sh
```

Local API service (refuses to start if port 8790 is taken, printing the
occupying PID):

```bash
bash scripts/run.sh     # start
pkill -f "uvicorn.*8790" # stop
```

Verification oracle:

```bash
uv run python scripts/check.py ops
uv run python scripts/check.py all
```

Optional: daily scheduling via launchd — plist in `scripts/launchd/`,
log at `out/sync-launchd.log`. SQLite runs in WAL mode for concurrent reads.
`sync-all.sh` does not restart the service.

## Build sessions (historical, strictly linear)

| # | Session | Produces |
|---|---|---|
| S1 | `specs/S1-scaffold.md` | uv project + FastAPI /healthz + check.py |
| S2 | `specs/S2-db-sync.md` | SQLite + idempotent pool sync |
| S3 | `specs/S3-plausibilidade.md` | roofline flags (ok/suspicious/impossible/exempt) |
| S4 | `specs/S4-derived-export.md` | cleaned derived JSONs + publish to apps/web |
| S5 | `specs/S5-match-api.md` | decision endpoints |
| S6 | `specs/S6-ops.md` | sync-all.sh + run.sh + smoke |

## Settled decisions (do not relitigate)

- SQLite instead of the monorepo Postgres (~5–10k rows, zero risk to the
  platform gate); port 8790 (checked against the shared-machine port map).
- Roofline ceiling computed without KV-cache reads — intentionally
  overestimated so it only flags truly impossible runs.
- Runs with speculation/MTP/batch>1 are `exempt`, never "fraud".
- Flags are metadata, never deletion. Rationale: `CONTRATO-GLOBAL.md` §1–§6.
