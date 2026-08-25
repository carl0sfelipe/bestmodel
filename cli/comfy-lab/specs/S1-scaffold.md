# S1 — Scaffold + probe de hardware

Depende de: nada. Produz: `pyproject.toml`, `src/config.py`,
`src/probe_hardware.py`, `scripts/check.py` (alvo `scaffold`),
`tests/fixtures/system-stats-synthetic.json`, `.gitignore`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `cli/comfy-lab/` — trabalhe
> dentro dele. Leia antes: `cli/comfy-lab/PROMPT-EXECUTOR.md` e
> `cli/comfy-lab/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte
> além dos listados em "Dados verificados". NUNCA use stub/mock como
> workaround de import — importe de verdade. Oráculo verde => atualizar
> ESTADO.md + UM commit `feat(comfy-S1): ...`.

## Objetivo

Projeto uv funcional, constantes do contrato em código, probe de hardware que
lê o `/system_stats` do ComfyUI (vivo) ou explica claramente que o servidor
não está de pé. Nada de lógica de veredito.

## Dados verificados

- Shape do `GET /system_stats` (server.py do clone, l.676-727, 2026-08-12):
  `{"system": {os, comfyui_version, python_version, pytorch_version, ...},
  "devices": [{name, type, index, vram_total, vram_free, torch_vram_total,
  torch_vram_free}]}`. `vram_*` em bytes; `type` = "cuda"|"mps"|etc.
- Porta 8188 livre em 2026-08-12; servidor ainda NÃO instalado (contrato §2).
- Constantes: CONTRATO §6, literais.

## Saídas exatas

- `pyproject.toml` via `uv init --package` ajustado (name `bestmodel-comfy`,
  requires-python `>=3.12`) + `uv add httpx`; layout flat `src/` com
  `packages = ["src"]` via setuptools (mesma solução do pack backend S1).
- `src/config.py` — exatamente as constantes do §6.
- `src/probe_hardware.py` — `fetch_system_stats()` (GET com timeout 2s;
  ConnectError -> mensagem "ComfyUI server not running at <url>" com exit 3)
  e `snapshot_to_file(stats, path)` gravando `data/hardware-snapshot.json`
  com campo extra `"capturedAt"` (ISO) e `"source": "live"`.
- `tests/fixtures/system-stats-synthetic.json` — shape EXATO do dado
  verificado acima, valores claramente sintéticos (`"name": "synthetic-gpu"`)
  e `"source": "synthetic"`. É fixture de shape, nunca de números.
- `scripts/check.py` — CLI com alvos; `scaffold` valida: config importa e
  bate com §6 (comparar COMFY_BASE_URL, RECIPE_VERSION,
  PROVISIONAL_TIGHT_FRACTION); parse da fixture sintética extrai
  devices[0].vram_total como int; alvos desconhecidos -> exit 1 com lista no
  stderr (exit 2 reservado à convenção "oráculo quebrado" do dispatch).
- `.gitignore`: `data/`, `experiments/`, `.venv/`, `__pycache__/`.

## O que NÃO fazer

- Não subir servidor ComfyUI; não criar scan_models/analyze (S2/S3); não
  adicionar deps além de httpx; não criar o node pack (S5).

## Verificação

```bash
uv sync
uv run python scripts/check.py scaffold
uv run python -m src.probe_hardware   # esperado: exit 3 com mensagem clara (servidor ausente)
```

## ORÁCULO

- comando: cd bestmodel-comfy && test -f scripts/check.py && uv run python scripts/check.py scaffold
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: o clone ComfyUI não existir em `/Users/mini/ComfyUI`
(config aponta pra ele) — humano confirma o caminho e atualiza o contrato.
