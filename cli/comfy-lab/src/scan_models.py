"""Local model inventory: ComfyUI models/ subdirs -> data/local-models.json."""
import datetime
import json
import pathlib

from src.config import COMFY_ROOT, LOCAL_MODELS, MODEL_DIRS

MODEL_EXTENSIONS = {"safetensors", "ckpt", "pt", "gguf", "sft"}


def iter_model_files(base):
    for pattern in ("*", "*/*"):
        for path in sorted(base.glob(pattern)):
            if path.is_file() and path.suffix.lstrip(".").lower() in MODEL_EXTENSIONS:
                yield path


def scan(comfy_root):
    entries = []
    models_root = pathlib.Path(comfy_root) / "models"
    for subdir in MODEL_DIRS:
        base = models_root / subdir
        if not base.is_dir():
            continue
        for path in iter_model_files(base):
            entries.append({
                "file": path.name,
                "dir": subdir,
                "bytes": path.stat().st_size,
                "format": path.suffix.lstrip(".").lower(),
            })
    return entries


def write_catalog(entries, path):
    catalog = {
        "scannedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "models": entries,
    }
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, indent=2) + "\n")
    return out


if __name__ == "__main__":
    scanned = scan(COMFY_ROOT)
    written = write_catalog(scanned, LOCAL_MODELS)
    for name in MODEL_DIRS:
        print(f"{name}: {sum(1 for e in scanned if e['dir'] == name)}")
    print(f"catalog -> {written} ({len(scanned)} models)")
