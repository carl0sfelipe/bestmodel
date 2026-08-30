# S28 — Denúncia de run irreal (run_report) + proveniência do import

> Fonte das decisões: dono em 2026-08-31 ("botar eles lá com a fonte de
> onde eu peguei... e deve ter um botão de denunciar run irreal") +
> mecanismo "fake pego" (+5 pontos) registrado no backlog. O import em si
> (S22) JÁ EXISTE e já está no prod (551 claims open, importadas
> 2026-08-26) — aqui se fecha o que falta: proveniência estruturada,
> denúncia com pontos, e o restante das células do pool.

## Objetivo

Quem vê uma claim/run irreal denuncia; a denúncia confirmada vira
mecânica "fake pego" (+5 pontos ao denunciante) e manda a claim para
`refuted`. Nada é removido automaticamente por denúncia — confirmar é
ato de moderação, nunca efeito colateral de um POST.

## Contrato

1. **Migration 0014** (`infra/migrations/0014_run_reports.sql`):
   - tabela `run_report`: `id uuid pk`, `target_kind text` CHECK IN
     ('run_claim','benchmark_run'), `run_claim_id uuid null`, 
     `benchmark_run_id uuid null` (exatamente UM dos dois não-nulo),
     `reporter_user_id uuid null` FK app_user (null = anônimo; anônimo
     nunca pontua), `reason_category text` CHECK IN
     ('numbers_unreal','wrong_hardware','wrong_model','duplicate','other'),
     `reason_detail text` (<=1000 chars), `status text` CHECK IN
     ('open','confirmed','dismissed') default 'open',
     `awarded_at timestamptz null`, `created_at`, `updated_at`.
   - índice parcial único: um reporter sem denúncia `open` duplicada
     para o mesmo alvo.
   - coluna `run_claim.provenance jsonb null` (estruturada: source_url,
     snapshot_at, pool_sha256, importer; null = importado antes da
     coluna existir).

2. **Service** `create_run_report`: alvo tem de existir (404); reporter
   OBRIGATÓRIO (auth — a mecânica de pontos exige identidade); teto de
   taxa (10 denúncias/dia/usuário, mesma janela da S20); nunca altera o
   alvo. `confirm_report`: status=confirmed, awarded_at=now (se
   reporter), claim alvo → status='refuted' (status já existe no CHECK
   da S15). `dismiss_report`: status=dismissed, sem efeito no alvo.

3. **Moderação**: chamador com handle em `MODERATOR_HANDLES` (env,
   vírgula-lista, vazia = ninguém modera). Sem conceito novo de
   admin/role — lista explícita de handles, decisão do dono.

4. **Pontos**: `fetch_contributor_points` passa a somar
   `validated_runs*2 + denúncias confirmadas com awarded_at*5`, nos três
   backends em lockstep (ABC + Fake derivado das runs/report inseridos +
   Postgres).

5. **Rotas** (`report_route.py`): POST `/v1/run-claims/{id}/reports` e
   POST `/v1/runs/{id}/reports` (auth); GET `/v1/reports` e POST
   `/v1/reports/{id}/confirm|dismiss` (moderador). Front-end (botão) vem
   do Claude Design — fora do escopo.

6. **Proveniência do import**: `import_localmaxxing.py` ganha
   `--source-url`/`--snapshot-at` → grava `run_claim.provenance`; o
   import no PROD roda com a fonte real (CanIRunIt pool snapshot
   2026-08-13T02:55:58Z do public API do localmaxxing.com) — dry-run
   antes, --apply depois; backfill honesto das 551 antigas
   (snapshot_at=null com nota "antes da coluna existir").

## Regras

Nao invente numero, prazo ou fonte alem dos listados acima. NUNCA use declare const como workaround — tabela ou coluna inexistente se migra, nao se declara. Nunca enfraquecer teste existente para passar. Fake deriva das linhas inseridas (nunca lista hardcodada). Postgres leg só skipa por psycopg.OperationalError (sem DATABASE_URL) — except largo disfarca infra quebrada.

## Dados verificados

- Prod: 551 run_claim source='localmaxxing' status='open' (importadas
  2026-08-26); pool do CanIRunIt tem 1310 células, snapshotAt
  2026-08-13T02:55:58Z; a diferença (759) é backlog 'nomodel' esperado
  (importer conservador, só mapeia catálogo).
- Tabelas existem: run_claim (CHECK provenance/report já vistos),
  benchmark_run, app_user; padrões de rota = claim_route.py; serviço de
  pontos = fetch_contributor_points (ABC na linha 277ff de
  database_session_provider.py).

## Verificação

VERIFICACAO: uv run pytest tests/test_run_report.py -q (2 backends) e
uv run pytest tests/test_contributor_export.py -q (lockstep de pontos
atualizado) — ambos verdes sem DATABASE_URL no Fake e com DATABASE_URL
no Postgres.

## Oráculo

- comando: uv run pytest tests/test_run_report.py -q
- exit esperado: 0 — antes da implementação, exit 5 (coleção não acha o
  arquivo de teste) é o estado vermelho por design.

## Barra

`infra/scripts/import_localmaxxing.py --dry-run` contra o PROD precisa
reportar: total, existing (551), imported (novas), nomodel — e o apply
carimba provenance. Suíte de referência para padrão de 2 backends:
tests/test_contributor_export.py (S27).
