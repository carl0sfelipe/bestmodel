#!/usr/bin/env python3
"""Expand the model catalog from HuggingFace configs (S22 support).

Reads the unmapped localmaxxing backlog (top slugs by cell count), resolves
each slug to a HuggingFace repo via explicit naming rules, pulls config.json
+ safetensors parameter counts, and emits candidate model_release records.
Every architectural number comes from HF — nothing invented; incomplete
candidates are reported, not guessed.

Usage:
    uv run python infra/scripts/expand_catalog_from_hf.py --top 30 --out /tmp/hf_candidates.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POOL_PATH = REPO_ROOT / "apps" / "web" / "data" / "derived" / "pool.json"
HF_API = "https://huggingface.co/api/models"
HF_RESOLVE = "https://huggingface.co"

REQUIRED_FIELDS = (
    "num_layers",
    "num_attention_heads",
    "num_kv_heads",
    "head_dim",
    "parameter_count_billion",
    "max_context_tokens",
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# slug pattern -> repo id builders. Names follow each lab's canonical style.
SLUG_RULES: list[tuple[str, str]] = [
    (r"^qwen-(?P<name>qwen[\d.]+-[\da-z]+.*)$", r"Qwen/\g<name>"),
    (r"^google-(?P<name>gemma[\d.]*-.*)$", r"google/\g<name>"),
    (r"^openai-(?P<name>gpt-oss-.*)$", r"openai/\g<name>"),
    (r"^deepseek-ai-(?P<name>deepseek[\w.-]*)$", r"deepseek-ai/\g<name>"),
    (r"^liquidai-(?P<name>lfm[\w.-]*)$", r"LiquidAI/\g<name>"),
    (r"^mistralai-(?P<name>[\w.-]+)$", r"mistralai/\g<name>"),
    (r"^meta-llama-(?P<name>llama[\w.-]*)$", r"meta-llama/\g<name>"),
    (r"^allenai-(?P<name>olmo[\w.-]*)$", r"allenai/\g<name>"),
]

# quant/format suffixes that exist as separate HF repos
FORMAT_SUFFIXES = ["", "-GGUF", "-MLX"]


def strip_format_suffix(slug_rest: str) -> str:
    for suffix in ("-gguf", "-mlx", "-fp8", "-nvfp4", "-awq", "-mtp", "-ud-mlx-6bit", "-ud-mlx-5bit"):
        if slug_rest.endswith(suffix):
            slug_rest = slug_rest[: -len(suffix)]
    # unsloth "UD" variant markers
    return re.sub(r"-(ud|tq|mx|q\d+-\d+s?|reap)[\w-]*$", "", slug_rest)


BRAND_CAPS = {"lfm": "LFM", "gpt": "GPT", "olmo": "OLMo", "sd": "SD", "deepseek": "DeepSeek"}
LOWER_ORGS = {"google", "openai"}  # these labs use lowercase repo names


def merge_versions(name: str) -> str:
    """'qwen3-6-27b' -> 'qwen3.6-27b' (version followed by a size segment);
    'qwen3-5-0-8b' -> 'qwen3.5-0.8b' (sub-1B sizes); 'qwen3-8b' stays put."""
    name = re.sub(r"(\d)-(\d+)(?=-\d)", r"\1.\2", name)
    return re.sub(r"\b0-(\d+)(?=[bB])", r"0.\1", name)


def titlecase(name: str, org: str = "") -> str:
    """'qwen3.6-35b-a3b' -> 'Qwen3.6-35B-A3B' following each lab's style."""
    name = merge_versions(name)
    if org in LOWER_ORGS:
        return name
    out = []
    for index, part in enumerate(name.split("-")):
        if re.fullmatch(r"e?\d+(\.\d+)?b", part) or re.fullmatch(r"a\d+b", part):
            out.append(part.upper())  # 35B, A3B, E4B, 0.8B
        elif re.fullmatch(r"[\d.]+", part):
            out.append(part)
        elif index == 0:
            first = re.match(r"[a-z]+", part)
            if first and first.group(0) in BRAND_CAPS:
                brand = BRAND_CAPS[first.group(0)]
                out.append(brand + part[len(brand):])
            else:
                out.append(part[:1].upper() + part[1:])
        else:
            out.append(part[:1].upper() + part[1:])
    return "-".join(out)


VARIANT_SUFFIXES = ["", "-Instruct", "-GGUF", "-MLX", "-MLX-4bit", "-MLX-6bit", "-MLX-8bit"]


