# CONTRATO GLOBAL — bestmodel-comfy

Toda sessão lê este arquivo ANTES de qualquer trabalho. Complemento por
referência: `../apps/web/CONTRATO-GLOBAL.md` §5 (classes de fit e escada
de base declarada: measured > reported > extrapolated > null) vale aqui como
vocabulário de veredito.

## 1. O produto

A vertical de **diffusion/imagem** do bestmodel, com o ComfyUI como runtime:

1. **Probe de hardware** — o ComfyUI já detecta device, tipo (CUDA/ROCm/MPS/
   XPU), VRAM total/livre, torch e OS; expõe tudo em `GET /system_stats`.
2. **Lab de medição** — receitas congeladas (workflows em API format com
   `recipe_version`) executadas contra o servidor local; métricas: tempo de
   load, s/step, s/imagem, VRAM de pico; gravação em `experiments/` +
   `index.jsonl` (padrão lab_recorder da spec L01 do monorepo).
3. **Analisador de workflow** (feature de consumo) — dado um workflow JSON,
   responder "roda nesta máquina?" ANTES de executar: modelos referenciados
   pelos loaders × tamanho em disco × VRAM do snapshot → veredito.
4. **Node pack de instrumentação** (o plugin em si) — package Python
   instalável em `custom_nodes/` medindo VRAM de pico de dentro do processo.

Valor central: mesmo flywheel do L01 (tuning + medição + pool assinado +
predição calibrada), apontado para um mercado onde ninguém responde "roda
Flux na minha 3060?". Upload/contribute fica FORA do v1 (§9) — depende de
extensão de schema da plataforma (backlog Track D).

## 2. Dependência externa (única): ComfyUI local

- Instalação em `/Users/mini/ComfyUI` (clone do upstream
  `comfyanonymous/ComfyUI`, master). O clone NÃO recebe commits nem código
  deste pack — integração só por HTTP e pelo symlink do §7.
- Servidor: `python main.py --listen 127.0.0.1 --port 8188` (venv próprio do
  clone). Em 2026-08-12 o venv/modelos ainda não existiam — instalação é
  trabalho do workspace ComfyUI (BMAD "Fábrica de Imagens", EPIC-01), não
  deste pack. S4+ declara `BLOQUEADA` se o servidor/modelo não existir.
- Superfície HTTP usada (verificada em `server.py` do clone, 2026-08-12):
  `GET /system_stats` (l.676 — devices com name/type/index/vram_total/
  vram_free + versões), `POST /prompt` (l.1062), `GET /history/{prompt_id}`
  (l.1049), `GET /queue` (l.1054), `GET /object_info` (l.790).

## 3. Stack e layout (fechado)

Python >= 3.12 via **uv** (projeto próprio, independente do monorepo).
Deps permitidas (só esta): `httpx`. O node pack do §7 usa apenas o que o
processo do ComfyUI já tem (torch, stdlib) — zero deps novas lá.

```
cli/comfy-lab/
├── pyproject.toml            # S1 (uv init)
├── src/
│   ├── config.py             # S1 — constantes §6
│   ├── probe_hardware.py     # S1 — /system_stats -> data/hardware-snapshot.json
│   ├── scan_models.py        # S2 — models/ do ComfyUI -> data/local-models.json
│   ├── analyze_workflow.py   # S3 — workflow JSON -> veredito
│   ├── lab_runner.py         # S4 — receitas -> experiments/
│   └── report_lab.py         # S6 — measured vs estimated
├── bestmodel_comfy/          # S5 — node pack (symlink p/ custom_nodes/)
│   └── __init__.py           # NODE_CLASS_MAPPINGS
├── recipes/                  # S4 — workflows API format congelados
├── scripts/
│   ├── check.py              # oráculo único: uv run python scripts/check.py <alvo>
│   └── comfy-server.sh       # S4 — start|stop do servidor (recusa porta ocupada)
├── data/                     # gerado (gitignored)
├── experiments/              # gerado (gitignored)
└── tests/fixtures/           # fixtures sintéticas (shape real, valores marcados)
```

## 4. Portas (máquina compartilhada — regra de ouro do monorepo)

PROIBIDO bindar: 5432, 6379, 9000, 9001, 7700 (reservadas neste ambiente);
5434, 6380, 9002, 9003, 7701 (stack Fase 0); 8790 (backend pack); 8901 (web
pack); 8012/8000 (gate/CLI). Este pack NÃO abre porta própria — ele fala com
o ComfyUI em **127.0.0.1:8188** (verificada livre em 2026-08-12) e pode
subir/derrubar esse servidor exclusivamente via `scripts/comfy-server.sh`.

