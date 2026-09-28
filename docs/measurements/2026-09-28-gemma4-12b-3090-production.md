# Gemma 4 12B em produção × rtx-3090-24gb — esta máquina

Implantação de produção 2026-09-28 (missão `/opt/inference`, repo privado
`inference-paraguai`). Diferente das células de benchmark: aqui o número existe
porque o serviço **está vendendo por token** em `https://gemma.bestmodel.run/v1`.

## O que é medido

Throughput de decode e TTFT no serviço real (vLLM 0.30, checkpoint QAT W4A16
`google/gemma-4-12B-it-qat-w4a16-ct`, contexto 32k, streaming, `max_tokens` 200,
prompt PT-BR ~25 tokens). Script: `report/perf_test.py` no repo da missão.

| Cenário | Decode | TTFT |
|---|---|---|
| 1 requisição | **66,5 tok/s** | 253 ms |
| 8 simultâneas | **485,7 tok/s** total (≈61 tok/s cada) | 126 / 224 / 225 ms (min/med/max) |

VRAM 22 842/24 576 MiB · 45 °C em carga · KV cache 167 544 tokens (5,1× a 32k).

## Por que W4A16 e não FP8 na 3090

FP8 online (`--quantization fp8`) crasha: o vLLM 0.30 despacha o GEMM para
`cutlass_scaled_mm_sm80_epilogue` (w8a8 SM80) que não suporta as formas do
Gemma4 (head_dim 256/512 híbrido). Ampere não tem tensor core FP8; o caminho
"FP8 pesos via Marlin" não existe para este modelo nesta versão. QAT W4A16
oficial do Google: 8,28 GiB de pesos, kernels Marlin maduros em Ampere,
qualidade de treino quantização-consciente (superior a PTQ/AWQ).

## Multimodal verificado (não assumido)

- imagem (`image_url` base64): leu OCR exato de 3 linhas num PNG gerado localmente.
- áudio via chat (`input_audio`): FLEURS `pt_br` humano 17,8 s → transcrição
  quase idêntica à referência do TSV (diffs: "Bieber"→"Biber", "20"→"vinte").
- `POST /v1/audio/transcriptions`: **não existe** no vLLM 0.30 (404).
- Voz robótica (espeak-ng) é rejeitada pelo modelo — qualidade de áudio importa.

## Honestidade

- Números de **decode** com batch 1 e 8, sem varredura de batch maior; a 3090
  satura em ~485 tok/s com 8 — não extrapolar linearmente.
- Áudio de reunião/telefonia **não validado** (só read speech FLEURS).
- WER formal do Gemma 4 ASR não medido aqui (a passagem do FLEURS foi 1 clipe,
  qualitativa). Não citar como número WER.

## Reproduzir

Repo `inference-paraguai`: `vllm/docker-compose.yml` sobe o serviço idêntico;
`report/perf_test.py` é o harness; `report/FINAL.md` é o dossiê completo
de operação (chaves por cliente, gateway LiteLLM, túnel, monitores).
