# Story 4.2 — Harvester: model cards HuggingFace [Épico 4]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Extração conservadora: tabela que não casa o formato documentado → ZERO
  células (nunca inventar/adivinhar valor); células saem sempre
  source_class='harvested' + status='unverified' via o framework 4.1.
- Nenhuma dependência nova (stdlib; fetch via urllib se necessário, e testes
  NUNCA tocam rede — fixture real commitado verbatim).
- Não invente alias de GPU, métrica ou fórmula fora das tabelas documentadas.

## Dados verificados (copie SEM ALTERAR)
- Alvo: model cards HF com tabelas markdown declarando performance
  (estilo TheBloke: linhas por quant, colunas por GPU, células "X tok/s").
- Mapeamento de métrica (documentado, fixo): "tok/s", "t/s",
  "tokens per second", "tokens/sec" → metric "decode_tok_s" (unit "tok/s").
- Alias de GPU (mapa fixo, case-insensitive, sem regex exótico):
  "rtx 3090"/"3090" → gpu-rtx-3090; "rtx 4090"/"4090" → gpu-rtx-4090;
  "rtx 3090 ti" → gpu-rtx-3090 (nota: catalog não tem 3090ti, staging é
  unbound); acentos/unicode não são aceitos em nome de GPU (fora do mapa →
  ignora a coluna).
- model_release_id do staging: string livre derivada do título do card
  (linhas de heading `# ` acima da tabela) + linha da tabela (ex.: nome do
  modelo + quant) — staging não tem FK; binding é a revisão (4.4).
- Framework 4.1 (packages/harvester/src/harvester.py): harvest(fixture,
  staging) já garante hash/idempotência/SourceMutated — 4.2 SÓ produz o
  fixture-dict.

## ENTREGÁVEIS
1. `packages/harvester/src/model_card_harvester.py`:
   - `extract_model_card_metrics(markdown_text: str, source_url: str, harvested_at: str) -> dict`
     (dict no formato fixture do 4.1: source_url/harvested_at/cells; 0 células
     é resultado válido e honesto).
   - `fetch_model_card(url: str) -> str` (urllib, UA "canirunit-harvester/0.1")
     — NÃO testado com rede; existe para o uso real.
   - Parsing: tabelas markdown (linhas `| ... |`); header precisa conter um
     token de métrica mapeado OU coluna de GPU conhecida; células com número +
     unidade de métrica; número sem unidade mas coluna de GPU conhecida e
     header com métrica → aceito (documentado).
2. `packages/harvester/tests/fixtures/model-card.md` — fixture REAL baixado
   de um model card HF que contenha tabela tok/s com 3090/4090 (fetch durante
   o desenvolvimento, commitado VERBATIM; tamanho grande é aceitável).
   + `fixtures/model-card.meta.json` com {"source_url": ..., "fetched_at": "YYYY-MM-DD"}.
3. `packages/harvester/tests/test_model_card_harvester.py` (>=5):
   a. fixture real → extract gera >=1 célula com metric decode_tok_s e
      gpu_model_id no mapa de alias;
   b. determinismo (2 chamadas → dicts iguais);
   c. tabela fora do formato → 0 células;
   d. integração com 4.1: fixture gerado do card real + harvest() para
      staging tmp → added>=1, source_class harvested, status unverified,
      reexec added=0;
   e. células sintéticas (card mínimo construído no teste) exercitam cada
      alias de GPU e número com/sem unidade.
4. pyproject da package: sem mudança (stdlib).

## COMMIT
(não commitar — sessão principal valida e commita.)

## VERIFICAÇÃO
pytest da package verde; oráculo abaixo verde (usa o fixture REAL).

## Oraculo
- comando: cd ~/Work/CanIRunIt && uv run pytest -q packages/harvester/tests/test_model_card_harvester.py 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && uv run python -c "import sys, json, tempfile; from pathlib import Path; sys.path.insert(0, 'packages/harvester/src'); from model_card_harvester import extract_model_card_metrics; from harvester import harvest; fx_dir = Path('packages/harvester/tests/fixtures'); meta = json.loads((fx_dir / 'model-card.meta.json').read_text()); card = fx_dir / 'model-card.md'; fixture = extract_model_card_metrics(card.read_text(), meta['source_url'], meta['fetched_at']); assert len(fixture['cells']) >= 1; p = Path(tempfile.mkdtemp()) / 'f.json'; p.write_text(json.dumps(fixture)); st = Path(tempfile.mkdtemp()) / 's.jsonl'; r = harvest(p, st); assert r.added >= 1 and len(st.read_text().splitlines()) >= 1 and 'harvested' in st.read_text(); print('ORACULO-4.2-OK')"
