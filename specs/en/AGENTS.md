# specs/en/ — Map

Executable specs: self-contained objective, deliverables, requirements,
acceptance commands. Phase 0 specs S00–S12 are DONE (acceptance verified at
commit time); L01+ is the active frontier.

| Spec | Status | Built in |
|---|---|---|
| S00-repo-foundation | done | monorepo, Makefile, compose, CI |
| S01-domain-schema | done | packages/domain-schema, contract 0.9.0 |
| S02-database-migrations | done | infra/migrations (15 tables / 8 enums) |
| S03-seed-catalog | done | infra/seed (23 GPU / 57 models / 9 quants / 4 runtimes) |
| S04-vram-feasibility | done | roofline-kernel VRAM + context |
| S05-throughput-prediction | done | roofline-kernel decode/prefill |
| S06-runtime-probes | done | packages/runtime-probes |
| S07-cli-alpha | done | cli/benchmark-probe core |
| S08-cli-sign-upload | done | signing + multipart upload |
| S09-query-submission-api | done | apps/public-api |
| S10-validation-pipeline | done | apps/intake-worker |
| S11-ranking-leaderboard | done | recommendation-engine + filters |
| S12-integration-gate | done | `make gate`, VRAM harness |
| L01-cli-v2-local-lab | PLANNED (Phase 1) | stories L01–L07 inside |
| L02-social-platform | PLANNED (Phase 1) | stories S13–S18 inside |
| L03-engine-unification | DONE (U0–U6, 2026-08-28) | engine port complete: domain schema+kernels (U1), migrations 0011/0012 (U2), comfyui adapter (U3), reported/transparency API (U4), canirunit CLI + harvester (U5); engine lineage frozen as archive |

Rules for new specs: name `<id>-<kebab-title>.md`; include objective, deps,
deliverable paths (exact), requirements, acceptance commands; cite the implementing module or migration files for formulas; where an
original internal design doc was cited, the implemented code/tests win. Register the story
in the release notes as it lands.
