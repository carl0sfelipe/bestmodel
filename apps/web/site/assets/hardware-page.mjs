// S5 — hardware-first journey (site/hardware.html) page logic.
// All data comes from data/derived/* via loadDerived(); every displayed
// number carries a basis (CONTRATO §1). The engine does fit/speed; this
// module only wires DOM + the real pool.
import { el, fmt, basisBadge, fitLabel, attributionFooter } from "./ui.mjs";
import { loadDerived } from "./load-data.mjs";
import { usableMemGb, fitClass, estimateTokS, vramNeededGb } from "./engine.mjs";

// This journey fixes 4-bit quantization (spec S5 — no quant switcher here).
const BITS = 4;

// Pillar config. Only chat and code have real community data (CONTRATO §4);
// the rest stay disabled until the pool covers them (§7.6).
const PILLARS = [
  { id: "chat", name: "Chat", icon: "▭", desc: "text generation · chat · reasoning", enabled: true },
  { id: "code", name: "Code", icon: "<", desc: "code completion · reasoning", enabled: true },
  { id: "image", name: "Image gen", icon: "▦", desc: "text → image · diffusion", enabled: false },
  { id: "audio", name: "Audio", icon: "∿", desc: "speech-to-text · text-to-speech", enabled: false },
  { id: "video", name: "Video", icon: "▶", desc: "video generation · animation", enabled: false },
  { id: "vision", name: "Vision", icon: "◉", desc: "image understanding · VLMs", enabled: false },
];

// Sample prose for the test-drive preview (kept verbatim from the prototype).
const SAMPLE_TEXT = `The morning light settled across the workshop like a thin sheet of tin. She wiped the lens with the hem of her shirt, then aimed it at the engine block. "Tell me what this is," she said. The model hesitated, then began: a V-twin, cast iron, the kind that outlives the people who bolt it in. Each sentence arrived at a steady cadence — fast enough that the cursor barely flickered, slow enough to feel human.`;

const state = {
  rigKey: null,      // selected rig key from stats.topRigs
  category: "chat",  // current pillar
  sort: "speed",     // catalog sort
  selected: null,    // DerivedModel in the test drive
  saved: false,
};

let RIGS = [];
let MODELS = [];
let CELLS = [];
let STATS = null;
let TOP = [];
const rigByKey = new Map();
const modelsBySlug = new Map();

const currentRig = () => (state.rigKey ? rigByKey.get(state.rigKey) : null);

function paramsLabel(model) {
  return model.paramsB != null ? `${model.paramsB}B` : "?";
}

function hwClassLabel(rig) {
  const cls = { DISCRETE_GPU: "discrete GPU", UNIFIED: "unified memory", CPU_ONLY: "CPU only" }[rig.hwClass] ?? rig.hwClass;
  return rig.gpuCount > 1 ? `${cls} · ${rig.gpuCount}×` : cls;
}

function fmtBw(bw) {
  if (bw == null) return "unknown";
  return bw >= 1000 ? `${fmt(bw / 1000, 1)} TB/s` : `${fmt(bw)} GB/s`;
}

/* ---------------- SCENE 01 — DETECT ---------------- */

function fillRigSelect() {
  const sel = document.getElementById("rigSelect");
  sel.innerHTML = '<option value="">— pick a reference rig —</option>' + TOP
    .map((tr) => `<option value="${tr.key}">${tr.label} · ${fmt(tr.runCount)} runs</option>`)
    .join("");
}

