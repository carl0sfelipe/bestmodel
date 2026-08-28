# Story 2.1 — source_class no leaderboard/API + badge (fatia API) [Épico 2]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Célula SEM source_class NÃO renderiza (nem na API, nem depois no site).
- As 4 classes canônicas: measured_signed | reported | harvested | derived
  (NÃO inventar quinta classe; roofline_transfer herda "derived" no badge v1).
- Não invente número, campo, flag ou fonte além dos listados.

## Dados verificados (copie SEM ALTERAR)
- Classes do PRD FR-3: measured_signed (assinada pelo CLI), reported (comunidade
  autenticada), harvested (harvester determinístico), derived (transferência
  roofline). Default pós-backfill = measured_signed (Story 1.3, migração 0005).
- Colunas criadas em 0005: benchmark_run.{source_class, recipe_id,
  seconds_per_clip, it_per_s, frames_per_s, source_url}.
- Contrato atual do leaderboard: GET /v1/leaderboard (apps/public-api),
  fetch_leaderboard_entries em database_session_provider, ranking em
  calculate_ranking_score (recommendation-engine) — estes NÃO mudam.

## ENTREGÁVEIS (fatia API; o badge visual do site é pack executor à parte)
1. `fetch_leaderboard_entries` (PostgresSession): SELECT += run.source_class,
   run.recipe_id, run.seconds_per_clip, run.it_per_s, run.frames_per_s;
   WHERE += run.source_class IS NOT NULL.
2. `query_leaderboard`: dropa entrada sem source_class (defesa em profundidade
   + paridade com FakeDatabase); _coerce_numeric cobre as 3 métricas vídeo;
   filtros exatos novos: source_class, recipe_id.
3. Rota: query params source_class e recipe_id.
4. Testes: entrada com source_class aparece com o campo; entrada SEM
   source_class não aparece; filtro por classe funciona; métricas vídeo
   coercionadas a float.

## COMMIT
apps/public-api + specs/ com identidade dev@local.

## VERIFICAÇÃO
uv run pytest verde; oráculo abaixo verde.

## Oraculo
- comando: cd ~/Work/CanIRunIt && uv run pytest -q apps/public-api/tests/test_leaderboard_route.py apps/public-api/tests/test_submission_route.py 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && uv run pytest -q 2>&1 | tail -1 | grep -qE '^[0-9]+ passed'
