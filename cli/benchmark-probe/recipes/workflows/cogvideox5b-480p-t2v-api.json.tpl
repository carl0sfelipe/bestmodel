{
  "1": {
    "class_type": "UNETLoader",
    "inputs": { "unet_name": "cogvideox_5b_transformer.safetensors", "weight_dtype": "default" },
    "_meta": { "title": "CogVideoX-5B transformer" }
  },
  "2": {
    "class_type": "CLIPLoader",
    "inputs": { "clip_name": "t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "cogvideox", "device": "default" },
    "_meta": { "title": "T5-XXL fp8 (text encoder)" }
  },
  "3": {
    "class_type": "CLIPTextEncode",
    "inputs": { "text": "__PROMPT__", "clip": ["2", 0] },
    "_meta": { "title": "Positive prompt" }
  },
  "4": {
    "class_type": "CLIPTextEncode",
    "inputs": { "text": "", "clip": ["2", 0] },
    "_meta": { "title": "Negative prompt (empty)" }
  },
  "5": {
    "class_type": "EmptyHunyuanLatentVideo",
    "inputs": { "width": __WIDTH__, "height": __HEIGHT__, "length": __FRAMES__, "batch_size": 1 },
    "_meta": { "title": "Empty video latent (CogVideoX 16ch)" }
  },
  "6": {
    "class_type": "ModelSamplingSD3",
    "inputs": { "model": ["1", 0], "shift": __SHIFT__ },
    "_meta": { "title": "ModelSamplingSD3 (flow shift)" }
  },
  "7": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["6", 0],
      "positive": ["3", 0],
      "negative": ["4", 0],
      "latent_image": ["5", 0],
      "seed": __SEED__,
      "steps": __STEPS__,
      "cfg": __CFG__,
      "sampler_name": "euler",
      "scheduler": "simple",
      "denoise": 1.0
    },
    "_meta": { "title": "KSampler" }
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": { "samples": ["7", 0], "vae": ["9", 0] },
    "_meta": { "title": "VAE Decode" }
  },
  "9": {
    "class_type": "VAELoader",
    "inputs": { "vae_name": "cogvideox_vae_diffusers.safetensors" },
    "_meta": { "title": "CogVideoX VAE" }
  },
  "10": {
    "class_type": "SaveAnimatedWEBP",
    "inputs": { "images": ["8", 0], "filename_prefix": "cogvideox_5b", "fps": 8.0, "lossless": false, "quality": 90, "method": "default" },
    "_meta": { "title": "Save Animated WEBP" }
  }
}
