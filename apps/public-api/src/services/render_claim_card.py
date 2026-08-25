"""Share-card rendering for run claims (S18).

Two deterministic formats, zero dependencies:

- SVG card sized for social embeds (1200x630); every user-controlled string is
  XML-escaped so a crafted handle cannot inject markup.
- Markdown snippet sized for forum posts and GitHub issues.

The number-honesty ladder drives the "prior" line: measured > reported >
extrapolated > formula > no data yet.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

CARD_WIDTH = 1200
CARD_HEIGHT = 630


def render_claim_card_svg(view: dict) -> str:
    handle = _escape(str(view.get("handle") or "anonymous"))
    model = _escape(str(view.get("model_release_id") or "-"))
    status = _escape(str(view.get("status") or "open").replace("_", " "))
    decode = view.get("claimed_metrics", {}).get("decode_tok_s")
    claimed_line = f"{_fmt(decode)} tok/s claimed" if decode else "no metric claimed"

    prior_label, prior_value = _prior_line(view)
    tally = view.get("tally") or {}
    votes_line = (
        f"community: {tally.get('plausible_count', 0)} up / "
        f"{tally.get('impossible_count', 0)} down · margin {_fmt(tally.get('margin', 0))}"
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" role="img" aria-label="bestmodel claim card">
  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" fill="#0b0f14"/>
  <rect x="24" y="24" width="{CARD_WIDTH - 48}" height="{CARD_HEIGHT - 48}" fill="#101820" stroke="#1f2d3d" stroke-width="2"/>
  <text x="72" y="112" font-family="monospace" font-size="30" fill="#5fd3a8">bestmodel.run</text>
  <text x="72" y="188" font-family="monospace" font-size="52" fill="#e6edf3">@{handle} claims</text>
  <text x="72" y="272" font-family="monospace" font-size="76" font-weight="bold" fill="#79c0ff">{_escape(claimed_line)}</text>
  <text x="72" y="340" font-family="monospace" font-size="34" fill="#8b949e">model: {model}</text>
  <text x="72" y="404" font-family="monospace" font-size="30" fill="{_prior_color(prior_label)}">{_escape(prior_label)}: {_escape(prior_value)}</text>
  <text x="72" y="468" font-family="monospace" font-size="30" fill="#8b949e">{_escape(votes_line)}</text>
  <text x="72" y="552" font-family="monospace" font-size="26" fill="#f0883e">status: {status} · prove it or doubt it</text>
</svg>
'''


def render_claim_card_markdown(view: dict) -> str:
    handle = str(view.get("handle") or "anonymous")
    model = str(view.get("model_release_id") or "-")
    decode = view.get("claimed_metrics", {}).get("decode_tok_s")
    claimed = f"**{_fmt(decode)} tok/s**" if decode else "**no metric claimed**"
    prior_label, prior_value = _prior_line(view)
    tally = view.get("tally") or {}

    return (
        f"@{handle} claims {claimed} on `{model}`\n"
        f"- engine prior ({prior_label}): {prior_value}\n"
        f"- community: {tally.get('plausible_count', 0)} plausible / "
        f"{tally.get('impossible_count', 0)} impossible\n"
        f"- prove or dispute it: https://bestmodel.run/claims/{view.get('id', '')}"
    )


def _prior_line(view: dict) -> tuple[str, str]:
    """Return the strongest honest prior available, per the honesty ladder."""
    prior = view.get("prior_snapshot") or {}
    pool = prior.get("pool")
    if pool and pool.get("p50_decode_tok_s"):
        return "measured", f"{pool['p50_decode_tok_s']:_f} tok/s median over {pool['run_count']} runs".replace("_f", "")
    roofline = prior.get("roofline")
    if roofline:
        low, high = roofline.get("plausible_range", [None, None])
        return "formula", f"engine expects {_fmt(low)}–{_fmt(high)} tok/s"
    return "no data yet", "be the first to measure this setup"


def _prior_color(label: str) -> str:
    return {"measured": "#5fd3a8", "formula": "#d2a8ff"}.get(label, "#8b949e")


def _fmt(value) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value) if value is not None else "-"


def _escape(text: str) -> str:
    return escape(text, {'"': "&quot;", "'": "&apos;"})
