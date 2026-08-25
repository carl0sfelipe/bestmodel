# CONTRATO GLOBAL — bestmodel-backend

Toda sessão lê este arquivo ANTES de qualquer trabalho. Complemento
obrigatório: `../apps/web/CONTRATO-GLOBAL.md` §3 (API do localmaxxing,
verificada ao vivo) e §4 (schemas derivados) valem aqui POR REFERÊNCIA — são
parte deste contrato.

## 1. O produto

Serviço local que industrializa os dados do site: sincroniza o pool público
do localmaxxing para um banco local, roda checagem de plausibilidade física
sobre cada run (a parte que o concorrente não faz), gera os JSONs derivados
que o site estático consome e expõe a decisão como API
("hardware -> modelos" e "modelo -> hardware").

Valor central: **curadoria por física**. O pool deles é auto-reporte sem
validação; nós recomputamos o teto roofline de cada run e excluímos dos
agregados o que é fisicamente impossível. Todo número servido carrega base
declarada (mesma escada da web: measured > reported > extrapolated > null).

## 2. Stack e layout (fechado)

Python >= 3.12 via **uv** (projeto próprio, independente do monorepo).
Deps permitidas (só estas): `fastapi`, `uvicorn`, `httpx` — `uv add` na
versão corrente. Banco: **SQLite** (stdlib `sqlite3`). Decisão: SQLite e não
o Postgres 5434 do monorepo — máquina compartilhada, ~5-10k linhas, zero
risco de contaminar o gate da Fase 0.

```
apps/pool-backend/
├── pyproject.toml           # S1 (uv init)
├── src/
│   ├── config.py            # S1 — constantes §5
│   ├── main.py              # S1 — FastAPI app + /healthz
│   ├── db.py                # S2 — conexão + migrate(DDL §4)
│   ├── sync_pool.py         # S2 — localmaxxing -> SQLite
│   ├── plausibility.py      # S3 — teto roofline + flags
│   ├── derive_export.py     # S4 — SQLite -> out/derived/*.json
│   └── match.py             # S5 — lógica dos endpoints de decisão
├── scripts/
│   ├── check.py             # oráculo único: uv run python scripts/check.py <alvo>
│   ├── sync-all.sh          # S6 — sync -> flags -> derived -> copy
│   └── run.sh               # S6 — uvicorn na porta §5
├── data/lmpool.sqlite3      # gerado (gitignored)
└── out/derived/             # gerado (gitignored; cópia vai p/ ../apps/web/data/derived/)
```

## 3. Portas (máquina compartilhada — regra de ouro do monorepo)

PROIBIDO bindar: 5432, 6379, 9000, 9001, 7700 (reservadas neste ambiente) e
5434, 6380, 9002, 9003, 7701 (stack Fase 0). O gate da Fase 0 usa 8012
ad-hoc; o CLI usa 8000 como default. **Porta deste backend: 8790**
(verificada livre em 2026-08-12). Única porta que este pack pode abrir, além
da 8901 já reservada pelo pack web para verificação estática.

## 4. Schema SQLite (DDL literal — S2 aplica exatamente isto)

```sql
CREATE TABLE IF NOT EXISTS sync_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lm_model(
  slug TEXT PRIMARY KEY, hf_id TEXT NOT NULL, display_name TEXT NOT NULL,
  family TEXT, params_b REAL, active_params_b REAL,
  is_moe INTEGER NOT NULL DEFAULT 0,
  category TEXT NOT NULL CHECK(category IN ('chat','code')),
  eval_score REAL, raw_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lm_rig(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, hw_class TEXT NOT NULL,
  mem_gb REAL, gpu_count INTEGER NOT NULL DEFAULT 1,
  bandwidth_gbs REAL, run_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS lm_run(
  id TEXT PRIMARY KEY,
  model_slug TEXT NOT NULL REFERENCES lm_model(slug),
  rig_key TEXT NOT NULL REFERENCES lm_rig(key),
  bits INTEGER, quant TEXT, engine TEXT,
  tok_s_out REAL NOT NULL, tok_s_prefill REAL, ttft_ms REAL,
  peak_vram_gb REAL, context_length INTEGER, batch_size INTEGER,
  spec_decoding INTEGER NOT NULL DEFAULT 0,
  mtp_enabled INTEGER NOT NULL DEFAULT 0,
  concurrency INTEGER, created_at TEXT NOT NULL, raw_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plausibility_flag(
  run_id TEXT PRIMARY KEY REFERENCES lm_run(id),
  ceiling_tok_s REAL NOT NULL, ratio REAL NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('ok','suspicious','impossible','exempt')),
  reason TEXT NOT NULL, computed_at TEXT NOT NULL);
```

