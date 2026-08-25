# S5 — Node pack de instrumentação (o plugin)

Depende de: S4. Produz: `bestmodel_comfy/__init__.py` (+ módulos), symlink em
`/Users/mini/ComfyUI/custom_nodes/bestmodel_comfy`, recipe v2, alvo
`nodepack` no check.py.

> Contexto de execução (dispatch): workdir = raiz do monorepo; caminhos
> relativos a `cli/comfy-lab/`. Leia antes: PROMPT-EXECUTOR.md e
> CONTRATO-GLOBAL.md (§7 — symlink é a ÚNICA escrita fora do pack). Código do
> node em INGLÊS. Oráculo verde => ESTADO.md + UM commit `feat(comfy-S5): ...`.

## Objetivo

O plugin propriamente dito: package Python carregável pelo mecanismo de
custom nodes do ComfyUI, medindo VRAM de pico de dentro do processo — o dado
que a API HTTP não expõe. Instalação local por symlink; é o embrião do
pacote distribuível (ComfyUI-Manager) da vertical.

## Dados verificados

- Mecanismo: ComfyUI importa cada dir de `custom_nodes/` como módulo e lê
  `NODE_CLASS_MAPPINGS` (ver `custom_nodes/example_node.py.example` no clone).
- Convenções de node: `INPUT_TYPES` classmethod, `RETURN_TYPES`, `FUNCTION`,
  `CATEGORY` (mesmo exemplo).
- Medição de pico: em CUDA, `torch.cuda.max_memory_allocated()` /
  `reset_peak_memory_stats()`. Em MPS as APIs de pico variam por versão do
  torch — DESCOBRIR em runtime (`hasattr`) e reportar `null` com
  `"peak_basis": "unavailable"` quando não houver; nunca fingir medição.

## Saídas exatas

- `bestmodel_comfy/__init__.py` + `bestmodel_comfy/probe_nodes.py` — node
  `bestmodelPeakVRAM`: `CATEGORY = "bestmodel"`; passthrough de IMAGE (recebe
  IMAGE, retorna IMAGE inalterada) que, ao executar, coleta pico de VRAM do
  device ativo e acrescenta uma linha JSON em
  `<pack>/experiments/peak-vram.jsonl` (`{"ts", "device_type", "peak_bytes",
  "peak_basis": "cuda_max_allocated"|"mps_<api>"|"unavailable"}`). Caminho do
  pack resolvido pelo próprio arquivo (`__file__`), nunca cwd.
- Reset do contador no início do fluxo: input opcional `reset` (BOOLEAN,
  default true) que zera as estatísticas de pico antes da passagem quando a
  API do device permitir.
- Symlink: `ln -s <pack>/bestmodel_comfy /Users/mini/ComfyUI/custom_nodes/bestmodel_comfy`
  (idempotente: se já existe e aponta certo, ok).
- `recipes/flux-schnell-fp8-1024-v2.json` (+ sidecar meta): a recipe da S4
  com o node de pico entre o VAEDecode e o SaveImage.
- Alvo `nodepack` no check.py: symlink existe e resolve; com servidor de pé,
  `GET /object_info/bestmodelPeakVRAM` responde 200; `run_recipe` da v2
  produz linha nova em `peak-vram.jsonl` com `peak_bytes > 0` OU
  `peak_basis == "unavailable"` (MPS sem API — válido, não verde falso).

## O que NÃO fazer

- Não importar nada além de torch/stdlib no node; não tocar em
  `comfy.model_management` para além de leitura; não registrar mais de um
  node no v1; não publicar no registry (distribuição é decisão do dono).

## Verificação

```bash
scripts/comfy-server.sh start   # reimportará custom_nodes com o symlink
uv run python scripts/check.py nodepack
scripts/comfy-server.sh stop
```

## ORÁCULO

- comando: cd bestmodel-comfy && scripts/comfy-server.sh start && uv run python scripts/check.py nodepack; s=$?; scripts/comfy-server.sh stop; exit $s
- exit esperado: 0 (antes do trabalho: exit 1 — alvo inexistente)

PARE E PERGUNTE se: o import do node falhar no boot do ComfyUI (log em
`data/comfy-server.log`) por mudança upstream no mecanismo de custom nodes.
