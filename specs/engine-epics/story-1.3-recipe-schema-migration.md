# Story 1.3 — Schema: recipe + recipe_id/source_class no run + migração [Épico 1]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Migração DEVE ser idempotente por construção (IF NOT EXISTS + DO blocks), não
  só pelo ledger de arquivos do migrate.py.
- Report LLM 0.9.0 permanece aceito BYTE-IDÊNTICO (campos novos todos opcionais);
  cenário vídeo NUNCA reutiliza campos de token (AD-1) — tem campos próprios.
- Backfill null-safe: nenhum dado existente pode ser perdido ou rejeitado.
- Não invente número, flag, coluna ou fonte além dos listados abaixo.

## Dados verificados (copie SEM ALTERAR)
- SPINE §3 (aprovado 27/08): CREATE TABLE recipe (recipe_id PK, runtime,
  workflow_sha256, params JSONB, model_release_id, quantization_profile_id,
  comfyui_version, author, created_at); benchmark_run += recipe_id FK,
  source_class default 'measured_signed', seconds_per_clip, it_per_s,
  frames_per_s, source_url.
- Constraints CHECK existentes (0003): benchmark_scenario.prompt_tokens>=0,
  generated_tokens>0, context_tokens>0, batch_size>0.
- PG enum runtime_engine (0002) tinha 8 valores; comfyui entra via
  ALTER TYPE ... ADD VALUE IF NOT EXISTS (permitido em txn PG>=12; seed roda em
  txn própria depois).
- FK recipe: id correto é 'wan22-flf2v-720p-81f-v1' (FLF2V, v de video) —
  typo flf2f FOI TESTADO e o FK rejeita (verificação negativa intencional).

## ENTREGÁVEIS
1. `infra/migrations/0005_recipe_and_video.sql`: ALTER TYPE comfyui; recipe;
   seed da recipe v1 (ON CONFLICT DO NOTHING); benchmark_run += 6 colunas;
   backfill source_class; benchmark_scenario vídeo (scenario_kind, width,
   height, frames, steps, cfg, shift, seed) com tokens NULLable + CHECKs
   condicionais (llm exige tokens; video exige dims/frames/steps) em DO blocks.
2. `packages/domain-schema`: RuntimeEngine+comfyui; MetricKind+3 vídeo;
   BenchmarkMetrics: peak_vram_mib ge=0 (0 válido p/ vídeo sem nvidia-smi;
   negativo rejeitado) + 3 campos vídeo Option; VideoScenario (kind explícito);
   BenchmarkReport.recipe_id opcional; schema export regenerado.
3. `apps/public-api`: SubmissionForm.recipe_id; intake resolve recipe (report
   assinado vence; desconhecido = 400); insert run com recipe_id/source_class/
   escalares vídeo; scenario record vídeo/llm; FakeDatabase.fetch_recipe_by_id
   + seed espelhado.
4. `cli/benchmark-probe` (Rust): ScenarioPayload untagged (Llm|Video);
   VideoScenarioFields; BenchmarkReportPayload.recipe_id opcional
   (skip_serializing_if); video report carrega recipe_id + cenário vídeo real.
5. Seed: inference_runtimes.json += comfyui 0.3.48.
6. Testes: contrato enums/metrics atualizados; 3 testes novos de submissão
   vídeo (202 + persistidos; recipe desconhecida 400; LLM sem recipe aceito);
   suite Python e Rust verdes.

## COMMIT
infra/ + packages/ + apps/ + cli/ + specs/ com identidade dev@local.
OPS: prod exige `migrate.py` + `load_seed.py` (comfyui runtime) na próxima subida.

## VERIFICAÇÃO
Oráculo abaixo verde (container PG descartável: migrate 2× + re-apply cru +
recipe presente + suites). GET de run: NÃO existe endpoint GET /v1/runs —
persistência comprovada nos testes de intake (FakeDatabase) e no SELECT do
oráculo; endpoint público fica para o Épico 5 (comunidade).

## Oraculo
- comando: docker rm -f canirunit-migtest-pg >/dev/null 2>&1; sleep 2; docker run -d --rm --name canirunit-migtest-pg -e POSTGRES_USER=inference_vein -e POSTGRES_PASSWORD=inference_vein -e POSTGRES_DB=inference_vein -p 5439:5432 postgres:16-alpine >/dev/null && sleep 5 && cd ~/Work/CanIRunIt && export DATABASE_URL="postgresql://inference_vein:inference_vein@localhost:5439/inference_vein" && uv run python infra/scripts/migrate.py | tail -1 | grep -qx 'applied 0005_recipe_and_video.sql' && uv run python infra/scripts/migrate.py | grep -q 'no pending migrations' && docker exec -i canirunit-migtest-pg psql -U inference_vein -d inference_vein -v ON_ERROR_STOP=1 < infra/migrations/0005_recipe_and_video.sql >/dev/null 2>&1 && docker exec canirunit-migtest-pg psql -U inference_vein -d inference_vein -t -A -c "SELECT count(*) FROM recipe WHERE recipe_id='wan22-flf2v-720p-81f-v1';" | grep -qx 1 && uv run pytest -q 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && cd cli/benchmark-probe && PATH="$HOME/.cargo/bin:$PATH" cargo test -q 2>&1 | grep -c 'test result: ok' | grep -qx 8 && cd ~/Work/CanIRunIt && docker rm -f canirunit-migtest-pg >/dev/null && echo ORACULO-1.3-VERDE
