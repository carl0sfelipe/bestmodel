{
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "wan2.2_i2v_high_noise_14B_fp16.safetensors",
      "weight_dtype": "default"
    },
    "_meta": { "title": "Wan 2.2 I2V High Noise 14B" }
  },
  "2": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "wan2.2_i2v_low_noise_14B_fp16.safetensors",
      "weight_dtype": "default"
    },
    "_meta": { "title": "Wan 2.2 I2V Low Noise 14B" }
  },
  "3": {
    "class_type": "CLIPLoader",
    "inputs": {
      "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
      "type": "wan",
      "device": "default"
    },
    "_meta": { "title": "UMT5-XXL fp8 (text encoder)" }
  },
  "4": {
    "class_type": "VAELoader",
    "inputs": { "vae_name": "wan_2.1_vae.safetensors" },
    "_meta": { "title": "Wan 2.1 VAE" }
  },
  "5": {
    "class_type": "LoadImage",
    "inputs": { "image": "__FIRST_IMAGE__" },
    "_meta": { "title": "First frame" }
  },
  "6": {
    "class_type": "LoadImage",
    "inputs": { "image": "__LAST_IMAGE__" },
    "_meta": { "title": "Last frame" }
  },
  "7": {
    "class_type": "CLIPTextEncode",
    "inputs": { "text": "__PROMPT__", "clip": ["3", 0] },
    "_meta": { "title": "Positive prompt" }
  },
  "9": {
    "class_type": "CLIPTextEncode",
    "inputs": { "text": "", "clip": ["3", 0] },
    "_meta": { "title": "Negative prompt (empty)" }
  },
  "8": {
    "class_type": "WanFirstLastFrameToVideo",
    "inputs": {
      "positive": ["7", 0],
      "negative": ["9", 0],
      "high_noise_model": ["1", 0],
      "low_noise_model": ["2", 0],
      "vae": ["4", 0],
      "width": __WIDTH__,
      "height": __HEIGHT__,
      "length": __FRAMES__,
      "batch_size": 1,
      "start_image": ["5", 0],
      "end_image": ["6", 0],
      "steps": __STEPS__,
      "cfg": __CFG__,
      "shift": __SHIFT__,
      "seed": __SEED__,
      "scheduler": "euler"
    },
    "_meta": { "title": "Wan 2.2 FLF2V (requires ComfyUI >= 0.3.48)" }
  },
  "10": {
    "class_type": "VAEDecode",
    "inputs": { "samples": ["8", 0], "vae": ["4", 0] },
    "_meta": { "title": "VAE Decode" }
  },
  "11": {
    "class_type": "SaveAnimatedWEBP",
    "inputs": {
      "images": ["10", 0],
      "filename_prefix": "wan22_flf2v",
      "fps": 16.0,
      "lossless": false,
      "quality": 90,
      "method": "default"
    },
    "_meta": { "title": "Save Animated WEBP" }
  }
}
