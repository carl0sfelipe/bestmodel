# S02 — PostgreSQL Database Migrations (Hardware / Model / Benchmark / Trust Tables)

## Objective

Create, in order, all PostgreSQL enum types and tables specified in Section 10 (from the original internal design doc), establishing the MVP persistence skeleton that serves as the foundation for S03 seed loading as well as the subsequent benchmark, trust, and leaderboard features.

## Dependencies

- S00 (provides `make migrate`, docker-compose Postgres, and the `DATABASE_URL` convention)

## Wave

W1

## Deliverables

- `infra/migrations/0001_create_hardware_catalog.sql`
- `infra/migrations/0002_create_model_catalog.sql`
- `infra/migrations/0003_create_benchmark_tables.sql`
- `infra/migrations/0004_create_trust_tables.sql`

## Technical Requirements

The SQL must be copied verbatim from Section 10 (from the original internal design doc) (including all column names, types, constraints, defaults, and enum values); no additions, deletions, or renames are allowed.

Per-file mapping:

| File | CREATE TYPE | CREATE TABLE / INDEX | Corresponding Plan Section |
|---|---|---|---|
| 0001_create_hardware_catalog.sql | hardware_class | gpu_model, cpu_model, hardware_submission, gpu_topology_link | 10.1–10.3 |
| 0002_create_model_catalog.sql | model_architecture, quant_format, kv_cache_format, runtime_engine | model_release, quantization_profile, inference_runtime | 10.4–10.6 |
| 0003_create_benchmark_tables.sql | benchmark_status, metric_kind, artifact_kind | benchmark_scenario, benchmark_run, benchmark_metric, benchmark_artifact, benchmark_run_lookup_idx | 10.7–10.10 |
| 0004_create_trust_tables.sql | (no new types) | trust_assessment, model_quality_evaluation, price_quote, roi_assumption | 10.11–10.13 |

Other requirements:

- Each file starts with `BEGIN;` and ends with `COMMIT;`.
- Within each file, `CREATE TYPE` must come before `CREATE TABLE` (types must precede their use).
- Foreign key order must be correct: `hardware_submission` → `gpu_model`/`cpu_model`; `gpu_topology_link` → `hardware_submission`; `benchmark_run` → `hardware_submission`/`model_release`/`quantization_profile`/`inference_runtime`/`benchmark_scenario`; `trust_assessment` → `benchmark_run`.
- The migration runner from S00 records applied versions, so repeated `make migrate` is idempotent.
- Files are UTF-8 encoded.

## Acceptance Criteria

1. Run `make migrate` on a clean database; exit code is 0.
2. Run `make migrate` again; exit code is 0 (already-applied migrations are skipped via the version table, idempotent).
3. Table list:

   ```bash
   psql "$DATABASE_URL" -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
   ```

   The output must be exactly the following 15 tables: `gpu_model, cpu_model, hardware_submission, gpu_topology_link, model_release, quantization_profile, inference_runtime, benchmark_scenario, benchmark_run, benchmark_metric, benchmark_artifact, trust_assessment, model_quality_evaluation, price_quote, roi_assumption`
4. Enum types:

   ```bash
   psql "$DATABASE_URL" -Atc "SELECT typname FROM pg_type WHERE typtype='e' ORDER BY typname;"
   ```

   Contains exactly 8: `hardware_class, model_architecture, quant_format, kv_cache_format, runtime_engine, benchmark_status, metric_kind, artifact_kind`
5. Enum value spot check:

   ```bash
   psql "$DATABASE_URL" -Atc "SELECT unnest(enum_range(NULL::quant_format));"
   ```

   Outputs 14 values: `fp16, bf16, fp8, int8, int4, awq, gptq, exl2, gguf_q2, gguf_q3, gguf_q4, gguf_q5, gguf_q6, gguf_q8`

## Notes

- Code, SQL comments, and commit messages must all be in English.
- This story creates no objects outside the plan and makes no simplifications to tables or columns.
- Do not run git commit.
