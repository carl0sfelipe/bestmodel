{
  "10": {
    "class_type": "WanFirstLastFrameToVideo",
    "inputs": {
      "positive": ["7", 0],
      "negative": ["9", 0],
      "vae": ["4", 0],
      "width": __WIDTH__,
      "height": __HEIGHT__,
      "length": __FRAMES__,
      "batch_size": 1,
      "start_image": ["5", 0],
      "end_image": ["6", 0]
    },
    "_meta": { "title": "Wan 2.2 FLF2V conditioning (ComfyUI >= 0.3.48 schema)" }
  },
  "3": {
    "class_type": "CLIPLoader",
    "inputs": { "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default" },
    "_meta": { "title": "UMT5-XXL fp8 (text encoder)" }
  },
  "4": {
    "class_type": "VAELoader",
    "inputs": { "vae_name": "wan_2.1_vae.safetensors" },
    "_meta": { "title": "Wan 2.1 VAE" }
  },
  "5": {
    "class_type": "LoadImage",
    "inputs": { "image": "first.png" },
    "_meta": { "title": "First frame" }
  },
  "6": {
    "class_type": "LoadImage",
    "inputs": { "image": "last.png" },
    "_meta": { "title": "Last frame" }
  },
  "7": {
    "class_type": "CLIPTextEncode",
    "inputs": { "text": "", "clip": ["3", 0] },
    "_meta": { "title": "Positive prompt" }
  },
  "9": {
    "class_type": "CLIPTextEncode",
    "inputs": { "text": "", "clip": ["3", 0] },
    "_meta": { "title": "Negative prompt (empty)" }
  },
  "1": {
    "class_type": "UNETLoader",
    "inputs": { "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default" },
    "_meta": { "title": "Wan 2.2 I2V High Noise 14B fp8" }
  },
  "2": {
    "class_type": "UNETLoader",
    "inputs": { "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default" },
    "_meta": { "title": "Wan 2.2 I2V Low Noise 14B fp8" }
  },
  "20": {
    "class_type": "KSamplerAdvanced",
    "inputs": {
      "model": ["1", 0],
      "add_noise": "enable",
      "noise_seed": __SEED__,
      "steps": __STEPS__,
      "cfg": __CFG__,
      "sampler_name": "euler",
      "scheduler": "simple",
      "start_at_step": 0,
      "end_at_step": 10,
      "return_with_leftover_noise": "enable",
      "positive": ["10", 0],
      "negative": ["10", 1],
      "latent_image": ["10", 2]
    },
    "_meta": { "title": "KSampler high-noise (steps 0-10)" }
  },
  "21": {
    "class_type": "KSamplerAdvanced",
    "inputs": {
      "model": ["2", 0],
      "add_noise": "disable",
      "noise_seed": __SEED__,
      "steps": __STEPS__,
      "cfg": __CFG__,
      "sampler_name": "euler",
      "scheduler": "simple",
      "start_at_step": 10,
      "end_at_step": __STEPS__,
      "return_with_leftover_noise": "disable",
      "positive": ["10", 0],
      "negative": ["10", 1],
      "latent_image": ["20", 0]
    },
    "_meta": { "title": "KSampler low-noise (steps 10-20)" }
  },
  "22": {
    "class_type": "VAEDecode",
    "inputs": { "samples": ["21", 0], "vae": ["4", 0] },
    "_meta": { "title": "VAE Decode" }
  },
  "23": {
    "class_type": "SaveAnimatedWEBP",
    "inputs": { "images": ["22", 0], "filename_prefix": "wan22_flf2v", "fps": 16.0, "lossless": false, "quality": 90, "method": "default" },
    "_meta": { "title": "Save Animated WEBP" }
  }
}
