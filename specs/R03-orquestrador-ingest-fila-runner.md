# R03 — Orquestrador (Kotlin/Ktor 3): ingest via hook do tusd, fila em SQLite, runner de estágios com contrato

## Objetivo

O servidor da 3090 recebe o tar do pack (hook `post-finish` do tusd),
desempacota em `packs/<pack_id>/`, verifica com `PackVerifier`, registra a
captura, e roda a cadeia de estágios declarada em `pipeline.json` executando
cada `stages/<id>/<impl>/run` como subprocesso com teto de tempo, validando
o `result.json` contra o schema e gravando job, candidatos e eventos. Sem
Redis no MVP: fila é tabela SQLite com polling por coroutine. Um lock de GPU.

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados —
tetos de tempo e caminhos são configuração (`pipeline.json`, env), nunca
constantes escondidas. NUNCA use declare const, `TODO()` ou mock de estágio
no código de produção; o único estágio "fake" permitido é o `s0-identity/bash`
real, que já existe. Nunca leia veredito de estágio de outra fonte que não o
`result.json` validado.

## Dados verificados

- Contrato: `stages/CONTRACT.md` (v1) e `$defs/StageResult` em
  `pack.schema.json` (R00, verde). Estágio de referência
  `stages/s0-identity/bash/run` gera `result.json` válido a partir de
  `fixtures/pack-minimal` (verificado 2026-09-20, `wall_s` ≈ 0.002).
- Hook do tusd (`post-finish`): POST JSON com `Type` e `Event.Upload{ID, Size,
  Storage{Path}, MetaData{filename, pack_id, sha256}}` — forma da doc do tusd;
  o executor confirma contra a versão instalada e fixa o exemplo em
  `apps/orchestrator/src/test/resources/tusd-post-finish.json`.
- Toolchain verificada: JDK 21, Gradle 8.14.3, Kotlin 2.2.0 (build raiz).
  Bibliotecas a pinar pelo executor a partir do Maven Central (versão exata
  = a que resolver no dia, registrada no `build.gradle.kts`): Ktor 3.x
  (server-netty, content-negotiation, serialization-kotlinx-json,
  server-test-host), Exposed 0.6x + `org.xerial:sqlite-jdbc`,
  `commons-compress` (untar), `networknt json-schema-validator` (já usada
  nos testes da R00 — aqui vira dependência de produção).
- `bin/with-timeout.sh` do llms.surf mata a **árvore** de processos ao
  estourar; o runner faz o mesmo (`ProcessHandle.descendants()` + destroy).

## Entregáveis (caminhos exatos)

- `apps/orchestrator/build.gradle.kts`; registrado em `settings.gradle.kts`.
- `apps/orchestrator/src/main/kotlin/run/bestmodel/rawpack/orchestrator/`
  - `App.kt` — Ktor: `POST /hooks/tus`, `GET /captures`, `GET /captures/{id}`,
    `GET /health` (versão + sha do git via env `GIT_SHA`).
  - `db/Schema.kt` — tabelas `capture(id, pack_id, received_at, dir, verified, device_model)`,
    `job(id, capture_id, stage, impl, status queued|running|done|failed, attempts, started_at, finished_at, notes)`,
    `candidate(id, capture_id, job_id, path, kind, sha256)`, `event(id, capture_id, ts, kind, payload_json)`.
  - `ingest/Ingest.kt` — untar para `PACKS_DIR/<pack_id>/` (recusa entradas
    com `..`), `PackVerifier.verify`; falha → HTTP 422 + evento `pack_rejected`,
    nada enfileirado; sucesso → `capture` + jobs da cadeia em ordem.
  - `runner/StageRunner.kt` — executa `run --in <dir> --out <PACKS_DIR>/<pack_id>/out/<stage>/ --params <file>`
    com teto `timeout_s` do `pipeline.json`; valida `result.json`; `ok:false`
    ou inválido → `job.failed` com `notes`; saídas com `kind` iniciado em
    `candidate` viram linhas `candidate`.
  - `runner/Worker.kt` — coroutine: pega o job `queued` mais antigo cuja
    dependência anterior está `done`; `Mutex` global para estágios com
    `gpu: true`; encadeia `--in` do estágio N+1 = `out/<stage N>` quando
    `pipeline.json` diz `input: previous`, senão o pack.
- `pipeline.json` na raiz: `[{"stage":"s0-identity","impl":"bash","input":"pack","timeout_s":60,"gpu":false}]`
  no MVP; R04 acrescenta s1/s2.
- Testes `apps/orchestrator/src/test/kotlin/...`:
  1. hook com tar da `fixtures/pack-minimal` → 202, `capture` criada, 1 job `queued`;
  2. worker roda `s0-identity/bash` → job `done`, `result.json` validado,
     `inputs_sha256` igual ao sha do manifest;
  3. tar com frame adulterado → 422, zero jobs, evento `pack_rejected` com o path;
  4. estágio que sai com exit 4 (script de teste em `src/test/resources/stages/`)
     → job `failed`, `notes` com o stderr truncado;
  5. estágio que dorme além do `timeout_s` → morto, job `failed`, sem
     processo órfão (`ProcessHandle` não vivo).
  Tudo com SQLite em arquivo temporário e `PACKS_DIR` temporário.

## Comportamentos obrigatórios

1. Nenhum estado fora de SQLite + `PACKS_DIR` + `events.jsonl` por captura.
2. Reinício do processo não perde jobs `queued`; jobs `running` órfãos voltam
   a `queued` com `attempts+1` (máx. 3, depois `failed`).
3. `GET /captures/{id}` devolve jobs, candidatos e últimos 50 eventos — é o
   que a R05 renderiza.
4. Logs em stdout com `pack_id` e `job_id` em toda linha.

## Verificação

VERIFICACAO: grep -q ':apps:orchestrator' settings.gradle.kts && grep -q 'hooks/tus' -r apps/orchestrator/src/main && test -f pipeline.json && grep -q 's0-identity' pipeline.json

## Barra

- nome: `stages/s0-identity/bash/run` sobre `fixtures/pack-minimal` (o mesmo
  estágio que o dispatcher do llms.surf chama no oráculo da R00).
- como fetchar: `./gradlew :apps:orchestrator:test`.
- como comparar: os 5 testes acima; depois, na 3090, um pack real do R02
  atravessa hook → verify → s0 → `GET /captures/{id}` com job `done`.

## Oráculo

- comando: test -x ./gradlew && ./gradlew :shared:pack-schema:test :apps:orchestrator:test -q
- exit esperado: 0. Antes da implementação: Gradle falha com "project
  ':apps:orchestrator' not found" (exit 1, sem `command not found`) —
  vermelho pelo motivo certo; verificado com `check-oracle.py` em 2026-09-20.
