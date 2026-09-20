# R02 — App de captura v0 (Kotlin, CameraX 1.5): burst RAW + contexto + pack + upload tus

## Objetivo

Um app "burro e fiel": mostra preview, dispara N capturas RAW (DNG) + 1 JPEG
de referência, grava `capture.jsonl` (CaptureResult por frame), `imu.jsonl`
(giroscópio/acelerômetro no relógio da câmera), `calib.json`, monta o pack
com `manifest.json` (sha256 de tudo), verifica com `PackVerifier`, empacota
em tar e sobe por tus para a máquina da 3090 quando há Wi-Fi e carregador.
Zero processamento de pixel no telefone.

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados:
N default, resolução e fps vêm de `docs/device/SM-S938B.device-probe.json`
(R01) — se o arquivo não existir, o app usa a MAIOR resolução RAW reportada
pelo próprio aparelho em tempo de execução e registra `sensor_mode.reason`.
NUNCA use declare const, `@Suppress` de erro ou frame sintético como
workaround; DNG que não veio do sensor não entra no pack. Nunca aplique
demosaic, denoise, nitidez ou tone-map no app.

## Dados verificados

- CameraX 1.5 (verificado developer.android.com 2026-09-20): `OUTPUT_FORMAT_RAW_JPEG`
  entrega DNG + JPEG numa chamada `takePicture(rawOptions, jpegOptions, ...)`;
  `OUTPUT_FORMAT_RAW` entrega só DNG; `DngCreator` é interno ao CameraX.
  Callback dispara duas vezes, ordem não garantida — checar `getImageFormat()`.
- Burst v0 = N `takePicture` sequenciais em RAW (CameraX não tem ring buffer
  ZSL de RAW); ZSL/`captureBurst` via Camera2 fica para R07. Registrar no
  manifest `notes: "burst=sequential-v0"`.
- `CaptureResult` completo por frame só via Camera2 interop
  (`Camera2Interop.Extender.setSessionCaptureCallback`).
- IMU: `SensorManager` com `SENSOR_DELAY_FASTEST`; timestamps de sensor em
  `elapsedRealtimeNanos`; a câmera reporta `SENSOR_INFO_TIMESTAMP_SOURCE`
  (REALTIME ou UNKNOWN) — gravar a fonte no manifest `notes`; se UNKNOWN, o
  alinhamento IMU↔frame é [A DEFINIR] no servidor, nunca "assumido igual".
- Orçamento de RAM (aritmética, não medição): 12 MP RAW16 ≈ 24 MB por frame;
  N default 8 → ≈ 200 MB por pack antes do tar.
- Upload: protocolo tus (resumível) — servidor `tusd` na 3090 (R03) atrás de
  Tailscale; cliente `io.tus.android.client`. Endpoint e token vêm de tela
  de configuração, nunca hardcoded.
- Schema e verificador: `shared/pack-schema` (R00, verde) — o app consome
  por composite build (`includeBuild("../..")` em `apps/android`).

## Entregáveis (caminhos exatos)

- `apps/android/capture-android/` — módulo do app (`applicationId run.bestmodel.rawpack.capture`).
- `.../capture/PackWriter.kt` — recebe frames (path + `CaptureRecord`), IMU,
  calib; escreve `manifest.json` via `Manifest` do pack-schema; chama
  `PackVerifier.verify` e recusa subir pack com `problems` não vazio.
- `.../capture/ImuLogger.kt` — buffer circular iniciado 300 ms antes do 1º
  disparo, fechado 300 ms depois do último; grava `imu.jsonl`.
- `.../capture/TarPacker.kt` — tar sem compressão (DNG não comprime) → `<pack_id>.tar`.
- `.../upload/TusUploadWorker.kt` — WorkManager, constraints
  `NetworkType.UNMETERED` + `requiresCharging` (toggle), retries com backoff;
  metadata tus: `filename=<pack_id>.tar`, `pack_id`, `sha256` do tar.
- `.../ui/CaptureScreen.kt` — preview, shutter, N (1–15), toggle "carregando", fila de upload.
- Testes JVM em `apps/android/capture-android/src/test/`: `PackWriterTest`
  (manifest gerado de frames fake explícitos → `PackVerifier` ok; frame
  faltando → recusa), `ImuLoggerTest` (janela e ordenação por `t_ns`),
  `TarPackerTest` (round-trip lista de entradas).

## Comportamentos obrigatórios

1. Pack no disco antes de qualquer upload; upload nunca apaga o pack — só
   marca `uploaded_at` num índice local (`packs.index.jsonl`).
2. `manifest.frames[0].role == reference` e é o frame com JPEG par.
3. `capture.jsonl` tem exatamente uma linha por DNG, com `timestamp_ns` igual
   ao `SENSOR_TIMESTAMP` do frame.
4. Falha de verificação (sha, tamanho, arquivo faltando) bloqueia o upload e
   aparece na tela — nunca sobe pack quebrado.
5. Barra do dono: um pack real do SM-S938x chega ao tusd e `PackVerifier`
   no servidor (R03) devolve `ok`.

## Verificação

VERIFICACAO: test -f apps/android/capture-android/build.gradle.kts && grep -q 'OUTPUT_FORMAT_RAW' -r apps/android/capture-android/src/main && grep -q 'PackVerifier' -r apps/android/capture-android/src/main

## Barra

- nome: `fixtures/pack-minimal` (forma) + primeiro pack real do SM-S938x (substância).
- como fetchar: `tar -tf <pack_id>.tar` no servidor; `PackVerifier.verify`.
- como comparar: mesmo `manifest.json` válido, `frames.size == N`, todas as
  linhas de `capture.jsonl` validando contra `$defs/CaptureRecord`.

## Oráculo

- comando: test -x apps/android/gradlew && cd apps/android && ./gradlew :capture-android:testDebugUnitTest -q
- exit esperado: 0 na máquina com Android SDK. Antes da implementação: exit 1
  pelo `test -x` (sem stderr) — vermelho pelo motivo certo. Barra no aparelho
  não é oráculo de CI.
