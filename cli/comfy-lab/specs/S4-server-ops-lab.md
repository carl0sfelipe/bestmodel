# S4 — Server ops + lab runner (primeira medição real)

Depende de: S1-S3 + PRÉ-REQUISITO EXTERNO: ComfyUI instalado (venv +
dependências) e >= 1 modelo em disco — trabalho do workspace ComfyUI
(EPIC-01). Se ausente: marcar `BLOQUEADA: aguardando EPIC-01` no ESTADO.md e
PARAR. Produz: `scripts/comfy-server.sh`, `src/lab_runner.py`,
`recipes/flux-schnell-fp8-1024.json`, alvo `lab` no check.py.

> Contexto de execução (dispatch): workdir = raiz do monorepo; caminhos
> relativos a `cli/comfy-lab/`. Leia antes: PROMPT-EXECUTOR.md e
> CONTRATO-GLOBAL.md (§2 rotas, §4 portas). Oráculo verde => ESTADO.md + UM
> commit `feat(comfy-S4): ...`. NUNCA deixar o servidor vivo ao final.

## Objetivo

Subir/derrubar o ComfyUI com disciplina de máquina compartilhada, capturar o
snapshot REAL de hardware e executar a primeira receita congelada medindo
tempos de verdade — a primeira linha de dado measured da vertical diffusion.

## Dados verificados

- Servidor: `python main.py --listen 127.0.0.1 --port 8188` a partir do venv
  do clone. Rotas: contrato §2.
- `GET /history/{prompt_id}` retorna o registro da execução; o campo
  `status.messages` carrega eventos com timestamps (`execution_start`,
  `execution_success`) — base do tempo de parede por prompt.
- Warmup obrigatório: primeira geração inclui load do modelo; NUNCA reportar
  cold-start como s/imagem (lição llama-optimus adotada no L01).
- Nome exato do arquivo de modelo em disco: descobrir em runtime via scan da
  S2 (não chumbar nome de arquivo que ainda não existe).

## Saídas exatas

- `scripts/comfy-server.sh` — `start`: recusa com PID se 8188 ocupada
  (`lsof`), senão sobe com nohup + log em `data/comfy-server.log` e espera
  `/system_stats` responder (timeout 60s); `stop`: mata pelo PID gravado em
  `data/comfy-server.pid` (nunca `pkill` genérico de python).
- `data/hardware-snapshot.json` regravado com `"source": "live"` (via
  `src.probe_hardware` da S1) — substitui o sintético.
- `recipes/flux-schnell-fp8-1024.json` — workflow API format congelado
  (recipe_version `comfy-r1` no nome de um node de anotação ou em arquivo
  sidecar `recipes/flux-schnell-fp8-1024.meta.json` com
  `{"recipe_version": ..., "warmup_runs": 1, "measured_runs": 3}`):
  UNETLoader/CheckpointLoaderSimple conforme o formato do modelo presente,
  EmptyLatentImage 1024×1024 batch 1, KSampler steps 4, SaveImage.
- `src/lab_runner.py` — `run_recipe(recipe_path)`: valida contra
  `src.analyze_workflow` primeiro (fit `no` -> aborta com o veredito no
  stderr); executa 1 warmup + 3 medições via `POST /prompt`, espera via
  polling de `/history/{id}` (intervalo 1s, timeout 15min); grava
  `experiments/<ts>-<recipe>/`: `meta.json` (recipe_version, snapshot de
  hardware, modelo usado), `metrics.json` (por run: wall_s; agregado:
  mean/std/min/max) e acrescenta 1 linha em `experiments/index.jsonl`.
- Alvo `lab` no check.py: com servidor DE PÉ (checar antes, mensagem clara se
  não), roda a receita e valida: index.jsonl ganhou linha, metrics.json tem 3
  runs + agregados, warmup NÃO está nas medições.

## O que NÃO fazer

- Não medir VRAM de pico ainda (S5 — o node); não criar outras receitas; não
  fazer upload; não otimizar flags do servidor; não rodar com outra carga
  pesada ativa (16GB unificados — contrato ComfyUI workspace).

## Verificação

```bash
scripts/comfy-server.sh start
uv run python scripts/check.py lab
scripts/comfy-server.sh stop
uv run python scripts/check.py all   # alvos de servidor pulam com aviso se down
```

## ORÁCULO

- comando: cd bestmodel-comfy && scripts/comfy-server.sh start && uv run python scripts/check.py lab; s=$?; scripts/comfy-server.sh stop; exit $s
- exit esperado: 0 (antes do trabalho: exit 1 — script inexistente)

PARE E PERGUNTE se: modelo nenhum em disco (BLOQUEADA, ver topo); geração
passar de 15min (M4 16GB pode estar em swap — humano decide receita menor);
8188 ocupada por processo desconhecido.
