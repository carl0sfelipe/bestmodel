# S1 — Scaffold do serviço

Depende de: nada. Produz: `pyproject.toml`, `src/config.py`, `src/main.py`,
`scripts/check.py` (alvo `scaffold`), `.gitignore`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/pool-backend/` — trabalhe
> dentro dele. Leia antes: `apps/pool-backend/PROMPT-EXECUTOR.md` e
> `apps/pool-backend/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte
> além dos listados em "Dados verificados"; o que faltar fica [A DEFINIR].
> NUNCA use stub/`declare const`/mock como workaround de import — importe de
> verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(backend-S1): ...`; mate qualquer servidor que subir
> (`pkill -f "uvicorn.*8790"`).

## Objetivo

Projeto uv funcional com FastAPI de pé, constantes do contrato em código e o
oráculo único nascendo. Nada de lógica de negócio.

## Dados verificados

- Porta 8790 livre em 2026-08-12; lista de portas proibidas: CONTRATO §3.
- uv disponível na máquina (monorepo hospedeiro roda inteiro via uv).
- Constantes: CONTRATO §5, literais.

## Saídas exatas

- `pyproject.toml` via `uv init --package` ajustado (name
  `bestmodel-backend`, requires-python `>=3.12`) + `uv add fastapi uvicorn httpx`.
- `src/config.py` — exatamente as constantes do §5.
- `src/main.py` — app FastAPI com `GET /healthz` retornando
  `{"ok": true, "runs": 0, "lastSyncAt": null}` enquanto não houver banco
  (S2 troca a fonte).
- `scripts/check.py` — CLI com alvos; `scaffold` valida: config importa e bate
  com §5 (comparar 3 valores: API_PORT, SUSPICIOUS_FRACTION, THROTTLE_MS);
  `/healthz` responde 200 via `fastapi.testclient` (sem subir servidor).
- `.gitignore`: `data/`, `out/`, `.venv/`, `__pycache__/`.

## Spec

1. `uv sync` deve deixar o projeto rodável; `uv run python -c "import src.main"`
   sem erro (usar layout src/ com packages configurado no pyproject).
2. `check.py` usa apenas stdlib + deps do §2; alvos desconhecidos -> exit 1
   com lista de alvos válidos no stderr (exit 2 é reservado para "oráculo
   quebrado" na convenção do dispatch — nunca usar); `all` roda a lista
   interna (por ora, só `scaffold`).

## O que NÃO fazer

- Não criar endpoints além de /healthz; não criar db.py (S2); não adicionar
  deps além das três do contrato; não configurar CORS/logging elaborado.

## Verificação

```bash
uv sync
uv run python scripts/check.py scaffold
uv run uvicorn src.main:app --port 8790 &   # smoke manual
curl -s localhost:8790/healthz; pkill -f "uvicorn.*8790"
```

## ORÁCULO

- comando: cd bestmodel-backend && test -f scripts/check.py && uv run python scripts/check.py scaffold
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: 8790 estiver ocupada no momento da verificação (conflito
novo na máquina — humano escolhe outra porta e atualiza o contrato).
