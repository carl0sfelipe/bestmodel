# infra/seed — Map

Seed catalogs loaded by BOTH backends: FakeDatabase reads these JSONs at
construction (`_load_seed`) and `make seed` loads them into Postgres. They
are the shared vocabulary of every fixture id (q-fp16, llama-cpp,
gpu-rtx-3090, gpu-a6000…).

| File | What it shapes |
|---|---|
| `gpu_models.json` | gpu ids + vram_mib (feeds leaderboard `vram_capacity_mib`) |
| `model_releases.json` | model ids referenced by runs and fixtures |
| `quantization_profiles.json` | quant ids + weight_format + expected_quality_retention (leaderboard derives these — never hand-copy them into tests) |
| `inference_runtimes.json` | runtime ids + engine names (run rows store the ID; the engine name is derived) |

## Change checklist

- Add/edit a seed id? Same commit: the FakeDatabase loads it automatically,
  but every fixture/test that references the OLD id breaks loudly — run
  `make test` and migrate them; `make seed` to refresh Postgres.
- New catalog file? Wire it into FakeDatabase `_load_seed` AND the seed
  script — a file only one backend reads is the fake==fake disease again.
- Renaming an id is a breaking change: ids are stored in run rows and
  referenced by migrations' seed rows (0011 recipe).

## Load-bearing decisions

- Seeds are the single vocabulary: tests must reference seed ids (real
  gpu/quant/runtime ids), never invent fictional ones — the S26 derivation
  made fictional ids visible as broken filters.
- `expected_quality_retention` lives HERE, not in test entries: the
  leaderboard derives it from the seed via the quant join.
