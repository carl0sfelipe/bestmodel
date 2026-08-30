# packages/domain-schema — Map

Contract + domain models (Pydantic v2). Everything else depends on this.

| Module | Content |
|---|---|
| `benchmark_report.py` | `BenchmarkReport` root (contract 0.9.0), enums RuntimeEngine/ArtifactKind; runtime coercion `llama.cpp`→`llama_cpp` (intentional) |
| `benchmark_metrics.py` | metrics + `MetricKind` enum (incl. reserved kinds: peak_ram_mib, temperature_c_max, energy_joule) |
| `benchmark_scenario.py` | scenario (prompt/generated/batch/context) |
| `gpu_spec.py` / `cpu_spec.py` | hardware specs (plan §10.1) |
| `model_arch.py` | model + `ModelArchitecture` (dense/moe/multimodal) |
| `quant_profile.py` | quant + `QuantFormat` (14 values) + `KvCacheFormat` |
| `schema/benchmark_report.v0.9.0.json` | versioned exported JSON Schema (regenerate + bump version on contract change) |

Tests pin: the §9.3 example report parses verbatim; constraint violations raise;
enum values exact; exported schema matches `model_json_schema()`.
Contract evolution: 0.9.1 additive blocks (`statistics`/`tuning`/`spec_decode`/
`peak_ram_mib`) — spec `specs/en/L01-cli-v2-local-lab.md` §contract.

## Change checklist

- Mexeu num campo do shape de run/scenario? A fonte única é `src/run_record.py`
  (`BenchmarkRunRecord`/`BenchmarkScenarioRecord`). Na mesma commit: a migration
  nova (append-only, `infra/migrations/`), os INSERTs/SELECTs do
  `PostgresSession`, o `FakeDatabase` (valida contra o modelo) e o round-trip
  `tests/test_session_video_roundtrip.py`. `make test` precisa passar antes do
  commit; `make gate` (perna de vídeo) se a coluna entra na leaderboard.
- Novo kind de métrica: `MetricKind` aqui + `METRIC_UNITS` no
  `submit_benchmark_run.py` + evidence keys no worker — chave sem unidade é
  silenciosamente descartada no insert.
- Vídeo é run scalar, nunca `benchmark_metric` row (AD-1) — não "conserte"
  movendo `seconds_per_clip` para métricas.
- Contract 0.9.0 (`benchmark_report.py`) é congelado; evolução = bloco aditivo
  0.9.x + spec, nunca edição silenciosa (spec L06/S26).