Regras de identidade (rigKey, slug, category, quant->bits, seed de
bandwidth): EXATAMENTE as do contrato web §4 e §6. Os campos
`spec_decoding/mtp_enabled/concurrency` vêm de `engineFlags`
(`specDecoding`, `mtpEnabled`, `concurrency` — verificados no wire em
2026-08-12; null -> 0/null).

## 5. Constantes fechadas (`src/config.py`)

```python
API_PORT = 8790
DB_PATH = "data/lmpool.sqlite3"
API_BASE = "https://www.localmaxxing.com/api"
THROTTLE_MS = 350                    # mesma etiqueta do pack web
USER_AGENT = "bestmodel-backend-sync/0.1"
MIN_RUNS_MEASURED = 3
SUSPICIOUS_FRACTION = 0.92           # regra roofline da Fase 0 (finding F2/A5)
IMPOSSIBLE_FRACTION = 1.05           # acima do teto físico + tolerância de medição
ATTRIBUTION = "community pool data via localmaxxing.com public API"
```

## 6. Plausibilidade (S3) — regra fechada

Teto de decode (bandwidth-bound; a regra que o próprio localmaxxing publica
mas não aplica): `ceiling_tok_s = bandwidth_gbs / (params_b_efetivo * bits/8)`
onde `params_b_efetivo = active_params_b` se MoE senão `params_b` (GB lidos
por token = pesos ativos; leitura de KV ignorada de propósito -> teto
superestimado -> só flagra o impossível de verdade).

`ratio = tok_s_out / ceiling_tok_s`. Verdicts:
- `exempt` (reason literal) se: `spec_decoding=1` ou `mtp_enabled=1` ou
  `batch_size>1` ou `concurrency>1` (batching/especulação quebram a premissa
  de 1 token por passada) ou bandwidth/params/bits null.
- `impossible` se ratio > IMPOSSIBLE_FRACTION.
- `suspicious` se ratio > SUSPICIOUS_FRACTION.
- `ok` caso contrário.

Agregados (S4) EXCLUEM runs `impossible`; `suspicious` entra com contagem
exposta. Nunca deletar runs: flag, não censura.

## 7. API HTTP (S5) — superfície literal

Sem auth (serviço local). JSON puro; erros `{"error": "..."}` com status
adequado.

```
GET /healthz                       -> {"ok": true, "runs": N, "lastSyncAt": iso|null}
GET /v1/rigs                       -> {rigs: Rig[]}            # schema web §4
GET /v1/models?category=           -> {models: DerivedModel[]} # schema web §4
GET /v1/plausibility/summary       -> {total, ok, suspicious, impossible, exempt,
                                       worst: [{runId, modelSlug, rigKey, ratio}] (top 10 ratio)}
GET /v1/match/hardware-to-models?rig_key=&bits=4&k=10
  -> {rig, picks: [{model, fit, estimate}]}    # escada idêntica ao engine web (§5 do contrato web)
GET /v1/match/model-to-hardware?model_slug=&bits=4&k=10
  -> {model, rigs: [{rig, fit, estimate}]}     # reverse lookup: rigs do pool onde cabe, rankeados
```

`fit` = "no"|"tight"|"ok"|"head" (regras web §5); `estimate` =
`{value, basis, n}` ou null. Implementação em `src/match.py` espelhando as
regras fechadas do contrato web §5-§6 (mesmas constantes, mesma escada).

## 8. Convenções

- Código/commits em inglês; specs/ESTADO em português.
- 1 sessão = 1 commit no git do monorepo: `feat(backend-S<n>): <resumo>`;
  só arquivos dentro de `apps/pool-backend/`.
- Oráculo único: `uv run python scripts/check.py <alvo>`; cada sessão adiciona
  seu alvo e mantém `all` (lista interna no próprio check.py).
- Funções 4-20 linhas, sem identificadores vagos, exceções com valor ofensor
  (convenções do monorepo hospedeiro).

## 9. Escopo negativo

- NÃO tocar em nada fora de `apps/pool-backend/` — exceção única: a cópia de
  `out/derived/*.json` para `../apps/web/data/derived/` (S4/S6).
- NÃO usar Postgres/Redis/Docker do monorepo; NÃO bindar porta fora do §3.
- NÃO usar POST contra a API deles; não raspar HTML; não burlar rate limit.
- NÃO inventar números: valor sem fonte no contrato/spec -> PARE e pergunte.
- NÃO implementar: auth, deploy remoto, scheduler embutido (agendamento é
  [A DEFINIR] com o dono — cron/launchd ficam de fora do v1), calibração de
  preditor da Fase 0 (pack futuro).
- NÃO deletar runs do banco por verdict; flag é metadado.