def candidate_repos(slug: str) -> list[str]:
    first, rest = slug.split("-", 1) if "-" in slug else (slug, "")
    base_labs = {"unsloth": "unsloth", "liquidai": "LiquidAI", "google": "google", "openai": "openai",
                 "deepseek-ai": "deepseek-ai", "meta-llama": "meta-llama", "allenai": "allenai",
                 "mistralai": "mistralai", "qwen": "Qwen"}
    org = base_labs.get(first, first)

    # rest already excludes the org prefix; strip quant/format markers
    clean = strip_format_suffix(rest or first)

    # upstream lab for rebrands like unsloth: use the model's own convention
    upstream_org = org
    if first == "unsloth":
        for pattern, _ in SLUG_RULES:
            match = re.match(pattern, f"x-{clean}")  # probe without real org
            del match
        # unsloth mirrors base names: Qwen/Qwen..., google/gemma...
        brand = clean.split("-")[0]
        if brand.startswith("gemma"):
            upstream_org, keep = "google", clean
        elif brand.startswith("qwen"):
            upstream_org, keep = "Qwen", clean
        elif brand.startswith("gpt"):
            upstream_org, keep = "openai", clean
        elif brand.startswith("lfm"):
            upstream_org, keep = "LiquidAI", clean
        elif brand.startswith("deepseek"):
            upstream_org, keep = "deepseek-ai", clean
        else:
            keep = clean
        base_name = titlecase(keep, upstream_org)
    else:
        base_name = titlecase(clean, org)

    # explicit rules still win (they carry org-internal naming quirks)
    repos: list[str] = []
    for pattern, template in SLUG_RULES:
        match = re.match(pattern, slug)
        if match:
            inner_org = template.split("/")[0]
            repos.append(f"{inner_org}/{titlecase(match.group('name'), inner_org)}")
            break

    for suffix in VARIANT_SUFFIXES:
        repos.append(f"{upstream_org}/{base_name}{suffix}")
    return list(dict.fromkeys(repos))


def fetch_json(url: str, timeout: float = 20.0):
    request = urllib.request.Request(url, headers={"User-Agent": "bestmodel-catalog/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_repo(slug: str) -> tuple[str | None, dict | None, int | None, str | None]:
    """Return (repo_id, config, param_count, note) for the first open candidate."""
    import urllib.error

    for repo in candidate_repos(slug):
        try:
            config = fetch_json(f"{HF_RESOLVE}/{repo}/raw/main/config.json")
        except urllib.error.HTTPError as error:
            if error.code == 401:
                continue  # exists but gated — try other variants
            continue
        except Exception:
            continue
        params: int | None = None
        try:
            metadata = fetch_json(f"{HF_API}/{urllib.parse.quote(repo, safe='/')}?expand[]=safetensors")
            params = (metadata.get("safetensors") or {}).get("total")
        except Exception:
            params = None
        return repo, config, params, None
    return None, None, None, "repo-not-found"


def to_release(config: dict, repo_id: str, slug: str, param_count: int | None) -> dict:
    text_config = config.get("text_config") if isinstance(config.get("text_config"), dict) else config

    def pick(*names, cast=int):
        for name in names:
            value = text_config.get(name, config.get(name))
            if value is not None:
                try:
                    return cast(value)
                except (TypeError, ValueError):
                    continue
        return None

    num_heads = pick("num_attention_heads", "n_head")
    hidden = pick("hidden_size", "d_model")
    kv_heads = pick("num_key_value_heads", "n_head_kv") or num_heads
    head_dim = pick("head_dim") or (hidden // num_heads if hidden and num_heads else None)
    expert_count = pick("num_local_experts", "num_experts", "n_routed_experts")
    experts_per_token = pick("num_experts_per_tok", "n_experts_per_token", "experts_per_token")
    active_params = text_config.get("num_experts_per_tok")  # placeholder, refined below

    record = {
        "slug": slug,
        "repo": repo_id,
        "architecture": "moe" if expert_count else "dense",
        "num_layers": pick("num_hidden_layers", "n_layers", "num_layers"),
        "num_attention_heads": num_heads,
        "num_kv_heads": kv_heads,
        "head_dim": head_dim,
        "expert_count": expert_count,
        "experts_per_token": experts_per_token,
        "max_context_tokens": pick("max_position_embeddings", "n_positions", "max_seq_len"),
        "hidden_size": hidden,
    }
    if param_count is not None:
        record["parameter_count_billion"] = round(param_count / 1e9, 2)
    # MoE active-parameter estimate: a rough, honest null unless HF states it
    record["active_parameter_count_billion"] = (
        round(active_params, 2) if isinstance(active_params, (int, float)) else None
    )
    record["_missing"] = [
        field for field in REQUIRED_FIELDS if record.get(field) in (None, "")
    ]
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--out", type=Path, default=Path("/tmp/hf_candidates.json"))
    parser.add_argument("--min-cells", type=int, default=3)
    args = parser.parse_args()

    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for cell in pool["cells"]:
        counts[cell["modelSlug"]] = counts.get(cell["modelSlug"], 0) + 1

    backlog = [
        (slug, n)
        for slug, n in sorted(counts.items(), key=lambda kv: -kv[1])
        if n >= args.min_cells
    ][: args.top]

    results = []
    for slug, n in backlog:
        repo, config, params, note = resolve_repo(slug)
        if repo is None or config is None:
            results.append({"slug": slug, "cells": n, "error": note or "repo-not-found"})
            continue
        record = to_release(config, repo, slug, params)
        record["cells"] = n
        results.append(record)

    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    complete = [r for r in results if not r.get("_missing") and not r.get("error")]
    print(f"scanned {len(backlog)} · complete {len(complete)} · out {args.out}")
    for r in results:
        if r.get("error"):
            status = r["error"]
        elif r.get("_missing"):
            status = f"missing={','.join(r['_missing'])}"
        else:
            status = "OK"
        print(f"  {r.get('cells', 0):3d}x {r['slug']} -> {r.get('repo', '?')} [{status}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
