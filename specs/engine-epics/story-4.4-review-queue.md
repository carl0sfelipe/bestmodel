# Story 4.4 — Fila de revisão: staging → produção com aprovação [Épico 4]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const ou símbolo fantasma: implementação real.
- Staging é IMUTÁVEL diante da revisão: a decisão vive no arquivo de decisões
  (commitável = o "commit de aprovação"); a promoção nunca edita o staging.
- Célula só entra em produção com decisão approved + binding humano; reject
  NUNCA grava nada em produção; id da run é derivado do cell_id (reexecução da
  promoção = ON CONFLICT DO NOTHING, zero duplicatas).
- Nenhuma dependência nova no package (psycopg já é dep do monorepo p/ o
  writer; tests NUNCA tocam rede/banco — writer é exercitado só no oráculo).
- Não invente campo, id, default ou destino fora dos listados.

## Dados verificados (copie SEM ALTERAR)
- VERIFICADO NESTA SESSÃO (PG 16 real): cenário com scenario_kind='declared'
  e TODAS as dims null passa nos CHECKs da 0005 (são condicionais a
  'llm'/'video') — colhida não tem cenário; NÃO criar migração nova.
- Catálogo (seed): ids de runtime são 'llama-cpp' (engine llama_cpp) e
  'comfyui' (engine comfyui); primeiro model_release é
  'model-codestral-22b'; 'gpu-rtx-3090' existe.
- Destino produção: benchmark_run (status 'validated', source_class
  'harvested', source_url, recipe_id quando aplicável) — leaderboard (2.1)
  mostra status='validated' AND source_class IS NOT NULL; métrica decode_tok_s
  → linha em benchmark_metric (enum JÁ contém decode_tok_s, unit 'tok/s');
  seconds_per_clip/it_per_s/frames_per_s → colunas escalares do run.
- Ids determinísticos (namespace 6ba7b810-9dad-11d1-80b4-00c04fd430c8):
  run_id = uuid5("harvested-run:" + cell_id);
  scenario_id = uuid5("harvested-scenario:" + cell_id);
  hardware_id = uuid5("harvested-hardware:" + gpu_model_id);
  recipe_id (de candidato) = uuid5("harvested-recipe:" + candidate_id) —
  vira string 'harv-' + primeiros 12 chars do uuid (id legível e estável).
- Defaults do binding (documentados, sobrescrevíveis pela decisão):
  quantization_profile_id 'q-fp16'; inference_runtime_id 'llama-cpp' para
  células decode_tok_s.
- Formato do arquivo de DECISÕES (JSONL, auditável/commitável):
  {"cell_id"|"candidate_id": str, "decision": "approved"|"rejected",
   "reviewer": str, "decided_at": "YYYY-MM-DD",
   "binding": {"model_release_id": str,
               "quantization_profile_id"?: str, "inference_runtime_id"?: str}}
  — binding obrigatório em approved; campo inteiro ignorado em rejected.

## ENTREGÁVEIS
1. `packages/harvester/src/review_queue.py` (stdlib + psycopg só no writer):
   - `load_decisions(path) -> list[dict]` com ValueError nomeando o problema
     (JSON ruim, decision inválida, approved sem binding.model_release_id,
     decisão duplicada para o mesmo id com decisões conflitantes).
   - `build_promotion_rows(cells_staging: list[dict], candidates_staging: list[dict], decisions: list[dict]) -> PromotionPlan`
     dataclass com: runs (lista de dicts PRONTOS p/ insert_benchmark_run:
     id/hardware_submission_id/model_release_id/quantization_profile_id/
     inference_runtime_id/benchmark_scenario_id/status='validated'/
     client_version='harvester-review-1'/signature='harvested'/
     payload_digest='harvested'/recipe_id|null/seconds_per_clip|it_per_s|
     frames_per_s|null/source_url), scenarios (id, scenario_kind='declared',
     todas as dims null, tensor_parallel 1), hardwares (id, owner
     '00000000-0000-0000-0000-000000000001', gpu_model_id, gpu_count 1,
     ram_gib 1, os 'harvested', os_version 'unverified', environment_snapshot
     {'source_class':'harvested'}), metrics (benchmark_run_id, kind, p50_value,
     unit), recipes (recipe_id/runtime 'comfyui'/workflow_sha256 null/params
     {'width','height','length','steps'} do candidato/model_release_id do
     binding/quantization null/comfyui_version null/author = reviewer).
     Célula decode_tok_s vira linha em metrics; seconds_per_clip vira escalar.
     Partição honesta: approved/rejected/undecided contadas no plano
     (counts) — undecided NUNCA vai a produção.
   - `write_promotion_rows(connection, plan) -> WriteReport(runs_written,
     recipes_written)` — psycopg executando os inserts existentes:
     scenarios/hardware ON CONFLICT DO NOTHING; runs ON CONFLICT (id) DO
     NOTHING; metrics só quando a run foi escrita NESTA execução (retorne do
     INSERT ... RETURNING id; sem RETURNING disponível, conte antes/depois);
     recipes ON CONFLICT (recipe_id) DO NOTHING.
   - `review_summary(cells, candidates, decisions) -> dict` (contagens p/
     relatório humano da fila).
