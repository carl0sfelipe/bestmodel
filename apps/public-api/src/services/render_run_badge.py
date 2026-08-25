"""Embeddable verified-run badge (C5, S20).

Shields-style two-tone SVG: "<model> · N tok/s — measured on <GPU>".
Deterministic output; all catalog strings are XML-escaped.
"""

from __future__ import annotations

from xml.sax.saxutils import escape


def render_run_badge(context: dict) -> str:
    model = _escape(str(context.get("model_release_id") or "model"))
    gpu = _escape(str(context.get("gpu_marketing_name") or "unknown gpu"))
    decode = context.get("decode_tok_s")
    value = f"{float(decode):.1f} tok/s" if decode is not None else "measured"

    label_width = 90 + 7 * len(model)
    value_width = 60 + 7 * len(f"{value} on {gpu}")
    width = label_width + value_width

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" '
        f'role="img" aria-label="{model}: {value} measured on {gpu}">\n'
        f'  <title>{model}: {value} measured on {gpu}</title>\n'
        f'  <linearGradient id="s" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/></linearGradient>\n'
        f'  <clipPath id="r"><rect width="{width}" height="28" rx="4"/></clipPath>\n'
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{label_width}" height="28" fill="#1f2d3d"/>\n'
        f'    <rect x="{label_width}" width="{value_width}" height="28" fill="#1b4721"/>\n'
        f'    <rect width="{width}" height="28" fill="url(#s)"/>\n'
        f'  </g>\n'
        f'  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="12">\n'
        f'    <text x="{label_width // 2}" y="18">{model}</text>\n'
        f'    <text x="{label_width + value_width // 2}" y="18">{value} on {gpu}</text>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def _escape(text: str) -> str:
    return escape(text, {'"': "&quot;", "'": "&apos;"})
