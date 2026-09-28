# Diagnóstico CogVideoX-5b (2026-09-28) — integração pausa

O `transformer/` do `zai-org/CogVideoX-5b` (diffusers, 2 shards, 11,15 GB,
1024 tensores) contém um DiT **Conv2d, 16 canais de entrada, hidden 3072,
42 blocks, text_proj 3072→512** — ou seja, arquitetura estilo CogVideoX-1.5
que consome LATENTE de vídeo e um text-embed de 3072 dims.

- Merge dos shards: OK (`cogvideox_5b_transformer.safetensors`, 11,14 GB).
- ComfyUI 0.37 detecta o modelo (CogVideoX1_5) e **enfileira** o workflow ✓.
- Execução falha no conditioning: `mat1 2x3072 vs mat2 512x3072` — o
  `t5xxl_fp8_e4m3fn_scaled` (4096-dim, flux/wan) não é o encoder que o
  caminho nativo espera para este grafo.

Próximos passos para retomar: (1) identificar o text encoder nativo do
CogVideoX-1.5/5b no caminho da 0.37 (o `CLIPLoader type=cogvideox` espera
o par exato); (2) ou usar o repo Comfy-Org repackaged quando existir.
Arquivos preservados em `cogvideo/transformer/` no HDD.
