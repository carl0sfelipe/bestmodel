# S6 — Operação (fluxo único + smoke)

Depende de: S5. Produz: `scripts/sync-all.sh`, `scripts/run.sh`, alvo `ops`,
seção "Operação" no README do pack.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/pool-backend/` — trabalhe
> dentro dele. Leia antes: `apps/pool-backend/PROMPT-EXECUTOR.md` e
> `apps/pool-backend/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte
> além dos listados em "Dados verificados"; o que faltar fica [A DEFINIR].
> NUNCA use stub/`declare const`/mock como workaround de import — importe de
> verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(backend-S6): ...`; mate qualquer servidor que subir
> (`pkill -f "uvicorn.*8790"`).

## Objetivo

Amarrar o ciclo inteiro num comando (sync -> flags -> derived -> publish) e
deixar o serviço iniciável/parável sem sustos na máquina compartilhada.

## Dados verificados

- Porta e constantes: CONTRATO §3/§5. Ciclo e ordem: specs S2-S4.
- Agendamento automático é [A DEFINIR] (CONTRATO §9) — fica de fora; o
  comando manual é o entregável.

## Saídas exatas

- `scripts/sync-all.sh`: `set -euo pipefail`; roda sync_pool, plausibility,
  derive_export `--publish`, e imprime resumo de 4 linhas (runs, flags por
  verdict, arquivos publicados, duração). Exit != 0 se qualquer etapa falhar.
- `scripts/run.sh`: sobe uvicorn na API_PORT com `--log-level warning`;
  recusa subir se a porta estiver ocupada (mensagem com o PID ocupante).
- Alvo `ops` no check.py: sync-all.sh existe e é executável; run.sh idem;
  `bash -n` passa nos dois; após um ciclo completo, healthz reporta
  `runs > 0` e `lastSyncAt` não-nulo (TestClient).
- README do pack ganha a seção "Operação" (comandos acima + como parar:
  `pkill -f "uvicorn.*8790"`).

## Spec

1. sync-all.sh NÃO reinicia o serviço; SQLite em WAL para leitura concorrente
   (PRAGMA journal_mode=WAL no connect() — ajuste em db.py permitido nesta
   sessão, 1 linha).
2. Nenhum output colorido/emoji; texto puro, uma informação por linha.

## O que NÃO fazer

- Não instalar cron/launchd; não criar systemd/Docker; não adicionar
  monitoramento — v1 é operação manual documentada.
- Não tocar no pack web além do que a S4 já permite (--publish).

## Verificação

```bash
bash scripts/sync-all.sh
uv run python scripts/check.py ops
uv run python scripts/check.py all      # regressão completa do pack
```

## ORÁCULO

- comando: cd bestmodel-backend && test -f scripts/sync-all.sh && uv run python scripts/check.py ops
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: o dono quiser agendamento automático (decisão de
cron/launchd na máquina compartilhada é dele) ou se o ciclo completo passar
de 10 min (throttle pode precisar de revisão conjunta).
