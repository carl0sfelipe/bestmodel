// S30 — the wall (leaderboard). Every number is real pool data via
// loadDerived() — no mock (CONTRATO §7.2). Basis follows engine.mjs's
// own rule: n >= MIN_RUNS_MEASURED renders "measured", 1–2 = "reported".
// Report/capture controls deep-link to /console (auth lives there).

import { el, fmt, sourceBadge, basisBadge, attributionFooter } from "./ui.mjs";
import { loadDerived } from "./load-data.mjs";
import { MIN_RUNS_MEASURED } from "./engine.mjs";

const state = { rig: "all", category: "all", sort: "toks" };

function basisOf(cell) {
  return cell.n >= MIN_RUNS_MEASURED ? "measured" : "reported";
}

function topRigs(rigs, cells) {
  const counts = new Map();
  for (const c of cells) counts.set(c.rigKey, (counts.get(c.rigKey) || 0) + (c.n || 1));
  return rigs
    .filter((r) => (counts.get(r.key) || 0) > 0)
    .sort((a, b) => (counts.get(b.key) || 0) - (counts.get(a.key) || 0))
    .slice(0, 24);
}

function render(rowsMeta, mount) {
  mount.innerHTML = "";

  const filters = el("div", { class: "wall-filters" });
  const rigSel = el("select", { class: "wall-sel", "aria-label": "hardware" });
  rigSel.append(el("option", { value: "all" }, "all hardware"));
  for (const r of rowsMeta.rigs) {
    const o = el("option", { value: r.key }, `${r.label} · ${r.runCount} runs`);
    if (state.rig === r.key) o.selected = true;
    rigSel.append(o);
  }
  const catSel = el("select", { class: "wall-sel", "aria-label": "category" });
  catSel.append(el("option", { value: "all" }, "all categories"));
  for (const c of rowsMeta.categories) {
    const o = el("option", { value: c.id }, c.label);
    if (state.category === c.id) o.selected = true;
    catSel.append(o);
  }
  const sortSel = el("select", { class: "wall-sel", "aria-label": "sort" });
  for (const [v, label] of [["toks", "sort: fastest decode"], ["runs", "sort: most runs"], ["recent", "sort: context tested"]]) {
    const o = el("option", { value: v }, label);
    if (state.sort === v) o.selected = true;
    sortSel.append(o);
  }
  rigSel.addEventListener("change", () => { state.rig = rigSel.value; draw(rowsMeta, mount); });
  catSel.addEventListener("change", () => { state.category = catSel.value; draw(rowsMeta, mount); });
  sortSel.addEventListener("change", () => { state.sort = sortSel.value; draw(rowsMeta, mount); });
  filters.append(rigSel, catSel, sortSel);
  mount.append(filters);

  // UX law: hardware, category and sort are separate labelled controls.
  let rows = rowsMeta.rows;
  if (state.rig !== "all") rows = rows.filter((r) => r.rigKey === state.rig);
  if (state.category !== "all") rows = rows.filter((r) => r.category === state.category);
  if (state.sort === "toks") rows.sort((a, b) => b.tokSOut - a.tokSOut);
  if (state.sort === "runs") rows.sort((a, b) => b.n - a.n);
  if (state.sort === "recent") rows.sort((a, b) => (b.maxContext || 0) - (a.maxContext || 0));
  rows = rows.slice(0, 60);

  const measured = rows.filter((r) => r.basis === "measured").length;
  const summary = el("p", { class: "wall-summary" },
    `${rows.length} cells shown · ${measured} measured (≥${MIN_RUNS_MEASURED} runs) · ${rows.length - measured} reported (1–2 runs) · ranking is always provisional: a signed run outranks any claim`);

  const list = el("div", { class: "wall-list" });
  let rank = 0;
  for (const r of rows) {
    rank += 1;
    const head = el("div", { class: "wall-row-head" });
    head.append(
      el("span", { class: "wall-rank" }, `#${rank}`),
      el("strong", { class: "wall-model" }, r.modelLabel),
      sourceBadge(r.sourceClass),
      basisBadge(r.basis),
    );
    const nums = el("div", { class: "wall-num" },
      `${fmt(r.tokSOut)} tok/s`, el("small", null,
        ` decode · ${fmt(r.tokSPrefill)} tok/s prefill · ${r.bits}-bit`));
    const meta = el("div", { class: "wall-meta" },
      `${r.rigLabel} · n=${r.n} · ${r.engine} · ctx ${r.maxContext ? fmt(r.maxContext, 0) : "—"}`);
    const actions = el("div", { class: "wall-actions" });
    actions.append(
      el("a", { class: "wall-link", href: "./console/" }, "capture / correct →"),
    );
    list.append(el("article", { class: "wall-row" }, head, nums, meta, actions));
  }

  mount.append(summary, list);
  mount.append(el("p", { class: "wall-foot" },
    "Rows are community cells (medians), ranked provisionally. A claim you capture today can be settled by a signed run tomorrow — that is the only ranking that matters."));
}

function draw(rowsMeta, mount) {
  render(rowsMeta, mount);
}

export async function mountWall(mount) {
  const { models, hardware, pool, stats } = await loadDerived();
  const bySlug = new Map(models.models.map((m) => [m.slug, m]));
  const byKey = new Map(hardware.hardware.map((h) => [h.key, h]));

  const rows = [];
  const categories = new Map();
  for (const c of pool.cells) {
    const m = bySlug.get(c.modelSlug);
    if (!m) continue;
    const rig = byKey.get(c.rigKey);
    const cat = m.category || "chat";
    categories.set(cat, (categories.get(cat) || 0) + 1);
    rows.push({
      modelLabel: m.displayName || m.slug,
      rigKey: c.rigKey,
      rigLabel: rig ? rig.label : c.rigKey,
      category: cat,
      bits: c.bits,
      tokSOut: c.tokSOutMedian ?? -1,
      tokSPrefill: c.tokSPrefillMedian,
      n: c.n || 1,
      engine: (c.engines || []).join(", ") || "engine unstated",
      maxContext: c.maxContextTested,
      sourceClass: m.sourceClass,
      basis: basisOf(c),
    });
  }

  const rigs = topRigs(hardware.hardware, pool.cells).map((r) => ({
    key: r.key, label: r.label, runCount: r.runCount ?? 0,
  }));
  const cats = [...categories.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id, n]) => ({ id, label: `${id} · ${n} cells` }));

  render({ rows, rigs, categories: cats }, mount);
  mount.append(attributionFooter(stats));
}