function guessRigByVendor(vendor) {
  const v = String(vendor || "").toLowerCase();
  const tags = [];
  if (/nvidia|0x10de/.test(v)) tags.push("nvidia", "rtx");
  else if (/amd|0x1002/.test(v)) tags.push("amd", "radeon", "rx", "ryzen");
  else if (/intel|0x8086/.test(v)) tags.push("intel", "arc");
  else if (/apple|unified/.test(v)) tags.push("unified");
  if (!tags.length) return null;
  let best = null;
  let bestScore = 0;
  for (const tr of TOP) {
    const rig = rigByKey.get(tr.key);
    if (!rig) continue;
    const label = tr.label.toLowerCase();
    let score = tags.reduce((acc, t) => acc + (label.includes(t) ? 1 : 0), 0);
    if (tags.includes("unified") && rig.hwClass === "UNIFIED") score += 2;
    if (score > bestScore) { bestScore = score; best = tr; }
  }
  return bestScore > 0 ? best : null;
}

async function detect() {
  const btn = document.getElementById("detectBtn");
  btn.innerHTML = `<div class="icon">…</div><div class="txt"><div class="lbl">Detecting…</div><div class="dsc">probing WebGPU — nothing leaves your browser</div></div>`;
  let guess = null;
  let vendor = "";
  try {
    const gpu = navigator.gpu;
    if (gpu && gpu.requestAdapter) {
      const adapter = await gpu.requestAdapter();
      const info = adapter?.info ?? (adapter ? await adapter.requestAdapterInfo() : null);
      vendor = String(info?.vendor ?? "");
      guess = guessRigByVendor(vendor);
    }
  } catch {
    guess = null;
  }
  if (guess) {
    document.getElementById("rigSelect").value = guess.key;
    setRig(guess.key, "best guess — confirm below");
    btn.innerHTML = `<div class="icon">✓</div><div class="txt"><div class="lbl">Best guess — confirm below</div><div class="dsc">${guess.label} · closest match to your GPU</div></div>`;
    toast(`Best guess: ${guess.label} — confirm below`);
  } else {
    btn.innerHTML = `<div class="icon">?</div><div class="txt"><div class="lbl">No WebGPU detection here</div><div class="dsc">pick a reference rig below</div></div>`;
    document.getElementById("rigSelect").scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

/* ---------------- RENDER ENTRY ---------------- */

function setRig(key, source) {
  state.rigKey = key;
  document.getElementById("specTag").textContent = source;
  renderSpecCard();
  renderPillars();
  renderCatalog();
  renderCoorte();
  renderRail();
  autoSelectTestModel();
  document.getElementById("rail").classList.add("on");
}

/* ---------------- SCENE 02 — ENVELOPE ---------------- */

function renderSpecCard() {
  const rig = currentRig();
  if (!rig) return;
  const topObjs = TOP.map((tr) => rigByKey.get(tr.key)).filter(Boolean);
  const maxMem = Math.max(1, ...topObjs.map((r) => r.memGb ?? 0));
  const maxBw = Math.max(1, ...topObjs.map((r) => r.bandwidthGBs ?? 0));

  document.getElementById("specName").textContent = rig.label;
  document.getElementById("specGpu").textContent = rig.label;
  document.getElementById("specVram").textContent = `${rig.memGb} GB`;
  document.getElementById("specBw").textContent = fmtBw(rig.bandwidthGBs);
  document.getElementById("specClass").textContent = hwClassLabel(rig);

  document.getElementById("specVramNum").textContent = `${rig.memGb} GB`;
  document.getElementById("specBwNum").textContent = fmtBw(rig.bandwidthGBs);

  setTimeout(() => {
    const memPct = Math.min(100, ((rig.memGb ?? 0) / maxMem) * 100);
    const bwPct = Math.min(100, ((rig.bandwidthGBs ?? 0) / maxBw) * 100);
    document.getElementById("specGpuBar").style.width = `${memPct}%`;
    document.getElementById("specVramBar").style.width = `${memPct}%`;
    document.getElementById("specBwBar").style.width = `${bwPct}%`;
  }, 100);
}

/* ---------------- SCENE 03 — PILLARS ---------------- */

function categoryCount(catId) {
  const rig = currentRig();
  if (!rig) return null;
  return MODELS.filter((m) => {
    if (m.category !== catId) return false;
    const fit = fitClass(rig, m, BITS);
    return fit === "ok" || fit === "head";
  }).length;
}

function renderPillars() {
  const container = document.getElementById("pillars");
  container.innerHTML = "";
  for (const cat of PILLARS) {
    const count = cat.enabled ? categoryCount(cat.id) : null;
    const attrs = { class: "pillar" + (cat.id === state.category ? " on" : "") + (cat.enabled ? "" : " disabled"), "data-pillar": cat.id };
    if (!cat.enabled) attrs["aria-disabled"] = "true";
    const card = el("div", attrs, [
      el("div", { class: "icon" }, cat.icon),
      el("div", { class: "name" }, cat.name),
      cat.enabled
        ? el("div", { class: "count" }, [
            el("b", null, count == null ? "—" : String(count)),
            count == null ? "" : (count === 1 ? " model fits" : " models fit"),
          ])
        : el("div", { class: "count nodata" }, "no community data yet"),
    ]);
    if (cat.enabled) {
      card.addEventListener("click", () => {
        state.category = cat.id;
        renderPillars();
        renderCatalog();
        autoSelectTestModel();
        renderRail();
      });
    }
    container.appendChild(card);
  }
}

/* ---------------- SCENE 04 — CATALOG ---------------- */

function buildCards() {
  const rig = currentRig();
  if (!rig) return [];
  return MODELS
    .filter((m) => m.category === state.category)
    .map((m) => {
      const fit = fitClass(rig, m, BITS);
      if (fit !== "ok" && fit !== "head") return null;
      const est = estimateTokS(rig, m, BITS, CELLS, RIGS);
      const need = vramNeededGb(m, BITS);
      const usable = usableMemGb(rig);
      const headroom = need && usable ? (usable - need.gb) / usable : null;
      return { m, fit, est, need, headroom };
    })
    .filter(Boolean);
}

const FIT_VAL_CLASS = { "fit-no": "bad", "fit-tight": "tight", "fit-ok": "good", "fit-head": "good" };

function statEl(label, val, cls) {
  return el("div", { class: "stat" }, [
    el("div", { class: "lbl" }, label),
    el("div", { class: "val " + (cls ?? "") }, val),
  ]);
}

function cardNode({ m, est, need }) {
  const fitLbl = fitLabel(fitClass(currentRig(), m, BITS));
  const runsTxt = est ? ` · ${est.n} ${est.n === 1 ? "run" : "runs"}` : " · no data yet";
  return el("div", { class: "model-card", "data-slug": m.slug }, [
    el("div", { class: "top" }, [
      el("div", { class: "name" }, m.displayName),
      el("div", { class: "params" }, paramsLabel(m)),
    ]),
    el("div", { class: "meta" }, [`4-bit · ${m.category}${runsTxt}`]),
    el("div", { class: "stats" }, [
      el("div", { class: "stat" }, [
        el("div", { class: "lbl" }, "Speed"),
        el("div", { class: "val " + (est ? "good" : "") }, est ? `${fmt(est.value)} tok/s` : "—"),
        basisBadge(est?.basis),
      ]),
      statEl("VRAM", need ? `${fmt(need.gb)} GB` : "—"),
      statEl("Fit", fitLbl.text, FIT_VAL_CLASS[fitLbl.cssClass] ?? ""),
    ]),
    el("div", { class: "run" }, "Test drive →"),
  ]);
}

function sortCards(cards) {
  const bySort = {
    speed: (a, b) => (b.est?.value ?? -1) - (a.est?.value ?? -1) || (b.m.paramsB ?? -1) - (a.m.paramsB ?? -1) || a.m.slug.localeCompare(b.m.slug),
    capable: (a, b) => (b.m.paramsB ?? -1) - (a.m.paramsB ?? -1) || (b.est?.value ?? -1) - (a.est?.value ?? -1) || a.m.slug.localeCompare(b.m.slug),
    quality: (a, b) => (b.headroom ?? -1) - (a.headroom ?? -1) || (b.est?.value ?? -1) - (a.est?.value ?? -1) || a.m.slug.localeCompare(b.m.slug),
  };
  cards.sort((x, y) => {
    const dx = x.est ? 0 : 1;
    const dy = y.est ? 0 : 1;
    if (dx !== dy) return dx - dy; // models without an estimate stay at the end
    return bySort[state.sort](x, y);
  });
}

function renderCatalog() {
  const rig = currentRig();
  const grid = document.getElementById("catalogGrid");
  if (!rig) {
    grid.innerHTML = `<div style="grid-column:1/-1;padding:60px 20px;text-align:center;color:var(--muted);font-family:var(--mono);font-size:13px">Pick a reference rig above to see what fits.</div>`;
    return;
  }
  const cat = PILLARS.find((p) => p.id === state.category);
  document.getElementById("catName").textContent = cat.name;
  const cards = buildCards();
  sortCards(cards);
  if (!cards.length) {
    grid.innerHTML = `<div style="grid-column:1/-1;padding:60px 20px;text-align:center;color:var(--muted);font-family:var(--mono);font-size:13px">No ${cat.name.toLowerCase()} models fit your rig at 4-bit yet.<br><span style="color:var(--dim);font-size:11px;margin-top:8px;display:inline-block">The pool only covers text inference today.</span></div>`;
    return;
  }
  grid.innerHTML = "";
  for (const c of cards) grid.appendChild(cardNode(c));
  grid.querySelectorAll(".model-card").forEach((card) => {
    card.addEventListener("click", () => {
      const m = modelsBySlug.get(card.dataset.slug);
      if (m) selectModel(m);
    });
  });
}

function autoSelectTestModel() {
  const cards = buildCards();
  sortCards(cards);
  if (cards.length) {
    state.selected = cards[0].m;
    renderTestDrive();
  }
}

/* ---------------- SCENE 05 — TEST DRIVE ---------------- */

function subCopy(est) {
  if (!est) return "No community speed data for this exact rig + quant yet — fit is estimated from VRAM.";
  if (est.basis === "measured" || est.basis === "reported") {
    return `Based on ${est.n} community ${est.n === 1 ? "run" : "runs"} on this exact rig. Real speed may vary with drivers, power state, and concurrent workloads.`;
  }
  return `Extrapolated from ${est.n} community ${est.n === 1 ? "run" : "runs"} on a similar rig, scaled by memory bandwidth. Real speed may vary.`;
}

let tdTimer = null;

function renderTestDrive() {
  const rig = currentRig();
  const m = state.selected;
  if (!rig || !m) return;
  const est = estimateTokS(rig, m, BITS, CELLS, RIGS);
  const need = vramNeededGb(m, BITS);
  const usable = usableMemGb(rig);

  document.getElementById("tdName").textContent = m.displayName;
  document.getElementById("tdMeta").textContent = `${paramsLabel(m)} · 4-bit · ${m.category}`;
  document.getElementById("tdUnit").textContent = "tokens / sec";
  document.getElementById("tdSub").textContent = subCopy(est);

  const pct = need && usable ? (need.gb / usable) * 100 : 0;
  const fill = document.getElementById("tdVramFill");
  fill.style.width = `${pct}%`;
  fill.classList.toggle("warn", pct > 80);
  document.getElementById("tdVramLbl").textContent = `${need ? fmt(need.gb) : "—"} / ${fmt(usable)} GB`;

  const speedEl = document.getElementById("tdSpeed");
  if (!est) {
    speedEl.textContent = "—";
  } else {
    let current = 0;
    const target = est.value;
    const start = performance.now();
    const duration = 1200;
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      current = target * (1 - Math.pow(1 - t, 3));
      speedEl.textContent = current.toFixed(1);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  renderTdPreview(m, est);
}

function renderTdPreview(m, est) {
  if (tdTimer) { clearInterval(tdTimer); tdTimer = null; }
  const text = document.getElementById("tdPrevText");
  const canvas = document.getElementById("tdPrevCanvas");
  document.getElementById("tdPrevMode").textContent = "text → text";
  canvas.style.display = "none";
  text.style.display = "block";
  if (!est) {
    text.innerHTML = escapeHtml(SAMPLE_TEXT) + '<span class="cur"></span>';
    return;
  }
  let pos = 0;
  text.innerHTML = '<span class="cur"></span>';
  const speed = Math.max(3, Math.floor(est.value * 0.4));
  tdTimer = setInterval(() => {
    pos += speed;
    if (pos > SAMPLE_TEXT.length) pos = SAMPLE_TEXT.length;
    text.innerHTML = escapeHtml(SAMPLE_TEXT.slice(0, pos)) + '<span class="cur"></span>';
    if (pos >= SAMPLE_TEXT.length) clearInterval(tdTimer);
  }, 60);
}

function escapeHtml(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

/* ---------------- SCENE 06 — COHORT ---------------- */

function renderCoorte() {
  const rig = currentRig();
  const list = document.getElementById("topList");
  const row = document.getElementById("statRow");
  list.innerHTML = "";
  row.innerHTML = "";
  if (!rig) return;

  const rigCells = CELLS.filter((c) => c.rigKey === rig.key);
  const byModel = new Map();
  for (const c of rigCells) {
    let agg = byModel.get(c.modelSlug);
    if (!agg) { agg = { slug: c.modelSlug, n: 0, rep: null }; byModel.set(c.modelSlug, agg); }
    agg.n += c.n;
    if (!agg.rep || c.n > agg.rep.n) agg.rep = c;
  }

  const top5 = [...byModel.values()].sort((a, b) => b.n - a.n || a.slug.localeCompare(b.slug)).slice(0, 5);
  for (const agg of top5) {
    const model = modelsBySlug.get(agg.slug);
    list.appendChild(el("li", null, [
      el("span", { class: "rank" }, String(top5.indexOf(agg) + 1).padStart(2, "0")),
      el("span", { class: "name" }, model?.displayName ?? agg.slug),
      el("span", { class: "meta" }, `${fmt(agg.rep.tokSOutMedian)} tok/s`),
      el("span", { class: "ppl" }, `${agg.n} ${agg.n === 1 ? "run" : "runs"}`),
    ]));
  }
  if (!top5.length) {
    list.appendChild(el("li", null, [el("span", { class: "meta" }, "no runs on this rig yet")]));
  }

  const totalRuns = rigCells.reduce((a, c) => a + c.n, 0);
  const engines = [...new Set(rigCells.flatMap((c) => c.engines))];
  const bits = new Map();
  rigCells.forEach((c) => bits.set(c.bits, (bits.get(c.bits) || 0) + c.n));
  const topBits = [...bits.entries()].sort((a, b) => b[1] - a[1])[0];

  row.appendChild(statBoxEl("community runs", fmt(totalRuns), "single-stream runs on this exact rig"));
  row.appendChild(statBoxEl("engines tested", String(engines.length), engines.join(", ") || "—"));
  row.appendChild(statBoxEl("most common quant", topBits ? `${topBits[0]}-bit` : "—", "by run count on this rig"));
}

function statBoxEl(title, value, sub) {
  return el("div", { class: "stat-box" }, [
    el("div", { class: "t" }, title),
    el("div", { class: "n" }, value),
    el("div", { class: "s" }, sub),
  ]);
}

/* ---------------- RAIL / WIRE-UP / BOOT ---------------- */

function renderRail() {
  const rail = document.getElementById("rail");
  rail.innerHTML = "";
  if (!state.rigKey) { rail.classList.remove("on"); return; }
  const rig = currentRig();
  const cat = PILLARS.find((p) => p.id === state.category);
  const chips = [
    { k: "machine", label: rig.label, target: "s02" },
    { k: "category", label: cat.name, target: "s03" },
  ];
  if (state.selected) chips.push({ k: "model", label: state.selected.displayName, target: "s05" });
  for (const c of chips) {
    const chip = el("button", { class: "chip", "data-k": c.k }, [el("span", { class: "dot" }), c.label]);
    chip.addEventListener("click", () => scrollTo(c.target));
    rail.appendChild(chip);
  }
  rail.classList.add("on");
}

function toast(msg) {
  const t = document.getElementById("toast");
  document.getElementById("toastMsg").textContent = msg;
  t.classList.add("on");
  setTimeout(() => t.classList.remove("on"), 2200);
}

function scrollTo(id) {
  document.getElementById(id).scrollIntoView({ behavior: "smooth", block: "start" });
}

function restoreSavedRig() {
  try {
    const saved = localStorage.getItem("cir.rig");
    if (saved && rigByKey.has(saved)) {
      state.saved = true;
      document.getElementById("rigSelect").value = saved;
      document.getElementById("saveLbl").textContent = "Saved ✓";
      document.getElementById("saveBtn").classList.add("done");
      setRig(saved, "saved");
    }
  } catch {}
}

function wireButtons() {
  document.getElementById("detectBtn").addEventListener("click", detect);
  document.getElementById("rigSelect").addEventListener("change", (e) => {
    if (e.target.value) setRig(e.target.value, "selected");
  });

  document.getElementById("saveBtn").addEventListener("click", () => {
    if (!state.rigKey) { toast("Pick a rig first"); return; }
    state.saved = !state.saved;
    document.getElementById("saveBtn").classList.toggle("done", state.saved);
    document.getElementById("saveLbl").textContent = state.saved ? "Saved ✓" : "Save this rig";
    try {
      if (state.saved) localStorage.setItem("cir.rig", state.rigKey);
      else localStorage.removeItem("cir.rig");
    } catch {}
    toast(state.saved ? "Rig saved · you'll see it next visit" : "Rig unsaved");
  });

  document.getElementById("catControls").addEventListener("click", (e) => {
    const btn = e.target.closest(".cat-btn");
    if (!btn) return;
    document.querySelectorAll("#catControls .cat-btn").forEach((x) => x.classList.remove("on"));
    btn.classList.add("on");
    state.sort = btn.dataset.sort;
    renderCatalog();
  });

  document.getElementById("runBtn").addEventListener("click", () => {
    toast("Run tooling ships with the CLI phase — the speed above is the real pool median for this rig.");
  });

  document.getElementById("copyCmdBtn").addEventListener("click", async () => {
    const m = state.selected;
    if (!m) return;
    try {
      await navigator.clipboard.writeText(m.hfId);
      toast(`Copied ${m.hfId}`);
    } catch {
      toast("Copy failed");
    }
  });

  document.querySelectorAll(".journey-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.journey === "goal") {
        toast("The goal-first journey ships in the next session.");
      }
    });
  });
}

