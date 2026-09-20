# R00 — Semente: contrato do pack (JSON Schema) + modelos e verificador em Kotlin + estágio de referência

> Status: **DONE 2026-09-20** — oráculo verde nesta árvore (7 testes,
> `BUILD SUCCESSFUL`). Fica como spec porque o oráculo é o gate de regressão
> de tudo que vem depois: R02, R03 e R06 importam `shared/pack-schema`.

## Objetivo

Um único arquivo define o que é um pack de captura
(`shared/pack-schema/src/main/resources/rawpack/pack.schema.json`). Os modelos
Kotlin (`Manifest`, `CaptureRecord`, `ImuRecord`, `StageResult`) espelham o
schema e um teste falha se divergirem. `PackVerifier` prova integridade
(sha256, tamanho, caminho dentro do pack) — é o que o app roda antes de subir
e o que o ingest roda ao receber. `stages/s0-identity/bash/run` prova o
contrato de estágio sem tocar pixel.

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados.
NUNCA use declare const, stub ou mock de schema como workaround — o schema e
o único definidor; modelo que não valida contra ele é bug do modelo.
Nunca enfraquecer teste existente para passar.

## Dados verificados

- Árvore (verificado 2026-09-20): `settings.gradle.kts` inclui `:shared:pack-schema`;
  `build.gradle.kts` raiz com Kotlin 2.2.0; `gradle/wrapper/` commitado (8.14.3).
- `fixtures/pack-minimal/`: manifest com 7 arquivos e sha256 reais; 3 frames
  **placeholder de texto** (não são DNG — só o contrato é real aqui);
  `capture.jsonl` com 3 linhas (a primeira carrega chave extra de fornecedor);
  `imu.jsonl` com 3 linhas (gyro/accel); `fixtures/stage-result/identity.result.json`
  com `inputs_sha256` = sha256 do manifest da fixture.
- Testes em `PackContractTest` (7): round-trip do manifest; capture records
  válidos com chave extra tolerada; imu records; stage result; verificador
  aceita a fixture e nomeia arquivo adulterado; schema E verificador recusam
  `../calib.json`; schema rejeita `manifest@2`, `kind: magnetometer`, `stage: fuse`, path absoluto.
- Toolchain: JDK 21, Gradle 8.14.3, Kotlin 2.2.0, kotlinx-serialization 1.9.0,
  JUnit 5.11.4, networknt 1.5.6 (Maven Central, resolvido 2026-09-20).

## Verificação

VERIFICACAO: grep -q '"rawpack/manifest@1"' shared/pack-schema/src/main/resources/rawpack/pack.schema.json && grep -q 'object PackVerifier' shared/pack-schema/src/main/kotlin/run/bestmodel/rawpack/schema/PackVerifier.kt && grep -q 'stage-result@1' stages/s0-identity/bash/run

## Barra

- nome: o próprio `pack.schema.json` — toda linguagem valida contra ele.
- como fetchar: `cat shared/pack-schema/src/main/resources/rawpack/pack.schema.json`
- como comparar: os 7 testes de `PackContractTest` + `s0-identity` gerando
  `result.json` válido a partir da fixture. Levantar a barra = mais casos
  negativos no teste "schema rejects"; nunca remover um.

## Oráculo

- comando: test -x ./gradlew && ./gradlew :shared:pack-schema:test -q && rm -rf .dispatch/s0out && stages/s0-identity/bash/run --in fixtures/pack-minimal --out .dispatch/s0out && grep -q '"ok":true' .dispatch/s0out/result.json
- exit esperado: 0. Estado atual: passa (story concluída). Num checkout sem
  `gradlew` o oráculo falha com exit 1 pelo `test -x` — sem stderr, motivo certo.
