# S6 — Relatório measured vs estimated + recalibração

Depende de: S4 (precisa de >= 1 experimento); ideal após S5 (pico exato).
Produz: `src/report_lab.py`, alvo `report` no check.py, atualização
justificada de `PROVISIONAL_TIGHT_FRACTION`.

> Contexto de execução (dispatch): workdir = raiz do monorepo; caminhos
> relativos a `cli/comfy-lab/`. Leia antes: PROMPT-EXECUTOR.md e
> CONTRATO-GLOBAL.md (§6). Oráculo verde => ESTADO.md + UM commit
> `feat(comfy-S6): ...`.

## Objetivo

Fechar o loop da vertical no v1: tabela measured vs estimated, veredito da S3
promovido de `extrapolated` para `measured` quando existir célula, e a fração
provisória do contrato recalibrada com dado real — nunca por palpite.

## Dados verificados

- Experimentos da S4/S5 em `experiments/` (metrics.json + index.jsonl +
  peak-vram.jsonl).
- Escada de base declarada: contrato web §5 por referência.

## Saídas exatas

- `src/report_lab.py` — lê `experiments/index.jsonl` e agrega células por
  (modelo, resolução, batch, steps, recipe_version): `s_per_image`
  (mean/std/n), `peak_bytes` quando houver. Saídas: `--json` (dict puro) e
  `--markdown` (tabela: recipe | modelo | s/img mean±std | peak VRAM | n).
- `src.analyze_workflow.verdict` passa a consultar as células agregadas:
  match exato de (modelo, resolução±0, batch, steps) -> `basis: "measured"`
  + `estimate_s_per_image` preenchido; sem célula -> comportamento S3
  intacto (null, extrapolated).
- Recalibração: se houver `peak_bytes` measured, recomputar a fração
  pico/pesos observada e atualizar `PROVISIONAL_TIGHT_FRACTION` no config com
  comentário citando o experimento (`# calibrado: exp <ts>, ratio X.XX`);
  sem peak measured (MPS sem API), NÃO mexer na fração e registrar em
  Perguntas abertas do ESTADO.md.
- Alvo `report` no check.py: `--json` retorna >= 1 célula com n >= 3;
  veredito da recipe congelada retorna `basis: "measured"` e estimate não
  nulo; `--markdown` contém o recipe_version.

## O que NÃO fazer

- Não inventar termo de ativação teórico (modelagem física de diffusion é
  trabalho da plataforma, Track D); não fazer upload; não apagar
  experimentos; não reportar célula com n < 3 como measured.

## Verificação

```bash
uv run python scripts/check.py report
uv run python -m src.report_lab --markdown
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-comfy && uv run python scripts/check.py report
- exit esperado: 0 (antes do trabalho: exit 1 — alvo inexistente)

PARE E PERGUNTE se: a fração recalibrada divergir da provisória em mais de
2x (ou o pico exceder os pesos em mais de 2x) — número anômalo é decisão de
humano, não ajuste silencioso.
