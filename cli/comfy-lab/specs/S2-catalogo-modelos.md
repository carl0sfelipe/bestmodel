# S2 — Catálogo local de modelos

Depende de: S1. Produz: `src/scan_models.py`, alvo `models` no check.py,
`tests/fixtures/models-tree/` (árvore sintética).

> Contexto de execução (dispatch): workdir = raiz do monorepo; caminhos
> relativos a `cli/comfy-lab/`. Leia antes: PROMPT-EXECUTOR.md e
> CONTRATO-GLOBAL.md. Oráculo verde => ESTADO.md + UM commit
> `feat(comfy-S2): ...`.

## Objetivo

Inventário do que existe em disco: escanear os `MODEL_DIRS` do ComfyUI e
produzir `data/local-models.json` com nome, subdir, tamanho em bytes e
formato — a matéria-prima do veredito da S3. Fonte de verdade = filesystem;
nenhum catálogo externo.

## Dados verificados

- Subdirs reais de `/Users/mini/ComfyUI/models/` em 2026-08-12 incluem todos
  os `MODEL_DIRS` do contrato §6 (checkpoints, diffusion_models, unet, vae,
  text_encoders, clip, loras).
- Em 2026-08-12 esses dirs só contêm placeholders (`put_checkpoints_here`) —
  o scan DEVE funcionar com dirs vazios (resultado: lista vazia, não erro).
- Extensões de modelo aceitas: `.safetensors`, `.ckpt`, `.pt`, `.gguf`,
  `.sft` (as que o ComfyUI lista para checkpoints/unet/vae).

## Saídas exatas

- `src/scan_models.py` — `scan(comfy_root) -> list[dict]`: para cada
  `MODEL_DIRS`, listar arquivos com extensão aceita (recursivo 1 nível);
  cada entrada: `{"file": nome, "dir": subdir, "bytes": os.stat, "format":
  extensão sem ponto}`. `write_catalog(entries, path)` grava
  `data/local-models.json` com `"scannedAt"` ISO. CLI:
  `uv run python -m src.scan_models` imprime resumo de 1 linha por dir.
- `tests/fixtures/models-tree/` — árvore sintética com 3 arquivos pequenos
  (bytes reais dos arquivos da fixture; conteúdo dummy) cobrindo checkpoints,
  vae e um dir vazio.
- Alvo `models` no check.py: roda `scan()` contra a fixture e valida
  contagem (3), bytes (== stat real da fixture) e formato; depois roda contra
  o `COMFY_ROOT` real e valida apenas que retorna lista (vazia é válido).

## O que NÃO fazer

- Não baixar nada; não inferir parâmetros/quant do modelo pelo nome (v1 é
  inventário, não identificação); não ler headers safetensors ainda (pós-v1);
  não tocar em `models/` do clone (leitura apenas).

## Verificação

```bash
uv run python scripts/check.py models
uv run python -m src.scan_models
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-comfy && uv run python scripts/check.py models
- exit esperado: 0 (antes do trabalho: exit 1 — alvo inexistente)

PARE E PERGUNTE se: algum `MODEL_DIRS` não existir no clone (mudança upstream
no layout de models/) — humano decide se atualiza o contrato §6.
