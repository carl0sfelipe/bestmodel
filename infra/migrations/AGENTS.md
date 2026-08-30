# infra/migrations — Map

Append-only SQL migrations applied by `scripts/migrate.py` via `make migrate`
(versioned in `meta.schema_migrations`; a file is applied once and never
re-edited — the next change is the next number).

| File | What it shapes |
|---|---|
| `0001–0002` | hardware + model catalogs (gpu_model, cpu_model, model_release, quantization_profile, inference_runtime, hardware_submission) |
| `0003` | benchmark_run / benchmark_scenario / benchmark_metric / benchmark_artifact + status & kind enums |
| `0004–0010` | trust, social identity, auth, rigs, claims/votes, follows, imported claims |
| `0011` | recipe table + video columns on run/scenario (recipe_id, source_class, seconds_per_clip, it_per_s, frames_per_s, source_url; scenario width/height/frames/steps/cfg/shift/seed) — seeds the wan22 recipe row |
| `0012` | contributor + reported submission log |

## Change checklist

- Migration aplicada NUNCA é editada — mudança nova = arquivo novo com o
  próximo número; `0011` usa `IF NOT EXISTS`/`DO blocks` como referência de
  idempotência quando algo precisar ser re-executável.
- Coluna nova em `benchmark_run`/`benchmark_scenario` ⇒ na MESMA commit:
  `packages/domain-schema/src/run_record.py` (fonte única do shape),
  `PostgresSession` (INSERT + SELECTs), `FakeDatabase` (valida contra o
  modelo), linha do round-trip `tests/test_session_video_roundtrip.py`.
  `make test` verde antes do commit; `make gate` (perna de vídeo) se a coluna
  afeta intake/leaderboard — "uploading a video cell requires the schema
  deployed" (precondition, not schedule).
- `metric_kind`/`artifact_kind`/`runtime_engine` ainda são enums SQL (0003,
  0011): valor novo custa migration + código — S26 os substitui por catalog
  tables (direção D2.4); não acrecente enum por capricho.
- `source_class` é TEXT com DEFAULT 'measured_signed' (0011): ladder aberta de
  classes, não enum.
- Seeds que acompanham schema (ex.: recipe do wan22 dentro do 0011) existem em
  duplicata no `FakeDatabase` — mexer num lado = mexer no outro.
