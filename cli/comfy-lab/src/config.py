COMFY_BASE_URL = "http://127.0.0.1:8188"
COMFY_ROOT = "/Users/mini/ComfyUI"
MODEL_DIRS = ["checkpoints", "diffusion_models", "unet", "vae",
              "text_encoders", "clip", "loras"]  # real subdirs of models/ (verified 2026-08-12)
HARDWARE_SNAPSHOT = "data/hardware-snapshot.json"
LOCAL_MODELS = "data/local-models.json"
RECIPE_VERSION = "comfy-r1"
# PROVISIONAL by design (no measured data yet; recalibrate in S6 with S4 data,
# same spirit as monorepo finding F2 — never loosen unilaterally):
PROVISIONAL_TIGHT_FRACTION = 0.8  # weights > 0.8 x vram_total -> "tight"
