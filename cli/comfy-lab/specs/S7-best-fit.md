# S7 — Best fit: melhor modelo que cabe + s/imagem automático

Depende de: S2 (catálogo), S3 (veredito), S6 (células measured). Produz:
`src/best_fit.py`, alvo `bestfit` no check.py.

> Contexto de execução (dispatch): workdir = raiz do monorepo; caminhos
> relativos a `cli/comfy-lab/`. Leia antes: PROMPT-EXECUTOR.md e
> CONTRATO-GLOBAL.md (§6). Oráculo verde => ESTADO.md + UM commit
> `feat(comfy-S7): ...`. Esta spec é o oráculo de parada da missão HEFESTO
> (oracfit `specs/hefesto-bestmodel-loop.md`).

## Objetivo

O comando que o dono pediu: responder, offline e no automático, "qual é o
melhor modelo de geração de imagem que cabe NESTE hardware e quanto tempo
por imagem?" — a partir do snapshot (S1), do catálogo local (S2) e das
células measured (S4/S6). Sem servidor, sem rede, sem número inventado.

## Dados verificados

- Snapshot real: `data/hardware-snapshot.json` (source: live) após a S4.
- Células: agregação da S6 sobre `experiments/index.jsonl`.
- Proxy de qualidade v1 (DECLARADO, não medido): entre modelos que cabem,
  maior peso em disco primeiro. Ranking por qualidade real (eval scores) é
  plataforma (Track D2/D3 no backlog do monorepo), não pack.

## Saídas exatas

- `src/best_fit.py`:
  - `rank_models(catalog, snapshot, cells) -> list[dict]`: para cada modelo
    "principal" do catálogo (dirs `checkpoints`, `diffusion_models`, `unet`;
    vae/clip/loras são auxiliares, fora do ranking), calcula fit (regra §6 /
    S3), anexa `s_per_image` `{value, basis, n}` da célula measured quando
    houver (match por arquivo de modelo), senão `{value: null, basis: null,
    n: 0}`. Ordena: fit `ok` > `tight` > `no`; dentro do mesmo fit, maior
    `bytes` primeiro (proxy declarado); empate: nome.
  - CLI `uv run python -m src.best_fit [--json|--markdown]`:
    - `--markdown` (default): tabela `# | modelo | fit | s/img (basis, n) |
      GB` + linha final `melhor que cabe: <modelo>` (primeiro com fit != no;
      se nenhum cabe, `melhor que cabe: nenhum`).
    - `--json`: `{"generatedAt", "hardware": {device name/type, vram_total},
      "ranking": [...], "best": <entry|null>}`.
- Alvo `bestfit` no check.py: contra fixtures (snapshot sintético S1 +
  models-tree S2 + células de um index.jsonl de fixture criado aqui),
  valida: ordenação (ok antes de tight antes de no; bytes desc dentro do
  fit), `s_per_image.value` preenchido só quando a célula existe, `best`
  correto, e `--json` é JSON puro parseável. Contra dados reais: roda sem
  exceção e imprime >= 1 linha (catálogo real pode ter 1 modelo).

## O que NÃO fazer

- Não chamar servidor nem rede; não inventar s/img (sem célula -> null);
  não rankear vae/clip/loras; não inventar score de qualidade — o proxy
  declarado do v1 é tamanho, e está escrito na saída (`"quality_proxy":
  "largest-that-fits-v1"` no --json).

## Verificação

```bash
uv run python scripts/check.py bestfit
uv run python -m src.best_fit --markdown
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-comfy && uv run python scripts/check.py bestfit
- exit esperado: 0 (antes do trabalho: exit 1 — alvo inexistente)

PARE E PERGUNTE se: o snapshot real ainda for `source: synthetic` ao rodar
contra dados reais (S4 não rodou — dependência quebrada).
