# apps/intake-worker — Map

Async validation worker consuming Redis stream `benchmark_runs` (group
`intake-workers`). Status machine: submitted → validated | quarantined | rejected.

| Module | Stage | Notes |
|---|---|---|
| `worker.py` | orchestrator | `process_run` pipeline order: validate → evidence → plausibility → dedupe → z-score → trust → ranking update; `run_worker_loop`/`main` for real mode; hydrates minimal events via repository |
| `validate_submission_payload.py` | §12.6 rejections | signature flag, schema version, runtime version, fingerprint shape, duration CONSISTENCY rule (finding F6), artifact hash mismatch |
| `extract_runtime_evidence.py` | §12.2 | parses `metric <name> <value>` evidence lines; rejects missing/inconsistent |
| `check_roofline_plausibility.py` | §12.3 | decode > 0.92 × roofline → `roofline_violation` (calibration open — finding F2) |
| `check_memory_plausibility.py` | §12.3 | peak < 0.80 × predicted → `impossible_memory_footprint` |
| `detect_duplicate_submission.py` | §12.4 | dimension group (hw model, model, quant, engine, ctx, batch) vs validated/quarantined |
| `calculate_modified_zscore.py` | §12.4 | MAD z-score; |z|>3.5 → `statistical_outlier`; MAD==0/peers<3 → skip |
| `calculate_trust_assessment.py` | §11.9 | weighted subscores [0,1]; outlier flags attached |
| `publish_ranking_update.py` | §11 | stream `ranking_updates` |
| `postgres_repository.py` | persistence | hydrates run payloads from DB+vault (decision D7); trust/status writes |
| `worker_models.py` | data model | `RunRecord`, `DimensionGroup`, builders |

Ops: flat imports need `PYTHONPATH=src`; `__init__.py` bootstraps domain/root
paths. Kill stale workers before debugging (`pkill -f "src.worker"` — incident I3).
Roofline checks SKIP when hardware is unbound (community rows) — documented.

## Change checklist

- Campo novo de run/scenario ⇒ `fetch_run_payload`/`_assemble_payload` aqui é
  a hidratação: se não ler a coluna, o worker nunca vê o valor — teste
  unitário com fake NÃO pega isso (finding F8); rode `make gate`.
- CLI passa a emitir métrica/campo novo ⇒ evidence keys
  (`EVIDENCE_METRIC_KEYS`/`VIDEO_METRIC_KEYS` em `extract_runtime_evidence.py`)
  e a checagem de duração em `validate_submission_payload.py` na mesma commit.
- Dimensão de dedupe (`_group_where` + `DimensionGroup`) ⇄ índice único da API
  (5-dim) ⇄ §12.4 (6-dim): os dois níveis de dedupe precisam seguir juntos.
- Status machine é `submitted → validated | quarantined | rejected`; nunca
  UPDATE de status fora do worker em caminho de prod.
