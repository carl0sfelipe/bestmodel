# Audio × rtx-3090-24gb — REPRO do Whisper Large v3 Turbo (FLEURS `pt_br`)

Dogfood 2026-09-27. Reprodução independente da célula de 2026-09-23
(`whisper-large-v3-turbo`, 39,22×real, WER 0.04) seguindo o protocolo
daquele arquivo: faster-whisper 1.2.1, CUDA fp16, `language=pt`,
`beam_size=5`, `vad_filter=True`, FLEURS `pt_br` test oficial,
velocidade = 3 reps nos primeiros 48 clipes, WER = passada full
(NFKC + lower + strip de pontuação).

## Resultados do repro

| Métrica | Repro (2026-09-27) | Célula original (2026-09-23) |
|---|---:|---:|
| `audioXReal` (mediana, n=3) | **44,93** (42,85 / 45,38 / 44,93*) | 39,22 (39,08 / 40,14 / 39,22) |
| Passada full — ×real | 41,51 (280,9 s p/ 11 660 s de áudio) | 38,21 |
| WER (full, 919 clipes) | **0,0988** | 0,04 |

\* primeira rep do primeiro script mediu generator não-consumido (153–177×real
— irreal): transcrição lazy do faster-whisper exige iterar os segmentos.

## Leitura

- **Velocidade confirmada**: 41–45×real no mesmo protocolo — a célula
  39,22×real se reproduz dentro da variância (caches quentes no repro).
- **WER divergiu (0,0988 vs 0,04)** com a mesma normalização declarada.
  Hipóteses: detalhe de join dos segmentos, tratamento de clipes silenciosos
  com VAD, ou diferença de referência (o TSV é headerless e a coluna de
  referência usada foi a normalizada). **Manter a célula 0.04 como
  `reported` e não subir a 0.0988 sem reconciliação de método.**

## Artefatos

- Script + resultado: `/data/bestmodel/audio/{repro.py,repro.log,stt_repro_result.json}`
- Modelo: `deepdml/faster-whisper-large-v3-turbo-ct2` (1,6 GB), FLEURS pt_br
  test (919 wavs) em `/data/bestmodel/audio/`
