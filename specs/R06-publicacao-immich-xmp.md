# R06 — Publicar o aprovado no Immich com a receita ao lado (XMP), idempotente

## Objetivo

Quando uma decisão `approve` existe (R05), o orquestrador sobe o JPEG
aprovado para o Immich do dono via API, grava `publication(capture_id,
candidate_id, immich_asset_id, sha256)` e escreve `published/<candidate>.xmp`
no diretório da captura com a receita completa (cadeia de estágios, impl,
params, `inputs_sha256`, seeds) — qualquer imagem publicada é reproduzível a
partir do pack. O pack original nunca é tocado.

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados —
rota, campos e versão da API do Immich são confirmados contra o servidor do
dono (`GET /api/server/version`) e registrados no commit; o que não for
confirmado fica [A DEFINIR] e a story não o usa. NUNCA use declare const,
cliente HTTP mockado em produção ou `asset_id` sintético; idempotência é por
sha256 do candidato, não por "já tentei".

## Dados verificados

- Immich (verificado 2026-09-20 no GitHub/imm docs): suporta RAW/DNG, stacks,
  API keys (`x-api-key`), upload de asset por multipart em `POST /api/assets`
  com `assetData`, `deviceAssetId`, `deviceId`, `fileCreatedAt`,
  `fileModifiedAt`; v3.0 acrescenta Workflows com webhooks. A rota/campos
  exatos de **stacks** variam por versão — [A DEFINIR] pelo executor contra
  o servidor do dono; se ausente, publicar sem stack e registrar.
- R05 grava `decision` com `verdict=approve` e a R03 conhece `candidate.path`
  e `sha256`.
- XMP: sidecar texto (RDF/XML) com namespace próprio
  `xmlns:rawpack="https://bestmodel.run/rawpack/ns/1"`; leitores comuns
  ignoram o que não conhecem — o darktable lê o seu, o nosso vai junto.
- Segredos: `IMMICH_URL`, `IMMICH_API_KEY` por env; nunca em arquivo commitado
  (mesma regra do `deploy/.env` do bestmodel).

## Entregáveis (caminhos exatos)

- `apps/orchestrator/src/main/kotlin/run/bestmodel/rawpack/orchestrator/publish/`
  - `ImmichClient.kt` — Ktor client: `serverVersion()`, `uploadAsset(file, createdAt)`
    → `assetId`; opcional `createStack(ids)` guardado por feature flag
    `IMMICH_STACKS=true` só após confirmação da rota.
  - `Publisher.kt` — dispara ao evento `decision_made(approve)`: se já existe
    `publication` com o mesmo `sha256` → no-op; senão upload, XMP, linha,
    evento `published`.
  - `RecipeXmp.kt` — monta o XMP a partir de `job`/`result.json` da cadeia.
  - `db/Schema.kt` — tabela `publication`.
- Testes (`PublisherTest`, Ktor `MockEngine`):
  1. approve → um `POST /api/assets` com header `x-api-key`, multipart com
     `assetData` e `deviceAssetId = <pack_id>/<candidate sha>`; `publication` gravada;
  2. segundo approve do mesmo candidato → zero chamadas HTTP;
  3. Immich responde 500 → sem `publication`, evento `publish_failed`, job
     de publicação volta a `queued` (máx. 3);
  4. XMP contém `rawpack:inputs_sha256` igual ao do `result.json` do s2 e a
     lista ordenada de estágios/impl;
  5. `IMMICH_API_KEY` ausente → publisher recusa iniciar com mensagem, nunca
     tenta sem chave.

## Comportamentos obrigatórios

1. Upload usa o arquivo do candidato como está (sem recompressão).
2. `fileCreatedAt` = `manifest.captured_at` (a data da foto, não a da publicação).
3. Pack e candidatos permanecem em `PACKS_DIR`; retenção é política futura, não desta story.
4. Falha de rede nunca perde a decisão: `decision` já está gravada; só a publicação repete.

## Verificação

VERIFICACAO: grep -q 'x-api-key' -r apps/orchestrator/src/main/kotlin && grep -q 'rawpack:inputs_sha256' -r apps/orchestrator/src/main/kotlin && grep -q 'publication' -r apps/orchestrator/src/main/kotlin/run/bestmodel/rawpack/orchestrator/db

## Barra

- nome: Immich do dono mostrando o JPEG aprovado de uma captura real, com
  `fileCreatedAt` = hora da foto.
- como fetchar: `GET /api/assets/{id}` no Immich + `published/*.xmp` no
  diretório da captura.
- como comparar: os 5 testes acima; depois a publicação real (screenshot do
  Immich em `docs/device/`).

## Oráculo

- comando: test -x ./gradlew && ./gradlew :apps:orchestrator:test -q --tests '*PublisherTest*'
- exit esperado: 0. Antes da implementação: exit 1 sem `command not found`
  — vermelho pelo motivo certo.
