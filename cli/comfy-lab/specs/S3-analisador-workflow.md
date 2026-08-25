# S3 — Analisador de workflow ("roda nesta máquina?")

Depende de: S1, S2. Produz: `src/analyze_workflow.py`, alvo `analyze` no
check.py, `tests/fixtures/workflow-basic.json`,
`tests/fixtures/workflow-unmapped.json`.

> Contexto de execução (dispatch): workdir = raiz do monorepo; caminhos
> relativos a `cli/comfy-lab/`. Leia antes: PROMPT-EXECUTOR.md e
> CONTRATO-GLOBAL.md (§5 nodes, §6 constantes) + contrato web §5 (classes de
> fit, escada de base). Oráculo verde => ESTADO.md + UM commit
> `feat(comfy-S3): ...`.

## Objetivo

A feature de consumo: dado um workflow ComfyUI em API format, responder ANTES
de executar se ele cabe na máquina do snapshot — modelos referenciados, soma
de pesos em disco, resolução/batch/steps, veredito com base declarada.

## Dados verificados

- API format = JSON `{node_id: {"class_type": str, "inputs": {...}}}` (é o
  shape que `POST /prompt` do servidor consome).
- Nodes reconhecidos e campos: contrato §5 (verificados em nodes.py do clone).
- Classes de fit por referência (contrato web §5): `no` | `tight` | `ok` |
  `head`. Neste pack v1: `no` se `weights_bytes > vram_total`; `tight` se
  `> PROVISIONAL_TIGHT_FRACTION × vram_total`; senão `ok`; `head` reservado
  para quando houver célula measured (S6). Fração é PROVISÓRIA (§6) — não
  afrouxar.

## Saídas exatas

- `src/analyze_workflow.py`:
  - `parse_workflow(path) -> dict`: extrai por node reconhecido do §5 os
    campos listados; loaders com `class_type` fora do §5 que tenham input
    terminando em `_name` entram em `unmapped_loaders`.
  - `resolve_models(parsed, catalog) -> dict`: casa nome de arquivo do
    workflow com o catálogo da S2; modelo referenciado e ausente em disco ->
    `missing_files` (veredito automático `no`, reason literal
    "model file not found: <nome>").
  - `verdict(parsed, resolved, snapshot) -> dict`:
    `{"fit": ..., "basis": "extrapolated", "weights_bytes": int,
    "vram_total": int, "resolution": [w,h], "batch_size": int, "steps": int,
    "estimate_s_per_image": null, "unmapped_loaders": [...],
    "missing_files": [...], "reasons": [...]}`. Estimativa é SEMPRE `null`
    na S3 (sem measured — escada do contrato web).
  - CLI: `uv run python -m src.analyze_workflow <workflow.json>` imprime o
    veredito em JSON puro no stdout.
- `tests/fixtures/workflow-basic.json` — workflow API format mínimo válido:
  CheckpointLoaderSimple (apontando para um arquivo da fixture
  `models-tree/`) + EmptyLatentImage 1024×1024 batch 1 + KSampler steps 4.
- `tests/fixtures/workflow-unmapped.json` — inclui um loader inventado
  (`FakeLoaderXYZ` com `model_name`) para o caminho `unmapped_loaders`.
- Alvo `analyze` no check.py: veredito da fixture basic contra snapshot
  sintético (S1) tem `fit` calculável, `estimate_s_per_image == null`,
  `missing_files == []`; fixture unmapped produz `unmapped_loaders ==
  ["FakeLoaderXYZ"]`; workflow referenciando arquivo inexistente -> `no` com
  reason literal.

## O que NÃO fazer

- Não estimar s/imagem (null até S6); não modelar ativações/decode do VAE no
  cálculo de VRAM (v1 = pesos em disco; termo de ativação entra na
  recalibração da S6 com dado medido); não executar workflow; não subir
  servidor.

## Verificação

```bash
uv run python scripts/check.py analyze
uv run python -m src.analyze_workflow tests/fixtures/workflow-basic.json
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-comfy && uv run python scripts/check.py analyze
- exit esperado: 0 (antes do trabalho: exit 1 — alvo inexistente)

PARE E PERGUNTE se: o API format real divergir do shape declarado em "Dados
verificados" (checar contra um export real quando o servidor existir).