function renderFooter() {
  const foot = document.getElementById("footer");
  foot.replaceWith(attributionFooter(STATS));
}

/* ---- scroll engine + ambient background (ported from prototype) ---- */

const scenes = Array.from(document.querySelectorAll(".scene"));
const sceneState = scenes.map((sEl) => ({ el: sEl, progress: 0 }));

function calcProgress() {
  const vh = window.innerHeight;
  sceneState.forEach((s) => {
    const r = s.el.getBoundingClientRect();
    const track = s.el.offsetHeight;
    const scrollRange = track - vh;
    if (scrollRange <= 0) s.progress = r.top <= 0 ? 1 : 0;
    else s.progress = Math.max(0, Math.min(1, -r.top / scrollRange));
  });
}
let ticking = false;
function tick() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { calcProgress(); ticking = false; });
}
window.addEventListener("scroll", tick, { passive: true });
window.addEventListener("resize", () => { sizeAmbient(); tick(); });

const nav = document.getElementById("nav");
window.addEventListener("scroll", () => {
  nav.classList.toggle("scrolled", window.scrollY > 30);
}, { passive: true });

const tics = document.querySelectorAll(".tic");
tics.forEach((t) => {
  t.addEventListener("click", () => {
    const target = document.getElementById(t.dataset.target);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

function updateChapter() {
  let activeId = "s01";
  const vh = window.innerHeight;
  for (const s of sceneState) {
    const r = s.el.getBoundingClientRect();
    if (r.top < vh * 0.5 && r.bottom > vh * 0.5) { activeId = s.el.id; break; }
  }
  tics.forEach((t) => t.classList.toggle("active", t.dataset.target === activeId));
}
setInterval(updateChapter, 200);

function updateSceneActivation() {
  sceneState.forEach((s) => {
    if (s.progress > 0.02) s.el.classList.add("on");
  });
}
setInterval(updateSceneActivation, 200);

const bg01 = document.getElementById("bg01");
const ctx01 = bg01.getContext("2d");
const bg02 = document.getElementById("bg02");
const ctx02 = bg02.getContext("2d");

function sizeBg(c, ctx) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  c.width = c.clientWidth * dpr;
  c.height = c.clientHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

let bgT = 0;
function drawBg01() {
  const w = bg01.clientWidth, h = bg01.clientHeight;
  ctx01.clearRect(0, 0, w, h);
  ctx01.globalAlpha = 0.06;
  ctx01.fillStyle = "#EDEEF0";
  for (let y = 20; y < h; y += 28) {
    for (let x = 20; x < w; x += 28) {
      const n = Math.sin(x * 0.008 + y * 0.008 + bgT * 0.3);
      if (n > 0.3) ctx01.fillRect(x, y, 1.5, 1.5);
    }
  }
  ctx01.globalAlpha = 1;
}
function drawBg02() {
  const w = bg02.clientWidth, h = bg02.clientHeight;
  ctx02.clearRect(0, 0, w, h);
  ctx02.globalAlpha = 0.06;
  ctx02.strokeStyle = "#E0A458";
  ctx02.lineWidth = 1;
  const cx = w * 0.5, cy = h * 0.5;
  for (let i = 0; i < 6; i++) {
    const r = 80 + i * 60 + Math.sin(bgT * 0.5 + i) * 8;
    ctx02.beginPath();
    ctx02.arc(cx, cy, r, 0, Math.PI * 2);
    ctx02.stroke();
  }
  ctx02.globalAlpha = 1;
}
/* Reallocating the canvas buffers (sizeBg) every frame pegged the main
   thread — the canvases span whole 140-220vh scenes. Size them only on
   boot/resize; the per-frame loop just draws. */
function sizeAmbient() {
  sizeBg(bg01, ctx01);
  sizeBg(bg02, ctx02);
}
function renderAmbient() {
  drawBg01();
  drawBg02();
  bgT += 0.016;
}
function ambientLoop() {
  renderAmbient();
  requestAnimationFrame(ambientLoop);
}

/* ---------------- BOOT ---------------- */

async function boot() {
  const d = await loadDerived();
  RIGS = d.hardware.rigs;
  MODELS = d.models.models;
  CELLS = d.pool.cells;
  STATS = d.stats;
  TOP = STATS.topRigs;
  for (const r of RIGS) rigByKey.set(r.key, r);
  for (const m of MODELS) modelsBySlug.set(m.slug, m);

  fillRigSelect();
  wireButtons();
  renderPillars();
  renderFooter();
  restoreSavedRig();
  sizeAmbient();
  requestAnimationFrame(ambientLoop);
  calcProgress();
}

boot().catch((err) => console.error("hardware-page:", err));
