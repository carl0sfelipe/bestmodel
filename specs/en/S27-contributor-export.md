# S27 — export por-contribuidor (o contrato consumido pelo The Lineup)

> B-L01 do PLANO-LINEUP (llms.surf docs/go-live/PLANO-LINEUP-2-GOLIVES.md,
> seção "Porta de entrada e medidor"). O contrato do JSON foi congelado
> LÁ (S13): {"generated_at", "contributors": [{"handle", "points",
> "validated_runs"}]} — o workflow do llms.surf consome
> raw.githubusercontent.com/carl0sfelipe/bestmodel/main/data/contributor-export.json.

## Verified data (dados verificados)

- app_user tem handle (find_app_user_by_handle, S25); signing_key.app_user_id
  (S23); benchmark_run.signature_key_id + status='validated' (S23/S26).
- Pontos v0 CONGELADOS AQUI: validated_run = 2 pontos (tabela do plano:
  signed_run=2). Categorias futuras (reprodução=3, fake=5, mode=2) entram
  como campos extras quando o produto passar a modelá-las — não existem hoje.
- Padrão da casa: Fake deriva das linhas inseridas (S26 — nunca fixture
  manual); perna Postgres roda no make gate (DATABASE_URL @5434); sem env,
  pytest.skip (padrão test_signing_keys.py).

Do not invent (nao invente) campos ou números além dos listados (alem
destes). NUNCA use declare const — o SQL e o Fake leem as linhas reais.

## Work

1. DatabaseSession (ABC) + PostgresSession + FakeDatabase:
   `fetch_contributor_points() -> list[dict]` — rows
   {"handle", "points", "validated_runs"}, points = validated_runs × 2,
   ORDER BY points DESC, handle. Só quem tem ≥1 run validada assinada.
2. infra/scripts/export-contributors.py (executável): DATABASE_URL →
   psycopg → escreve data/contributor-export.json (pretty + newline).
   Exit não-zero se DATABASE_URL ausente ou inacessível — fail loud.
3. tests/test_contributor_export.py: Fake — 2 usuários (ana 2 runs
   validadas, bruno 1) + 1 run NÃO validada fora da conta; contrato exato
   das chaves; ordem por pontos. Postgres: mesmo assert, skip sem env.

## Do not touch

benchmark_run/signing_key schemas, rotas, leaderboard (S26), web, Vast.
A Action consumidora já existe no llms.surf (workflow lineup.yml).

## Verificação

VERIFICACAO: grep -q "fetch_contributor_points" apps/public-api/src/dependencies/database_session_provider.py

## Barra

Novas categorias de contribuição entram aqui como campos extras do export
sem quebrar o contrato — chaves novas, nunca chaves renomeadas.

## Oráculo

- comando: uv run pytest tests/test_contributor_export.py --quiet && test -x infra/scripts/export-contributors.py
- exit esperado: 0 — contrato pinado nos 2 backends e o exportador existe
  executável. Antes: 127 = vermelho por design.
