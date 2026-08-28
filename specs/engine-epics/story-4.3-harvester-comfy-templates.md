# Story 4.3 — Harvester: template library ComfyUI [Épico 4]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Candidato de receita NUNCA é recipe publicada: staging JSONL próprio,
  status 'unverified_candidate' (promoção é a revisão 4.4).
- Extração conservadora: nó sampler sem width/height/length legíveis →
  params parciais (apenas os legíveis, null nos demais); nada é inferido.
- Nenhuma dependência nova (stdlib). Testes NUNCA tocam rede — template REAL
  commitado verbatim.
- Não invente campo, URL, nó, param, formato ou fonte além dos listados abaixo.

## Dados verificados (copie SEM ALTERAR)
- Fonte: templates de workflow versionados do ComfyUI (formato exportado
  UI: {"nodes": [...]} OU formato API: {"<id>": {"class_type", "inputs"}}).
- Nós de amostragem (mesma regra do benchmark-probe 1.2): class_type contém
  "Sampler" ou termina com "ToVideo".
- Nós de modelo: UNETLoader/CLIPLoader/VAELoader/CheckpointLoaderSimple →
  inputs com nome de arquivo (.safetensors/.gguf/.pt etc.).
- Params de interesse nos inputs do sampler: width, height, length (frames),
  steps (inteiros positivos; ausente → null).
- Template real conhecido: Comfy-Org/frontend repo, public/templates/video/
  (ex.: wan_image_to_video.json); URL exata vai no .meta.json do fixture.
- Namespace uuid5 do repo: 6ba7b810-9dad-11d1-80b4-00c04fd430c8.

## ENTREGÁVEIS
1. `packages/harvester/src/comfy_template_harvester.py`:
   - `extract_recipe_candidates(template_text: str, source_url: str, harvested_at: str) -> dict`
     no formato fixture análogo ao 4.1: {"source_url", "harvested_at",
     "candidates": [...]} com candidate = {"workflow_class": str,
     "models": [str], "width": int|null, "height": int|null,
     "length": int|null, "steps": int|null}.
   - `stage_recipe_candidates(fixture: dict, staging_path: Path) -> HarvestResult-like`
     (added/skipped; candidate_id = uuid5(NAMESPACE, "{source_url}|{sha256 do
     template_text}|{workflow_class}|{width}x{height}x{length}x{steps}|{models
     ordenados juntados por ,}"); idempotente por candidate_id: mesma id →
     skip; mesmo source_url com sha DIFERENTE de candidato já estagiado →
     SourceMutated (importada do harvester 4.1); nada escrito em erro).
   - Linha de staging JSONL: {"candidate_id", "source_url", "source_sha256",
     "workflow_class", "models", "width", "height", "length", "steps",
     "source_class": "harvested", "status": "unverified_candidate",
     "harvested_at"}.
   - Aceita UI-format e API-format (detecção: tem "nodes" list → UI; objeto
     de objetos com class_type → API; senão ValueError).
2. `packages/harvester/tests/fixtures/<template-real>.json` — template REAL
   de workflow da lib do ComfyUI com sampler Wan (fetch no desenvolvimento,
   commitado VERBATIM) + `<template-real>.meta.json` {"source_url",
   "fetched_at"}.
3. `packages/harvester/tests/test_comfy_template_harvester.py` (>=5):
   a. template real → >=1 candidato com workflow_class contendo Wan/Video
      ou Sampler e models nao-vazio;
   b. determinismo;
   c. idempotência: stage 2x → added 0 na segunda, arquivo byte-idêntico;
   d. template mutado (mesmo source_url, texto editado) → SourceMutated com
      staging intocado;
   e. template mínimo sintético API-format → params extraídos exatos;
      formato desconhecido → ValueError.

## COMMIT
(não commitar — sessão principal valida e commita.)

## VERIFICAÇÃO
pytest da package verde; oráculo abaixo verde (template REAL).

## Oraculo
- comando: cd ~/Work/CanIRunIt && uv run pytest -q packages/harvester/tests/test_comfy_template_harvester.py 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && uv run python -c "import sys, json, tempfile; from pathlib import Path; sys.path.insert(0, 'packages/harvester/src'); from comfy_template_harvester import extract_recipe_candidates, stage_recipe_candidates; fx_dir = Path('packages/harvester/tests/fixtures'); meta = json.loads((fx_dir / 'comfy-template.meta.json').read_text()); tpl = fx_dir / 'comfy-template.json'; fixture = extract_recipe_candidates(tpl.read_text(), meta['source_url'], meta['fetched_at']); assert len(fixture['candidates']) >= 1; st = Path(tempfile.mkdtemp()) / 'recipes.jsonl'; r1 = stage_recipe_candidates(fixture, st); r2 = stage_recipe_candidates(fixture, st); assert r1.added >= 1 and r2.added == 0 and 'unverified_candidate' in st.read_text(); print('ORACULO-4.3-OK')"
