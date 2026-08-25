# S03 — Seed Data Catalog (GPU / Model / Quantization / Runtime)

## Objective

Load a queryable seed catalog: ≥20 GPUs, ≥50 models, quantization profiles covering the Section 11.8 loss table, and 4 runtimes, written via an idempotent script into the database tables created in S02, satisfying the Phase 0 exit criterion of "50 models × 20 GPUs queryable."

## Dependencies

- S02 (migration table creation: gpu_model, model_release, quantization_profile, inference_runtime)

## Wave

W2

## Deliverables

- `infra/seed/gpu_models.json`
- `infra/seed/model_releases.json`
- `infra/seed/quantization_profiles.json`
- `infra/seed/inference_runtimes.json`
- `infra/seed/load_seed.py`
- Makefile target `make seed`

## Technical Requirements

### GPU (≥20 entries, written to gpu_model, fields correspond to Section 10.1)

JSON array, object fields: `id, vendor, marketing_name, vram_mib, memory_bandwidth_gib_s, fp16_tflops, int8_tops, tdp_watt, pcie_generation, pcie_lane_width, supports_nvlink, released_at`

- Constraints: `vram_mib > 0`, `memory_bandwidth_gib_s > 0`, `tdp_watt > 0`
- Cover mainstream cards, e.g. RTX 4090 / 4080 / 3090 / 3080, A100 40/80GB, A6000, L40S, RTX 6000 Ada, RTX 3060, etc.

### Model (≥50 entries, written to model_release, fields correspond to Section 10.4)

JSON array, object fields: `id, family, release_name, architecture, parameter_count_billion, active_parameter_count_billion, num_layers, hidden_size, num_attention_heads, num_kv_heads, head_dim, expert_count, experts_per_token, max_context_tokens, released_at`

- Cover families: qwen-2.5-coder, qwen-2.5, llama-3, deepseek-r1, mistral, mixtral, etc.
- MoE (`architecture='moe'`) requires at least 3 entries, all of which must fill in `active_parameter_count_billion`, `expert_count`, `experts_per_token` (for the Section 11.2 active-weights formula)

### Quantization profile (≥8 entries, written to quantization_profile, mapped from the Section 11.8 loss table)

`expected_quality_retention = 1 − loss midpoint`:

| id | display_name | weight_format | weight_bits | Loss range (11.8) | retention |
|---|---|---|---|---|---|
| q-fp16 | FP16 | fp16 | 16 | 0.000 | 1.0000 |
| q-bf16 | BF16 | bf16 | 16 | 0.000 | 1.0000 |
| q-fp8 | FP8 | fp8 | 8 | 0.005–0.015 | 0.9900 |
| q-awq-int4 | AWQ INT4 | awq | 4 | 0.010–0.035 | 0.9775 |
| q-gptq-int4 | GPTQ INT4 | gptq | 4 | 0.015–0.045 | 0.9700 |
| q-exl2-4.0bpw | EXL2 4.0bpw | exl2 | 4 | 0.015–0.050 | 0.9675 |
| q-gguf-q4-k-m | GGUF Q4_K_M | gguf_q4 | 4.5 | 0.020–0.060 | 0.9600 |
| q-gguf-q3-k-m | GGUF Q3_K_M | gguf_q3 | 3.5 | 0.050–0.120 | 0.9150 |
| q-gguf-q2-k | GGUF Q2_K | gguf_q2 | 2.5 | 0.120–0.300 | 0.7900 |

- `kv_cache_format` defaults to `'fp16'` and `kv_cache_bits` to 16; `group_size` may be null

### Runtime (≥4 entries, written to inference_runtime, engine uses the runtime_engine enum)

| id | engine | supports_tensor_parallel | supports_kv_cache_quant | supports_cpu_offload |
|---|---|---|---|---|
| llama-cpp | llama_cpp | false | true | true |
| ollama | ollama | false | true | true |
| vllm | vllm | true | true | false |
| exllamav2 | exllamav2 | false | true | false |

- `version` is non-empty, satisfying the `UNIQUE(engine, version)` constraint

### Load script load_seed.py

- Uses psycopg (or SQLAlchemy), reading `infra/seed/*.json`
- Writes in order: gpu_model → model_release → quantization_profile → inference_runtime
- Idempotent: `INSERT ... ON CONFLICT (id) DO NOTHING` (id is a deterministic primary key)
- Database connection reads the `DATABASE_URL` environment variable
- The script, JSON files, comments, and commit messages must all be in English

### Makefile

- `make seed`: depends on `make migrate`, executes `uv run python infra/seed/load_seed.py`

## Acceptance Criteria

1. `make migrate && make seed`, exit code is 0.
2. Idempotent: run `make seed` twice consecutively; both exit codes are 0 and counts are unchanged.
3. Counts:

   ```bash
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM gpu_model;"            # >= 20
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM model_release;"        # >= 50
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM quantization_profile;" # >= 8
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM inference_runtime;"    # >= 4
   ```

4. Field completeness (each count must equal the total row count of the corresponding table):

   ```bash
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM gpu_model WHERE vram_mib > 0 AND memory_bandwidth_gib_s > 0 AND tdp_watt > 0;"
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM model_release WHERE num_layers > 0 AND num_kv_heads > 0 AND head_dim > 0 AND max_context_tokens > 0;"
   ```

5. MoE completeness:

   ```bash
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM model_release WHERE architecture='moe';"  # >= 3
   psql "$DATABASE_URL" -Atc "SELECT count(*) FROM model_release WHERE architecture='moe' AND active_parameter_count_billion IS NOT NULL;"  # equals the above
   ```

6. Spot-check queries return meaningful results:

   ```bash
   psql "$DATABASE_URL" -c "SELECT marketing_name, vram_mib, memory_bandwidth_gib_s FROM gpu_model ORDER BY vram_mib DESC LIMIT 5;"
   psql "$DATABASE_URL" -c "SELECT id, expected_quality_retention FROM quantization_profile ORDER BY expected_quality_retention DESC;"
   ```

   `expected_quality_retention` falls within the [0.70, 1.00] range, and the descending order matches the Section 11.8 loss table.

## Notes

- The seed data is a "queryable skeleton"; values need only be plausible and need not match real-world benchmarks; later correction is handled by benchmark backfill.
- Do not run git commit.
