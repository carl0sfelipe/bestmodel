"""Hardware probe: ComfyUI /system_stats -> data/hardware-snapshot.json."""
import datetime
import json
import pathlib
import sys

import httpx

from src.config import COMFY_BASE_URL, HARDWARE_SNAPSHOT


def fetch_system_stats():
    try:
        response = httpx.get(f"{COMFY_BASE_URL}/system_stats", timeout=2.0)
    except httpx.ConnectError:
        print(f"ComfyUI server not running at {COMFY_BASE_URL}", file=sys.stderr)
        sys.exit(3)
    response.raise_for_status()
    return response.json()


def snapshot_to_file(stats, path):
    snapshot = dict(stats)
    snapshot["capturedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshot["source"] = "live"
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2) + "\n")
    return out


if __name__ == "__main__":
    stats = fetch_system_stats()
    written = snapshot_to_file(stats, HARDWARE_SNAPSHOT)
    device = stats["devices"][0]
    print(f"snapshot -> {written} ({device['name']}, vram_total={device['vram_total']})")
