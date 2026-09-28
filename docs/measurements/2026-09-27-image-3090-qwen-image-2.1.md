# Image × rtx-3090-24gb — Qwen-Image 2.1 GGUF Q8_0, T2I 1024×1024

Dogfood 2026-09-27 (primeira rodada de imagem nesta máquina). Template oficial
`image_qwen_image_2_1_t2i.json` convertido para API via comfy-cli, com o UNETLoader
trocado por `UnetLoaderGGUF` (ComfyUI-GGUF custom node já instalado).

## Recipe

| Field | Value |
|---|---|
| GPU | RTX 3090 24 GiB (this host) |
| Model | `qwen-image-2.1-Q8_0.gguf` (7,59 GB, abenzerps/Qwen-Image-2.1-GGUF) |
| Text encoder | `qwen3vl_8b_int8_convrot.safetensors` (mesmo repo) |
| VAE | `qwen_image_2.1_vae_bf16.safetensors` |
| Sampler | euler · cfg 1.0 · 25 steps · 1024×1024 · seed fixa por run |

## Resultados

| Run | Wall | Basis |
|---|---:|---|
| cold (1º do boot, pesos no HDD) | 150,1 s | inclui load 7,6 GB + warmup CUDA |
| warm (seed 43) | 36,0 s | measured |
| warm (seed 44) | 35,9 s | measured |
| warm (seed 45) | 13,8 s | ⚠️ dedupe/cache parcial do ComfyUI — não usar |
| KSampler | **1,06–1,10 it/s** | log do ComfyUI |
| Peak VRAM | 17 340 MiB | amostragem 1 s |

## Armadilha registrada

O ComfyUI deduplica prompt idêntico (mesmo seed) e devolve o resultado em cache
(0,7–0,9 s). **Variar o seed entre runs** — caso idêntico ao ocorrido no vídeo
(célula de cache removida do banco em 2026-09-27).
