# R01 — Probe de capacidades do Galaxy S25 Ultra (app Android descartável, Kotlin)

## Objetivo

Antes de desenhar o app de captura, saber o que a Samsung expõe a um app de
terceiro no SM-S938x: câmeras lógicas/físicas, nível de hardware,
resoluções `RAW_SENSOR`/`JPEG`/`JPEG_R` por câmera, chaves de `CaptureResult`
disponíveis (OIS, lens shading map, noise profile, rolling shutter skew,
faces, flicker), calibração de lente e quais Extensions do CameraX existem
(HDR, NIGHT, BOKEH, FACE_RETOUCH, AUTO). O app grava um JSON e o dono o
commita em `docs/device/SM-S938B.device-probe.json`. O pack (R02) só carrega
o que este JSON provar que existe.

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados —
resolução, fps ou chave que o aparelho não reportar fica [A DEFINIR] no JSON,
nunca preenchido de ficha técnica. NUNCA use declare const, mock de
`CameraCharacteristics` ou valor hardcoded como workaround no app real; mock
só no teste de unidade do escritor de JSON.

## Dados verificados

- API oficial (verificado em developer.android.com, 2026-09-20): CameraX 1.5
  expõe `ImageCapture.OUTPUT_FORMAT_RAW` e `OUTPUT_FORMAT_RAW_JPEG` com
  `ImageCapture.getImageCaptureCapabilities(cameraInfo).supportedOutputFormats`;
  Extensions via `ExtensionsManager.getInstanceAsync` + `isExtensionAvailable`.
- Camera2 (API 28+): `CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES`
  (RAW, LOGICAL_MULTI_CAMERA), `getPhysicalCameraIds()`,
  `SCALER_STREAM_CONFIGURATION_MAP.getOutputSizes(ImageFormat.RAW_SENSOR)`,
  `getAvailableCaptureResultKeys()`, `LENS_INTRINSIC_CALIBRATION`,
  `LENS_DISTORTION`, `LENS_POSE_ROTATION/TRANSLATION`, `SENSOR_INFO_TIMESTAMP_SOURCE`,
  `STATISTICS_INFO_AVAILABLE_OIS_DATA_MODES`, `STATISTICS_INFO_AVAILABLE_LENS_SHADING_MAP_MODES`.
- Relato de comunidade (r/GalaxyS25Ultra, 2026): teles bloqueadas para
  terceiros, principal com LEVEL_3, ultrawide limitada — **é hipótese a
  confirmar pelo probe, não dado**.
- Toolchain: Android SDK **não** existe nesta máquina de spec; build
  `apps/android/` é separado do build JVM raiz (ver `settings.gradle.kts`).
- Schema: `pack.schema.json` não tem `$defs/DeviceProbe` ainda — esta story
  o adiciona (aditivo) e o teste de R00 continua verde.

## Entregáveis (caminhos exatos)

- `apps/android/settings.gradle.kts` (AGP 8.x, `includeBuild("../..")` para
  consumir `:shared:pack-schema` por substituição de dependência).
- `apps/android/capture-probe/` — um Activity: botão "Probe", progresso,
  escreve `device-probe.json` em `getExternalFilesDir` e abre share sheet.
- `shared/pack-schema/src/main/resources/rawpack/pack.schema.json` — novo
  `$defs/DeviceProbe`: `{schema:"rawpack/device-probe@1", device{model,soc,os},
  cameras:[{id, facing, hardware_level, capabilities[], physical_ids[],
  raw_sizes:[[w,h]], jpeg_sizes, jpeg_r_sizes, result_keys[], timestamp_source,
  ois_modes[], lens_shading_modes[], has_intrinsics, has_distortion}],
  camerax:{output_formats[], extensions:{hdr,night,bokeh,face_retouch,auto}}}`.
- `shared/pack-schema/.../schema/DeviceProbe.kt` modelo Kotlin + caso no `PackContractTest`.
- `apps/android/capture-probe/src/test/...ProbeJsonWriterTest.kt` — escritor
  de JSON testado com dados fake explícitos (marcados fake) e validado contra
  o schema.
- `docs/device/README.md` — como rodar no aparelho e onde commitar o JSON.

## Comportamentos obrigatórios

1. O JSON valida contra `$defs/DeviceProbe` (teste JVM).
2. Tudo que o aparelho não reporta sai como `null`/lista vazia, nunca como
   valor default plausível.
3. O app nunca abre sessão de captura — só lê características e Extensions.
4. Barra do dono: `docs/device/SM-S938B.device-probe.json` commitado, com
   `cameras[].raw_sizes` não vazio para a câmera principal.

## Verificação

VERIFICACAO: grep -q 'device-probe@1' shared/pack-schema/src/main/resources/rawpack/pack.schema.json && grep -q 'DeviceProbe' shared/pack-schema/src/test/kotlin/run/bestmodel/rawpack/schema/PackContractTest.kt && test -f apps/android/capture-probe/build.gradle.kts

## Barra

- nome: `docs/device/SM-S938B.device-probe.json` (a verdade do aparelho).
- como fetchar: rodar o probe no SM-S938x e compartilhar o arquivo.
- como comparar: R02 só declara no pack chaves presentes em `result_keys[]`
  e resoluções presentes em `raw_sizes` deste arquivo.

## Oráculo

- comando: test -x ./gradlew && ./gradlew :shared:pack-schema:test -q && test -x apps/android/gradlew && cd apps/android && ./gradlew :capture-probe:testDebugUnitTest -q
- exit esperado: 0 na máquina com Android SDK. Antes da implementação:
  exit 1 pelo `test -x apps/android/gradlew` (sem stderr) — vermelho pelo
  motivo certo. Sem SDK o segundo gradlew falha com mensagem do AGP: nesse
  caso o executor registra a limitação e a barra fica com o dono.