## 5. Nodes reconhecidos pelo analisador (v1 — verificados em nodes.py)

| Node (class_type) | O que extrair |
|---|---|
| `CheckpointLoaderSimple` (l.609) | `ckpt_name` -> arquivo em `models/checkpoints/` |
| `UNETLoader` (l.966) | `unet_name` -> `models/diffusion_models/` ou `models/unet/` |
| `VAELoader` (l.754) | `vae_name` -> `models/vae/` |
| `EmptyLatentImage` (l.1229) | `width`, `height`, `batch_size` |
| `KSampler` (l.1580) | `steps` |

Loader não mapeado no workflow -> entra no veredito como
`unmapped_loaders: [class_type, ...]` (nunca ignorar em silêncio). Cobertura
de outros loaders (CLIP/LoRA/GGUF) é evolução pós-v1 via `GET /object_info`.

## 6. Constantes fechadas (`src/config.py`)

```python
COMFY_BASE_URL = "http://127.0.0.1:8188"
COMFY_ROOT = "/Users/mini/ComfyUI"
MODEL_DIRS = ["checkpoints", "diffusion_models", "unet", "vae",
              "text_encoders", "clip", "loras"]   # subdirs reais de models/ (verificados 2026-08-12)
HARDWARE_SNAPSHOT = "data/hardware-snapshot.json"
LOCAL_MODELS = "data/local-models.json"
RECIPE_VERSION = "comfy-r1"
# PROVISÓRIO por design (sem measured ainda; recalibrar na S6 com dados da S4,
# mesmo espírito do finding F2 do monorepo — não afrouxar por conta própria):
PROVISIONAL_TIGHT_FRACTION = 0.8   # weights > 0.8×vram_total -> "tight"
```

## 7. Node pack e symlink (S5 — exceção única de escrita fora do pack)

`bestmodel_comfy/` é um package Python com `NODE_CLASS_MAPPINGS` no
`__init__.py` (mecanismo padrão de custom node do ComfyUI). Instalação local:
`ln -s /Users/mini/bestmodel/cli/comfy-lab/bestmodel_comfy
/Users/mini/ComfyUI/custom_nodes/bestmodel_comfy`. O symlink é a ÚNICA
escrita permitida fora deste diretório. Código do node em inglês; métricas de
pico via torch (`torch.cuda.max_memory_allocated` em CUDA; em MPS usar as
APIs `torch.mps` disponíveis na versão do torch instalada — verificar em
runtime, nunca assumir).

## 8. Convenções

- Código/commits em inglês; specs/ESTADO em português.
- 1 sessão = 1 commit no git do monorepo: `feat(comfy-S<n>): <resumo em inglês>`;
  só arquivos dentro de `cli/comfy-lab/`.
- Oráculo único: `uv run python scripts/check.py <alvo>`; cada sessão adiciona
  seu alvo e mantém `all`. Alvos que exigem servidor vivo checam antes com
  timeout de 2s e falham com mensagem clara (não pendurar).
- Veredito sempre carrega base declarada (escada do contrato web §5);
  estimativa sem célula measured = `null` — NUNCA inventar número.
- Funções 4-20 linhas, sem identificadores vagos, exceções com valor ofensor.

## 9. Escopo negativo

- NÃO tocar em nada fora de `cli/comfy-lab/` — exceção única: symlink §7.
- NÃO commitar/modificar o clone do ComfyUI; NÃO editar core, nodes.py ou
  server.py de lá; NÃO fazer fork.
- NÃO baixar modelos (aquisição é manual, workspace ComfyUI); NÃO fazer
  upload/contribute para a plataforma (v2 — depende do Track D no backlog do
  monorepo); NENHUMA request de rede além de 127.0.0.1:8188.
- NÃO bindar porta nenhuma (§4); NÃO deixar servidor vivo ao fim da sessão
  (`scripts/comfy-server.sh stop`).
- NÃO inventar números: sem measured -> `null` + base declarada; frações
  provisórias do §6 não podem ser afrouxadas pelo executor.
- NÃO implementar: assinatura Ed25519, trust score, leaderboard, UI web —
  tudo isso é plataforma (monorepo), não pack.
