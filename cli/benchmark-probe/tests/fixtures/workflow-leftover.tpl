{
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "fixture-high-noise.safetensors",
      "weight_dtype": "default"
    }
  },
  "8": {
    "class_type": "WanFirstLastFrameToVideo",
    "inputs": {
      "positive": ["7", 0],
      "negative": ["9", 0],
      "vae": ["4", 0],
      "width": __WIDTH__,
      "height": __HEIGHT__,
      "length": __FRAMES__,
      "steps": __STEPSS__,
      "cfg": __CFG__,
      "shift": __SHIFT__,
      "seed": __SEED__
    }
  }
}
