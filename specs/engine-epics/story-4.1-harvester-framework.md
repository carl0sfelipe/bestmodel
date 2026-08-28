# Story 4.1 — Framework de harvester determinístico [Épico 4]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Harvester NUNCA escreve direto em produção: staging JSONL, status
  `unverified`, source_class `harvested` (a fila de revisão é a Story 4.4).
- Reexecução NUNCA duplica células (NFR-3); fonte que mudou de conteúdo sob
  o MESMO source_url é rejeitada com erro claro (hash mismatch), nunca
  silenciosamente atualizada.
- Nenhuma dependência nova: stdlib (hashlib/json/uuid/pathlib/dataclasses) +
  pytest já existente.
- Não invente campo, formato ou número além dos definidos abaixo.

## Dados verificados (copie SEM ALTERAR)
- 4 classes canônicas (FR-3): harvested = extraída deterministicamente de
  fonte estruturada por script versionado; NÃO entra em leaderboard até 4.4.
- Namespace uuid5 fixo do repo: 6ba7b810-9dad-11d1-80b4-00c04fd430c8.
- Formato do FIXTURE (entrada, JSON):
  {"source_url": str, "harvested_at": "YYYY-MM-DD",
   "cells": [{"gpu_model_id": str, "model_release_id": str, "recipe_id": str|null,
              "metric": str, "value": number, "unit": str, "note": str}]}
- Formato do STAGING (saída, JSONL, 1 célula/linha, ordem de inserção):
  {"cell_id": uuid5, "source_url": str, "source_sha256": 64hex,
   "gpu_model_id": str, "model_release_id": str, "recipe_id": str|null,
   "metric": str, "value": number, "unit": str, "source_class": "harvested",
   "status": "unverified", "harvested_at": "YYYY-MM-DD"}
- cell_id = uuid5(NAMESPACE, "{source_url}|{source_sha256}|{gpu}|{model}|{recipe}|{metric}")
  com recipe renderizado como string vazia quando null.

## ENTREGÁVEIS
1. `packages/harvester/src/harvester.py` (pacote novo, estilo dos demais:
   docstring de módulo, `from __future__ import annotations`, type hints):
   - `harvest(fixture_path: Path, staging_path: Path) -> HarvestResult`
   - `HarvestResult` dataclass: `added: int`, `skipped: int`,
     `cells_staged: list[dict]` (as células desta execução).
   - `SourceMutated(Exception)`: atributos `source_url`, `staged_sha256`,
     `incoming_sha256`; mensagem contém os dois hashes.
   - Semântica: lê fixture → sha256 dos BYTES do arquivo → para cada cell,
     deriva cell_id → staging existe? (a) identidade já presente com MESMO
     source_sha256 → skip; (b) MESMA (source_url+gpu+model+recipe+metric) com
     source_sha256 DIFERENTE → SourceMutated ANTES de gravar qualquer coisa
     (staging intocado); (c) nova identidade → append. Arquivo de staging é
     criado se não existir; nada é escrito quando a execução termina em erro.
   - Fixture inválido (JSON ruim / sem source_url / cells não-lista /
     cell sem campo obrigatório) → ValueError com nome do campo.
2. `packages/harvester/tests/test_harvester.py` (>=5 testes):
   a. primeira coleta estácia células com source_class harvested,
      source_url, source_sha256 == sha256 do arquivo, cell_id determinístico;
   b. reexecução no mesmo staging: added=0, skipped=N, arquivo byte-idêntico
      (comparar conteúdo antes/depois);
   c. fixture adulterado (mesmo source_url, valor editado) → SourceMutated,
      staging intocado, mensagem contém staged e incoming hash;
   d. cell_id independente do staging: dois stagings diferentes a partir do
      mesmo fixture geram ids idênticos;
   e. fixture malformado → ValueError claro (parametrizado em 2–3 casos).
   Fixture de teste em `packages/harvester/tests/fixtures/model-card-fixture.json`
   (2 células: uma LLM decode_tok_s numa gpu-rtx-3090, uma vídeo
   seconds_per_clip numa gpu-rtx-4090 com recipe wan22-flf2v-720p-81f-v1).
3. `pyproject.toml` (raiz): adicionar "packages/harvester/src" ao
   `pythonpath` do `[tool.pytest.ini_options]` (NÃO mexer em mais nada).
4. Nada de CLI, nada de rede (fetchers são 4.2/4.3), nada de banco.

## COMMIT
(não commitar — a sessão principal valida o oráculo e commita.)

## VERIFICAÇÃO
`uv run pytest -q packages/harvester/tests` verde e oráculo abaixo verde.

## Oraculo
- comando: cd ~/Work/CanIRunIt && uv run pytest -q packages/harvester/tests 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && uv run python -c "import sys, tempfile; from pathlib import Path; sys.path.insert(0, 'packages/harvester/src'); from harvester import harvest; fx = Path('packages/harvester/tests/fixtures/model-card-fixture.json'); st = Path(tempfile.mkdtemp()) / 's.jsonl'; r1 = harvest(fx, st); r2 = harvest(fx, st); assert r1.added == 2 and r2.added == 0 and r2.skipped == 2, (r1, r2); assert len(st.read_text().splitlines()) == 2; print('ORACULO-4.1-OK')"