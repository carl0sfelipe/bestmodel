# S5 — API de decisão (match)

Depende de: S4. Produz: `src/match.py`, endpoints §7, alvo `match`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/pool-backend/` — trabalhe
> dentro dele. Leia antes: `apps/pool-backend/PROMPT-EXECUTOR.md` e
> `apps/pool-backend/CONTRATO-GLOBAL.md` (e o contrato web §5/§6
> referenciado). Não invente número, prazo ou fonte além dos listados em
> "Dados verificados"; o que faltar fica [A DEFINIR].
> NUNCA use stub ou `declare const` como workaround de import — importe de verdade.
> Oráculo verde => atualizar ESTADO.md + UM commit `feat(backend-S5): ...`;
> mate qualquer servidor que subir (`pkill -f "uvicorn.*8790"`).

## Objetivo

Expor a sacada como API: dado um rig, quais modelos cabem e a que velocidade
(e o inverso: dado um modelo, em quais rigs do pool ele roda). Mesma escada
de honestidade do engine web, server-side.

## Dados verificados

- Superfície HTTP: CONTRATO §7, literal.
- Regras de fit/estimativa/ranking: contrato web §5 (funções e escada) e §6
  (constantes) — reimplementar em Python com os MESMOS valores; casos de
  teste espelham os da spec web S3 (Q4_K_M->4 etc.).
- Fonte de dados: SQLite (lm_*, plausibility_flag) — runs impossible fora,
  como na S4.

## Saídas exatas

- `src/match.py`: funções puras `usable_mem_gb(rig)`, `vram_needed_gb(model,
  bits)`, `fit_class(rig, model, bits)`, `estimate_tok_s(rig, model, bits,
  cells)`, `top_picks(...)` — assinaturas Python espelhando o web §5.
- Endpoints `/v1/rigs`, `/v1/models`, `/v1/match/hardware-to-models`,
  `/v1/match/model-to-hardware` em main.py conforme §7.
- Alvo `match` no check.py.

## Spec

1. Parâmetros inválidos (rig_key/model_slug inexistente, bits fora do
   domínio do contrato web §6: {1,2,3,4,5,6,7,8,16}) -> 404/422 com
   `{"error": ...}` incluindo o valor ofensor.
2. `model-to-hardware`: candidatos = rigs com célula para (model, bits) OU
   fit ok/head por fórmula; ranking igual ao top_picks (peso da basis, depois
   tok/s), `k` default 10.
3. As células vêm de uma query única por request (sem cache; dados pequenos).
4. `check.py match` valida via TestClient: healthz reflete runs reais;
   hardware-to-models para o rig de MAIOR run_count retorna >= 1 pick
   `measured`; model-to-hardware para o modelo de maior runCount retorna o
   próprio rig de maior célula; erro 404 para rig_key inexistente; todos os
   `estimate.basis` ∈ {measured, reported, extrapolated}; nenhum estimate
   inventado quando não há célula nem bandwidth (deve vir null).

## O que NÃO fazer

- Não ranquear por eval_score/qualidade (v1 é fit+velocidade); não paginar;
  não adicionar POST; não duplicar as constantes (importar de config.py).

## Verificação

```bash
uv run python scripts/check.py match
uv run uvicorn src.main:app --port 8790 &
curl -s "localhost:8790/v1/match/hardware-to-models?rig_key=<top-rig>&bits=4&k=5" | python3 -m json.tool | head -30
pkill -f "uvicorn.*8790"
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-backend && test -f src/match.py && uv run python scripts/check.py match
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: o pick "measured" do rig top não existir (bug de
identidade entre S2/S4/S5 — não afrouxar o teste).
