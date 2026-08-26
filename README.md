# bestmodel

**[bestmodel.run](https://bestmodel.run)** — the open compatibility engine for
local AI. Answer three questions for any model on any machine:
**can it run / how fast / is it worth it?**

Not another formula-based estimator. A signed, validated,
community-measured pool feeding a calibrated predictor:

- **measured** — median of many community runs on your exact rig and quantization
- **reported** — one or two community runs on the same rig, shown honestly
- **extrapolated** — scaled by memory bandwidth from the closest tested rig
- **formula** — a published VRAM rule when no measurement exists yet
- **no data yet** — we say so instead of inventing a number

## What's here

| Path | What it is |
|---|---|
| [`apps/public-api/`](apps/public-api) | FastAPI: hardware↔model matching, submission intake, leaderboard |
| [`apps/intake-worker/`](apps/intake-worker) | Anti-fraud pipeline: evidence checks, roofline plausibility, dedup, trust scores |
| [`apps/web/`](apps/web) | The static site at bestmodel.run + its data pipeline |
| [`apps/pool-backend/`](apps/pool-backend) | Pool sync + plausibility curation + local match API |
| [`packages/`](packages) | `domain-schema`, `roofline-kernel` (prediction), `runtime-probes`, `recommendation-engine`, `fake-adapters` |
| [`cli/benchmark-probe/`](cli/benchmark-probe) | Rust measurement agent: detects hardware/runtimes, runs standardized scenarios, signs reports (Ed25519), uploads |
| [`cli/comfy-lab/`](cli/comfy-lab) | Diffusion vertical: ComfyUI probe, workflow analyzer, lab runner |
| [`infra/`](infra) | Docker stack, migrations, seed catalogs, end-to-end gate |
| [`docs/`](docs) | Architecture, calibration findings, backlog, research |
| [`specs/`](specs/en) | Executable specs (S00–S12 done; L01 CLI v2 and L02 social platform planned) |

## Quickstart

```bash
make check-ports   # verify no collision with services already on this machine
make infra-up      # postgres :5434 · redis :6380 · minio :9002-9003 · meilisearch :7701
make migrate       # schema
make seed          # catalog: 23 GPUs × 57 models × 9 quants × 4 runtimes
make test          # full pytest suite
make gate          # end-to-end: CLI signed report → API → worker → leaderboard
```

Requires Docker, Python 3.11+ via [uv](https://docs.astral.sh/uv/), and Rust
(for the CLI).

## How scoring works

1. **VRAM feasibility** — weights + KV-cache footprint per quantization/context.
2. **Throughput** — decode/prefill rooflines calibrated against real
   measurements (P50 error ~6% against the validation corpus).
3. **Trust weighting** — every submission carries Ed25519-signed runtime
   evidence; statistical anomaly detection downweights implausible numbers.

Calibration findings: [`docs/findings.md`](docs/findings.md) ·
Architecture: [`docs/architecture.md`](docs/architecture.md)

## Roadmap

- **L01 — CLI v2 Local Lab**: one-command measured answers on your machine
  ([spec](specs/en/L01-cli-v2-local-lab.md))
- **L02 — Social platform**: accounts, rigs, run claims with community
  plausibility voting, shareable result cards, duels, trending feeds
  ([spec](specs/en/L02-social-platform.md))
- Track B/C details: [`docs/backlog.md`](docs/backlog.md)

## Data sources & attribution

- **localmaxxing.com community pool** — the launch seed of the *claimed*
  track: 551 aggregated cells imported as unverified claims (owner-approved,
  open data). They never enter the leaderboard; the community votes and can
  settle each one with a signed CLI run. Refresh with
  `bash apps/pool-backend/scripts/sync-all.sh` then
  `uv run python infra/scripts/import_localmaxxing.py --apply` (idempotent).
- **HuggingFace model configs** — catalog expansion
  (`infra/scripts/expand_catalog_from_hf.py`) pulls architectural specs
  straight from each model's config.json; nothing is hand-typed.

## License

Hybrid licensing, chosen so the commons stays open and adoption is frictionless:

| Scope | License |
|---|---|
| Platform core (`apps/**`) | [AGPL-3.0](LICENSE) — any network service built on it must stay open |
| Engine & tools (`packages/**`, `cli/**`) | [MIT](LICENSE-MIT) — use them anywhere, including proprietary products |

Commercial hosted inference (managed GPU containers) is offered by the
sponsors of this project under a separate proprietary codebase; it integrates
through public APIs only, as defined in L02.
