// S4 — shared DOM helpers. Presentation only: no engine import, no fetch.
// Element classes and colors come from site/assets/theme.css + CONTRATO §7.

// CONTRATO §6 — engine.mjs exports the same string; the kit must not
// depend on the engine, so the constant is duplicated here on purpose.
const ATTRIBUTION = "community pool data via localmaxxing.com public API";

const BASIS_TEXT = {
  measured: "measured",
  reported: "reported",
  extrapolated: "~ extrapolated",
};

const FIT_LABELS = {
  no: { text: "won't run", cssClass: "fit-no" },
  tight: { text: "runs, tight", cssClass: "fit-tight" },
  ok: { text: "comfortable", cssClass: "fit-ok" },
  head: { text: "headroom", cssClass: "fit-head" },
};

export function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null) continue;
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else if (key === "hidden") node.hidden = Boolean(value);
    else if (typeof value === "boolean") {
      if (value) node.setAttribute(key, "");
    } else node.setAttribute(key, value);
  }
  for (const child of [].concat(children ?? [])) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function fmt(n, digits = 1) {
  const v = n == null ? NaN : Number(n);
  if (!Number.isFinite(v)) return "-";
  return v.toLocaleString("en-US", { maximumFractionDigits: digits });
}

// S24: source-class badges — the honesty UI. Taxonomy lives in engine.mjs
// (pure, DOM-free, tested there); this is only the rendering.
import { sourceText } from "./engine.mjs";

export function sourceBadge(sourceClass) {
  return el(
    "span",
    { class: "source-badge", "data-source": sourceClass ?? "unknown" },
    sourceText(sourceClass)
  );
}

export function sourceLegend() {
  return el(
    "div",
    { class: "source-legend" },
    "data sources: community-reported (harvested pool) · measured · signed (bestmodel signed runs) · mock (fixtures)"
  );
}

export function basisBadge(basis) {
  const key = basis ?? "none";
  return el("span", { class: "basis-badge", "data-basis": key }, BASIS_TEXT[basis] ?? "no data yet");
}

export function fitLabel(fitClass) {
  return FIT_LABELS[fitClass] ?? { text: "no data yet", cssClass: "fit-none" };
}

export function copyButton(text) {
  // CONTRATO §7.3: the `curl -sSf canirun.it/sh | sh` install block stays
  // hidden until the domain and installer exist ([A DEFINIR]).
  const hidden = /^curl\s+-sSf\s+canirun\.it\//.test(text);
  const cp = el("button", { class: "cp" }, "copy");
  cp.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      cp.textContent = "copied";
      cp.classList.add("done");
      setTimeout(() => { cp.textContent = "copy"; cp.classList.remove("done"); }, 2000);
    } catch {
      cp.textContent = "copy failed";
    }
  });
  return el("div", { class: "install", hidden }, [
    el("span", { class: "prompt" }, "$"),
    el("span", null, text),
    cp,
  ]);
}

export function attributionFooter(stats) {
  const date = stats?.snapshotAt ? String(stats.snapshotAt).slice(0, 10) : "no snapshot date";
  return el("footer", { class: "for-human" }, [
    el("div", null, "can-i-run-it"),
    el("div", null, `${ATTRIBUTION} · snapshot ${date}`),
    sourceLegend(),
  ]);
}