2. `packages/harvester/tests/test_review_queue.py` (>=6, OFFLINE):
   a. load_decisions valida e rejeita os casos ruins (parametrizado);
   b. build_promotion_rows: célula approved com binding gera run com
      source_class 'harvested' + source_url + status validated + ids uuid5
      EXATOS recalculados no teste;
   c. célula decode → metrics row (kind decode_tok_s, unit tok/s);
      célula seconds_per_clip → escalar no run e zero metrics de vídeo;
   d. rejected e undecided não geram rows (counts corretos);
   e. idempotência lógica: mesmo plano 2x → mesmos ids (determinismo);
   f. candidato approved → recipe com id 'harv-<12>' + params do candidato +
      author reviewer; candidato sem binding → ValueError.
3. Sem mudanças em pyproject/harvester.py/migrações.

## COMMIT
(não commitar — sessão principal valida e commita.)

## VERIFICAÇÃO
pytest verde; oráculo abaixo verde (PG REAL descartável: fixture REAL do 4.2
vira célula colhida → decisão approved → produção → leaderboard → reexec
sem duplicar).

## Oraculo
- comando: docker rm -f canirunit-migtest-pg >/dev/null 2>&1; sleep 2; docker run -d --rm --name canirunit-migtest-pg -e POSTGRES_USER=inference_vein -e POSTGRES_PASSWORD=inference_vein -e POSTGRES_DB=inference_vein -p 5439:5432 postgres:16-alpine >/dev/null && sleep 5 && cd ~/Work/CanIRunIt && export DATABASE_URL="postgresql://inference_vein:inference_vein@localhost:5439/inference_vein" && uv run python infra/scripts/migrate.py >/dev/null && uv run python infra/seed/load_seed.py >/dev/null && uv run python -c "import sys, json, tempfile; from pathlib import Path; sys.path.insert(0, 'packages/harvester/src'); sys.path.insert(0, 'packages/domain-schema/src'); sys.path.insert(0, 'packages/roofline-kernel/src'); sys.path.insert(0, 'packages/recommendation-engine/src'); sys.path.insert(0, 'packages/fake-adapters/src'); sys.path.insert(0, 'apps/public-api'); from model_card_harvester import extract_model_card_metrics; from harvester import harvest; from review_queue import load_decisions, build_promotion_rows, write_promotion_rows; import psycopg; fx_dir = Path('packages/harvester/tests/fixtures'); meta = json.loads((fx_dir / 'model-card.meta.json').read_text()); card_fx = extract_model_card_metrics((fx_dir / 'model-card.md').read_text(), meta['source_url'], meta['fetched_at']); p = Path(tempfile.mkdtemp()) / 'f.json'; p.write_text(json.dumps(card_fx)); st = Path(tempfile.mkdtemp()) / 's.jsonl'; harvest(p, st); cells = [json.loads(l) for l in st.read_text().splitlines()]; dec = Path(tempfile.mkdtemp()) / 'decisions.jsonl'; dec.write_text(json.dumps({'cell_id': cells[0]['cell_id'], 'decision': 'approved', 'reviewer': 'carlos', 'decided_at': '2026-08-26', 'binding': {'model_release_id': 'model-codestral-22b'}}) + '\n'); plan = build_promotion_rows(cells, [], load_decisions(dec)); conn = psycopg.connect('postgresql://inference_vein:inference_vein@localhost:5439/inference_vein'); r1 = write_promotion_rows(conn, plan); r2 = write_promotion_rows(conn, plan); conn.close(); assert r1.runs_written == 1 and r2.runs_written == 0, (r1, r2); import subprocess; q = subprocess.run(['docker', 'exec', 'canirunit-migtest-pg', 'psql', '-U', 'inference_vein', '-d', 'inference_vein', '-t', '-A', '-c', \"SELECT source_class || '|' || status || '|' || count(*) FROM benchmark_run WHERE source_class='harvested' GROUP BY source_class, status;\"], capture_output=True, text=True).stdout.strip(); assert q == 'harvested|validated|1', q; print('ORACULO-4.4-OK')" && uv run pytest -q packages/harvester/tests 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && docker rm -f canirunit-migtest-pg >/dev/null && echo ORACULO-4.4-VERDE