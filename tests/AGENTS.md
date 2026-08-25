# tests/ — Map

Root-level suites (package-local tests live under each package/app). Added here
when they cross package boundaries or assert system-level properties.

| Path | Content |
|---|---|
| `test_smoke.py` | trivial guard so `make test` always has a root test |
| `integration/test_e2e_submission_flow.py` | submission chain with fake adapters: signed report → intake 202 → worker validates → leaderboard entry appears |
| `regression/vram_error_harness.py` | **the calibration corpus** — measured (config → peak VRAM) pairs; run with `uv run python -m tests.regression.vram_error_harness` |
| `regression/test_vram_error_harness.py` | asserts P50 error < 10% (Phase 0 exit criterion) |

Rules: only ADD measured entries to the harness corpus, never remove or weaken;
the corpus is the scarcest asset in this repo (`__init__.py` files exist so the
suites run both via pytest and `python -m`).
