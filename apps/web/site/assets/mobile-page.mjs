// S7 — mobile-first ad landing (site/m/index.html) page logic.
// Same engine/ui/load-data as the desktop journeys, compressed presentation
// per prototypes/mobile-landing.html. All numbers come from data/derived/*
// via loadDerived(); every speed carries a basis (CONTRATO §1). This module
// only wires DOM + the real pool — no formulas live here.
import { el, fmt, basisBadge, fitLabel, attributionFooter } from "./ui.mjs";
import { loadDerived } from "./load-data.mjs";
import {
  quantBits, usableMemGb, vramNeededGb, fitClass, estimateTokS, topPicks,
} from "./engine.mjs";

// Output options: text/code have real community data (CONTRATO §4); the rest
// stay disabled with the honest tooltip (§7.6).
const OUTPUTS = [
  { id: "text", label: "text", g: "▭", ex: "Chat, reasoning, writing", enabled: true },
  { id: "code", label: "code", g: "<", ex: "Code completion, reasoning", enabled: true },
  { id: "image", label: "image", g: "▦", ex: "Text → image · diffusion", enabled: false },
  { id: "audio", label: "audio", g: "∿", ex: "Speech-to-text · text-to-speech", enabled: false },
  { id: "video", label: "video", g: "▶", ex: "Video generation", enabled: false },
];

// Pillars: chat/code have real data; the rest disabled until the pool covers
// them (CONTRATO §4, §7.6). Same set as the desktop hardware journey.
const PILLARS = [
  { id: "chat", name: "Chat", icon: "▭", desc: "text generation · chat · reasoning", enabled: true },
  { id: "code", name: "Code", icon: "<", desc: "code completion · reasoning", enabled: true },
  { id: "image", name: "Image gen", icon: "▦", desc: "text → image · diffusion", enabled: false },
  { id: "audio", name: "Audio", icon: "∿", desc: "speech-to-text · text-to-speech", enabled: false },
  { id: "video", name: "Video", icon: "▶", desc: "video generation · animation", enabled: false },
  { id: "vision", name: "Vision", icon: "◉", desc: "image understanding · VLMs", enabled: false },
];

// Quant segment labels (CONTRATO §6): FP16/Q8/Q6/Q4 map via engine.quantBits.
const QUANT_SEG = ["FP16", "Q8", "Q6", "Q4"];

// Sample prose for the test-drive preview (kept verbatim from the prototype).
const SAMPLE_TEXT = `The morning light settled across the workshop like a thin sheet of tin. She wiped the lens with the hem of her shirt, then aimed it at the engine block. "Tell me what this is," she said. The model hesitated, then began: a V-twin, cast iron, the kind that outlives the people who bolt it in.`;

const FIT_ORDER = { head: 3, ok: 2, tight: 1 };
const FIT_SHORT = { head: "headroom", ok: "ok", tight: "tight", no: "won't run" };
const FIT_VAL_CLASS = { head: "good", ok: "good", tight: "tight", no: "bad" };
const SOURCE_LABEL = { detected: "auto-detected", guess: "best guess", selected: "selected", saved: "saved" };

const state = {
  journey: "goal",       // "goal" | "hardware"
  input: "text",         // fixed text input (pool is text inference)
  output: "text",        // text | code
  machine: null,         // rig key | null
  machineSource: "auto", // detect/selected source label for the envelope
  category: "chat",      // hardware journey pillar
  quant: 4,              // bits
  selectedModel: null,   // DerivedModel in the test drive
  sort: "speed",         // catalog sort
};

let RIGS = [];
let MODELS = [];
let CELLS = [];
let STATS = null;
let TOP = [];
const rigByKey = new Map();
const modelsBySlug = new Map();

const currentRig = () => (state.machine ? rigByKey.get(state.machine) : null);
const currentCategory = () => (state.journey === "goal" ? (state.output === "code" ? "code" : "chat") : state.category);
const currentBits = () => (state.journey === "hardware" ? 4 : state.quant);
const categoryModels = () => MODELS.filter((m) => m.category === currentCategory());

function hwClassLabel(rig) {
  const cls = { DISCRETE_GPU: "discrete GPU", UNIFIED: "unified memory", CPU_ONLY: "CPU only" }[rig.hwClass] ?? rig.hwClass;
  return rig.gpuCount > 1 ? `${cls} · ${rig.gpuCount}×` : cls;
}

function fmtBw(bw) {
  if (bw == null) return "unknown";
  return bw >= 1000 ? `${fmt(bw / 1000, 1)} TB/s` : `${fmt(bw)} GB/s`;
}

function paramsLabel(model) {
  return model.paramsB != null ? `${model.paramsB}B` : "?";
}

function rigDsc(rig) {
  const parts = [];
  if (rig.memGb != null) parts.push(`${rig.memGb} GB`);
  else parts.push(hwClassLabel(rig));
  if (rig.bandwidthGBs != null) parts.push(fmtBw(rig.bandwidthGBs));
  return parts.join(" · ");
}

function escapeHtml(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
function haptic() { if (navigator.vibrate) navigator.vibrate(8); }

function subCopy(est) {
  if (!est) return "No community speed data for this exact rig + quant yet — fit is estimated from VRAM.";
  if (est.basis === "measured" || est.basis === "reported") {
    return `Based on ${est.n} community ${est.n === 1 ? "run" : "runs"} on this exact rig. Real speed may vary with drivers, power state, and concurrent workloads.`;
  }
  return `Extrapolated from ${est.n} community ${est.n === 1 ? "run" : "runs"} on a similar rig, scaled by memory bandwidth. Real speed may vary.`;
}

function toast(msg) {
  const t = document.getElementById("toast");
  document.getElementById("toastMsg").textContent = msg;
  t.classList.add("on");
  setTimeout(() => t.classList.remove("on"), 2200);
}

/* ---------------- CANDIDATES (engine-backed, no formulas here) ---------------- */

function buildCandidates() {
  const rig = currentRig();
  if (!rig) return [];
  const bits = currentBits();
  const usable = usableMemGb(rig);
  return categoryModels()
    .map((m) => {
      const fit = fitClass(rig, m, bits);
      if (fit == null || fit === "no") return null;
      const est = estimateTokS(rig, m, bits, CELLS, RIGS);
      const need = vramNeededGb(m, bits);
      const headroom = need && usable ? (usable - need.gb) / usable : null;
      return { m, fit, est, need, headroom };
    })
    .filter(Boolean);
}

function sortCandidates(list) {
  list.sort((a, b) => {
    const da = a.est ? 0 : 1, db = b.est ? 0 : 1;
    if (da !== db) return da - db;
    const fa = FIT_ORDER[a.fit] ?? 0, fb = FIT_ORDER[b.fit] ?? 0;
    if (fb !== fa) return fb - fa;
    const sa = a.est?.value ?? -1, sb = b.est?.value ?? -1;
    if (sb !== sa) return sb - sa;
    return a.m.slug.localeCompare(b.m.slug);
  });
}

function tdInfo() {
  const rig = currentRig();
  if (!rig) return null;
  const m = state.selectedModel;
  if (m) {
    const bits = currentBits();
    return { m, bits, fit: fitClass(rig, m, bits), est: estimateTokS(rig, m, bits, CELLS, RIGS) };
  }
  const pick = topPicks(rig, categoryModels(), CELLS, RIGS, 1)[0];
  return pick ? { m: pick.model, bits: pick.bits, fit: pick.fit, est: pick.est } : null;
}

function categoryCount(catId) {
  const rig = currentRig();
  if (!rig) return null;
  const bits = currentBits();
  return MODELS.filter((m) => {
    if (m.category !== catId) return false;
    const fit = fitClass(rig, m, bits);
    return fit === "ok" || fit === "head";
  }).length;
}

/* ---------------- RENDER ---------------- */

function render() {
  const main = document.getElementById("main");
  main.innerHTML = state.journey === "goal" ? renderGoalJourney() : renderHardwareJourney();
  bindEvents();
  updateBottomBar();
  updateFinalCTA();
}

/* ------------------ GOAL JOURNEY ------------------ */

function renderGoalJourney() {
  const rig = currentRig();
  const candidates = rig ? buildCandidates() : [];
  sortCandidates(candidates);
  const best = tdInfo();
  const usable = rig ? usableMemGb(rig) : null;

  return `
    <section class="panel" id="p-hero">
      <div class="trust"><span class="live"></span><span>${fmt(STATS.totals.runs, 0)} verified community speed runs</span></div>

      <h1>What do you want <span class="em">your machine</span> to do?</h1>
      <div class="hero-sub">Every model that fits — scored against your exact hardware.</div>

      <div class="intent-q">
        <div class="lbl">Pick an output</div>
        <div class="intent-grid">
          ${OUTPUTS.map((o) => `
            <button class="intent-chip ${o.id === state.output ? "on" : ""}${o.enabled ? "" : " disabled"}" data-output="${o.id}" ${o.enabled ? "" : 'title="no community data yet"'} ${o.enabled ? "" : "disabled"}>
              <div class="io">${state.input} <span class="arr">→</span> ${o.label}</div>
              <div class="ex">${o.ex}</div>
            </button>
          `).join("")}
        </div>
      </div>

      <button class="machine-mini" id="machinePick">
        <div class="ic">${rig ? "✓" : "⌘"}</div>
        <div class="txt">
          <div class="lbl">${rig ? escapeHtml(rig.label) : "Pick your machine"}</div>
          <div class="dsc">${rig ? rigDsc(rig) : "Auto-detect or choose a rig"}</div>
        </div>
        <div class="chev">›</div>
      </button>
    </section>

    ${rig ? `
    <!-- PANEL 2: UNIVERSE -->
    <section class="panel" id="p-universe">
      <div class="kicker">The universe filtered</div>
      <div class="universe">
        <div class="universe-top">
          <div>
            <div class="t">public models speed-tested</div>
            <div class="big">${fmt(STATS.totals.models, 0)}</div>
          </div>
          <div>
            <div class="t">match your intent</div>
            <div class="big">${fmt(candidates.length, 0)}</div>
          </div>
        </div>
        <div class="universe-desc">
          We scanned the public model index and kept only <b>${candidates.length}</b> that do <b>${state.input} → ${state.output}</b> and fit inside <b>${usable != null ? fmt(usable) : "—"} GB</b> usable memory.
        </div>
        <div class="constellation">
          <canvas id="constellationCanvas"></canvas>
        </div>
      </div>
    </section>

    <!-- PANEL 3: SPECTRUM -->
    <section class="panel" id="p-spectrum">
      <div class="kicker">Compatibility is a spectrum</div>
      <h2>Not just "yes or no" — <span class="em">how well</span> it runs.</h2>
      <div class="sub">Swipe to see every model that fits, scored by how much headroom your machine has.</div>

      <div class="spectrum">
        <div class="spectrum-head">
          <div class="t">${candidates.length} candidates</div>
          <div class="q">
            ${QUANT_SEG.map((q) => `<button class="${quantBits(q) === state.quant ? "on" : ""}" data-quant="${q}">${q}</button>`).join("")}
          </div>
        </div>
        <div class="spectrum-track" id="specTrack">
          ${candidates.length === 0 ? `
            <div class="spec-node" style="flex:0 0 280px">
              <div class="name">No models match</div>
              <div class="stats" style="margin-top:10px">Try a different output or looser quantization.</div>
            </div>
          ` : candidates.slice(0, 20).map((x) => `
            <button class="spec-node" data-model="${x.m.slug}">
              <div class="row">
                <div class="name">${escapeHtml(x.m.displayName)}</div>
                <div class="fit ${x.fit}">${FIT_SHORT[x.fit]}</div>
              </div>
              <div class="stats">
                <div class="s"><b>${x.est ? fmt(x.est.value) : "—"}</b>${x.est ? "t/s" : ""}</div>
                <div class="s"><b>${x.need ? fmt(x.need.gb) : "—"}</b>${x.need ? "GB" : ""}</div>
                <div class="s"><b>${paramsLabel(x.m)}</b></div>
              </div>
            </button>
          `).join("")}
        </div>
      </div>
    </section>

    ${best ? `
    <!-- PANEL 4: TEST DRIVE -->
    <section class="panel" id="p-td">
      <div class="kicker">Test drive</div>
      <h2>See what it <span class="em">actually</span> feels like.</h2>
      <div class="sub" id="tdSub"></div>
      <div class="td-card">
        <div class="td-model">
          <div class="name" id="tdName">—</div>
          <div class="meta" id="tdMeta">—</div>

          <div class="td-vram">
            <div class="bar"><div class="fill" id="tdVramFill" style="width:0%"></div></div>
            <div class="lbl"><span id="tdVramLbl">— / — GB</span><span>weights + KV cache</span></div>
          </div>

          <div class="td-speed">
            <div class="num" id="tdSpeed">—</div>
            <div class="unit">tokens / sec</div>
          </div>
          <div class="td-basis" id="tdBasis"></div>
        </div>

        <div class="preview">
          <div class="preview-head"><span>live preview</span><span>text → text</span></div>
          <div class="preview-body">
            <div class="preview-text" id="prevText"></div>
            <canvas id="prevCanvas"></canvas>
          </div>
        </div>

        <div class="td-cta">
          <button class="btn-secondary" id="copyRunCmd">Copy run command</button>
          <button class="btn-secondary" id="changeModel">Change model</button>
        </div>
      </div>
    </section>

    <!-- PANEL 5: RECOMMENDATIONS -->
    <section class="panel" id="p-recs">
      <div class="kicker">Your top 3</div>
      <h2>Three models <span class="em">you can actually run.</span></h2>
      <div class="rec-stack">
        ${topPicks(rig, categoryModels(), CELLS, RIGS, 3).map((p, i) => recCard(p, i)).join("")}
      </div>
    </section>

    <!-- PANEL 6: COHORT -->
    <section class="panel" id="p-cohort">
      <div class="kicker">Your cohort</div>
      <h2><span class="em">People with ${escapeHtml(rig.label)}</span> are running these.</h2>
      <div class="sub">Verified single-stream runs on this exact rig.</div>
      ${cohortHtml(rig, true, candidates.length)}
    </section>
    ` : ""}
    ` : `
    <!-- PANEL 2 (no machine): prompt -->
    <section class="panel" id="p-prompt">
      <div class="kicker">One more thing</div>
      <h2>Tell us your <span class="em">machine</span>.</h2>
      <div class="sub">We'll instantly show you every ${state.input} → ${state.output} model it can run — with verified speeds.</div>
      <button class="machine-mini" id="machinePick2" style="margin-top:8px">
        <div class="ic">⌘</div>
        <div class="txt">
          <div class="lbl">Pick your machine</div>
          <div class="dsc">Auto-detect or choose a rig</div>
        </div>
        <div class="chev">›</div>
      </button>
    </section>
    `}
  `;
}

/* ------------------ HARDWARE JOURNEY ------------------ */

function renderHardwareJourney() {
  const rig = currentRig();
  const cat = PILLARS.find((p) => p.id === state.category);
  const cards = rig ? buildCandidates() : [];
  sortCatalog(cards);
  const best = tdInfo();
  const totalFit = (categoryCount("chat") ?? 0) + (categoryCount("code") ?? 0);

  return `
    <section class="panel" id="p-hero">
      <div class="trust"><span class="live"></span><span>${fmt(STATS.totals.runs, 0)} verified community speed runs</span></div>

      <h1>Your machine is <span class="em">under‑used</span>.</h1>
      <div class="hero-sub">We'll show you every model it can actually run — and what it feels like to run them.</div>

      <div class="detect-card">
        <div class="detect-head">
          <div class="t">${rig ? "Your machine" : "Tell us your rig"}</div>
          <div class="m">${rig ? (SOURCE_LABEL[state.machineSource] ?? state.machineSource) : "WebGPU probe"}</div>
        </div>

        ${rig ? `
          <div class="detect-rig">
            <div class="name">${escapeHtml(rig.label)}</div>
            <div class="meta">${fmtBw(rig.bandwidthGBs)} · ${hwClassLabel(rig)}</div>
          </div>
          <button class="detect-primary" id="changeMachine" style="background:var(--surface-2);border-color:var(--hair)">
            <div class="icon" style="background:rgba(255,255,255,.05);color:var(--ink)">↻</div>
            <div class="txt">
              <div class="lbl" style="color:var(--ink)">Change machine</div>
              <div class="dsc">try a different rig</div>
            </div>
          </button>
        ` : `
          <button class="detect-primary" id="autoDetectBtn">
            <div class="icon">⌘</div>
            <div class="txt">
              <div class="lbl">Auto‑detect this device</div>
              <div class="dsc">WebGPU probe · nothing leaves your browser</div>
            </div>
          </button>

          <div class="detect-or">or choose a rig</div>
          <button class="detect-select" id="pickMachineBtn" style="display:block;text-align:left">— pick a reference rig —</button>
        `}

        <div class="detect-foot">
          <span class="lock">●</span>
          <span>Privacy-first · verified pool on this exact rig</span>
        </div>
      </div>
    </section>

    ${rig ? `
    <!-- PANEL 2: ENVELOPE -->
    <section class="panel" id="p-envelope">
      <div class="kicker">Your envelope</div>
      <h2>This is what your machine <span class="em">can hold</span>.</h2>
      <div class="sub">VRAM decides what runs. Bandwidth decides how fast. We'll use both to score every model.</div>

      <div class="spec-card">
        <div class="spec-head">
          <div class="name">${escapeHtml(rig.label)}</div>
          <div class="tag">${SOURCE_LABEL[state.machineSource] ?? state.machineSource}</div>
        </div>

        <div class="spec-row"><div class="lbl">GPU</div><div class="val">${escapeHtml(rig.label)}</div><div class="num"></div></div>
        <div class="spec-row"><div class="lbl">VRAM</div><div class="val">${rig.memGb} GB</div><div class="num">key number</div></div>
        <div class="spec-row"><div class="lbl">Bandwidth</div><div class="val">${fmtBw(rig.bandwidthGBs)}</div><div class="num">→ speed</div></div>
        <div class="spec-row"><div class="lbl">Class</div><div class="val">${hwClassLabel(rig)}</div><div class="num"></div></div>
      </div>
    </section>

    <!-- PANEL 3: CATEGORIES -->
    <section class="panel" id="p-cats">
      <div class="kicker">What fits</div>
      <h2><span class="em">${totalFit} models</span> fit at 4-bit.</h2>
      <div class="sub">Tap a category. Every number is a live count of models that fit your exact VRAM.</div>

      <div class="pillars">
        ${PILLARS.map((c) => pillarHtml(c)).join("")}
      </div>
    </section>

    <!-- PANEL 4: CATALOG -->
    <section class="panel" id="p-catalog">
      <div class="catalog-top">
        <h2><span class="cat">${cat.name}</span> that fit.</h2>
        <div class="catalog-controls">
          <button class="cat-btn ${state.sort === "speed" ? "on" : ""}" data-sort="speed">fast</button>
          <button class="cat-btn ${state.sort === "capable" ? "on" : ""}" data-sort="capable">big</button>
          <button class="cat-btn ${state.sort === "quality" ? "on" : ""}" data-sort="quality">best fit</button>
        </div>
      </div>

      ${cards.length === 0 ? `
        <div style="padding:40px 20px;text-align:center;color:var(--muted);font-family:var(--mono);font-size:12px;background:var(--surface);border-radius:12px;border:1px solid var(--hair)">
          No ${cat.name.toLowerCase()} models fit this rig at 4-bit yet.<br><span style="color:var(--dim);font-size:11px;margin-top:8px;display:inline-block">The pool only covers text inference today.</span>
        </div>
      ` : `
        <div class="catalog-scroll" id="catScroll">
          ${cards.map(catalogCard).join("")}
        </div>
      `}
    </section>

    ${best ? `
    <!-- PANEL 5: TEST DRIVE -->
    <section class="panel" id="p-td">
      <div class="kicker">Test drive</div>
      <h2>See it <span class="em">run</span>.</h2>
      <div class="sub" id="tdSub"></div>
      <div class="td-card">
        <div class="td-model">
          <div class="name" id="tdName">—</div>
          <div class="meta" id="tdMeta">—</div>

          <div class="td-vram">
            <div class="bar"><div class="fill" id="tdVramFill" style="width:0%"></div></div>
            <div class="lbl"><span id="tdVramLbl">— / — GB</span><span>weights + KV cache</span></div>
          </div>

          <div class="td-speed">
            <div class="num" id="tdSpeed">—</div>
            <div class="unit">tokens / sec</div>
          </div>
          <div class="td-basis" id="tdBasis"></div>
        </div>

        <div class="preview">
          <div class="preview-head"><span>live preview</span><span>text → text</span></div>
          <div class="preview-body">
            <div class="preview-text" id="prevText"></div>
            <canvas id="prevCanvas"></canvas>
          </div>
        </div>

        <div class="td-cta">
          <button class="btn-secondary" id="copyRunCmd">Copy run command</button>
          <button class="btn-secondary" id="changeModel">Change model</button>
        </div>
      </div>
    </section>

    <!-- PANEL 6: COHORT -->
    <section class="panel" id="p-cohort">
      <div class="kicker">Your cohort</div>
      <h2><span class="em">People with ${escapeHtml(rig.label)}</span> run these.</h2>
      ${cohortHtml(rig, false, 0)}
    </section>
    ` : ""}
    ` : ""}
  `;
}

function pillarHtml(cat) {
  if (!cat.enabled) {
    return `<button class="pillar disabled" aria-disabled="true">
      <div class="icon">${cat.icon}</div>
      <div class="name">${cat.name}</div>
      <div class="count nodata">no community data yet</div>
    </button>`;
  }
  const count = categoryCount(cat.id);
  return `<button class="pillar ${cat.id === state.category ? "on" : ""}" data-cat="${cat.id}">
    <div class="icon">${cat.icon}</div>
    <div class="name">${cat.name}</div>
    <div class="count"><b>${count ?? "—"}</b>${count == null ? "" : count === 1 ? " model fits" : " models fit"}</div>
  </button>`;
}

function sortCatalog(list) {
  const bySort = {
    speed: (a, b) => (b.est?.value ?? -1) - (a.est?.value ?? -1) || (b.m.paramsB ?? -1) - (a.m.paramsB ?? -1) || a.m.slug.localeCompare(b.m.slug),
    capable: (a, b) => (b.m.paramsB ?? -1) - (a.m.paramsB ?? -1) || (b.est?.value ?? -1) - (a.est?.value ?? -1) || a.m.slug.localeCompare(b.m.slug),
    quality: (a, b) => (b.headroom ?? -1) - (a.headroom ?? -1) || (b.est?.value ?? -1) - (a.est?.value ?? -1) || a.m.slug.localeCompare(b.m.slug),
  };
  list.sort((x, y) => {
    const dx = x.est ? 0 : 1, dy = y.est ? 0 : 1;
    if (dx !== dy) return dx - dy; // models without an estimate stay at the end
    return bySort[state.sort](x, y);
  });
}

function catalogCard({ m, fit, est, need }) {
  const fitLbl = fitLabel(fit);
  return `
    <button class="model-card" data-model="${m.slug}">
      <div class="top">
        <div class="name">${escapeHtml(m.displayName)}</div>
        <div class="params">${paramsLabel(m)}</div>
      </div>
      <div class="meta">4-bit · ${m.category}${est ? ` · ${est.n} ${est.n === 1 ? "run" : "runs"}` : " · no data yet"}</div>
      <div class="stats">
        <div class="stat"><div class="lbl">Speed</div><div class="val ${est ? "good" : ""}">${est ? `${fmt(est.value)} t/s` : "—"}</div>${basisBadge(est?.basis).outerHTML}</div>
        <div class="stat"><div class="lbl">VRAM</div><div class="val">${need ? `${fmt(need.gb)} GB` : "—"}</div></div>
        <div class="stat"><div class="lbl">Fit</div><div class="val ${FIT_VAL_CLASS[fit] ?? ""}">${fitLbl.text}</div></div>
      </div>
      <div class="run">Test drive →</div>
    </button>
  `;
}

function recCard(pick, rank) {
  const rig = currentRig();
  const need = vramNeededGb(pick.model, pick.bits);
  const usable = rig ? usableMemGb(rig) : null;
  const headPct = need && usable ? Math.max(4, Math.min(100, ((usable - need.gb) / usable) * 100)) : 4;
  const warn = headPct < 15;
  const tag = rank === 0 ? "Best fit" : rank === 1 ? "Runner-up" : "Also great";
  const fitLbl = fitLabel(pick.fit);
  return `
    <div class="rec ${rank === 0 ? "best" : ""}">
      <div class="rec-head">
        <div class="badge">${tag}</div>
        <div class="reason-short">${fitLbl.text}</div>
      </div>
      <div class="name">${escapeHtml(pick.model.displayName)}</div>
      <div class="meta">${paramsLabel(pick.model)} · ${pick.model.category} · ${pick.bits}-bit · ${fitLbl.text}</div>
      <div class="hd"><div class="hd-fill ${warn ? "warn" : ""}" style="width:${headPct}%"></div></div>
      <div class="reason">
        ${pick.est ? `<b>${fmt(pick.est.value)} tok/s</b>` : "no speed data yet"}
        ${pick.est ? ` · ${basisBadge(pick.est.basis).outerHTML} · ${pick.est.n} ${pick.est.n === 1 ? "run" : "runs"}` : ""}
      </div>
    </div>
  `;
}

/* ---------------- COHORT ---------------- */

function cohortData(rig) {
  const rigCells = CELLS.filter((c) => c.rigKey === rig.key);
  const byModel = new Map();
  for (const c of rigCells) {
    let agg = byModel.get(c.modelSlug);
    if (!agg) { agg = { slug: c.modelSlug, n: 0, rep: null }; byModel.set(c.modelSlug, agg); }
    agg.n += c.n;
    if (!agg.rep || c.n > agg.rep.n) agg.rep = c;
  }
  return [...byModel.values()].sort((a, b) => b.n - a.n || a.slug.localeCompare(b.slug)).slice(0, 5);
}

function cohortHtml(rig, withStats, fitCount) {
  const top5 = cohortData(rig);
  const rows = top5.length
    ? top5.map((agg, i) => {
        const model = modelsBySlug.get(agg.slug);
        return `
          <li>
            <span class="rank ${i === 0 ? "top" : ""}">${String(i + 1).padStart(2, "0")}</span>
            <span class="name">${escapeHtml(model?.displayName ?? agg.slug)}</span>
            <span class="ts">${fmt(agg.rep.tokSOutMedian)} t/s · ${agg.n} ${agg.n === 1 ? "run" : "runs"}</span>
          </li>`;
      }).join("")
    : `<li><span class="name" style="color:var(--muted)">no runs on this rig yet</span></li>`;

  const stats = withStats ? `
    <div class="stat-grid">
      <div class="stat-box">
        <div class="t">community rigs</div>
        <div class="n">${fmt(STATS.totals.rigs, 0)}</div>
        <div class="s">verified single-stream pool</div>
      </div>
      <div class="stat-box">
        <div class="t">models fit</div>
        <div class="n">${fmt(fitCount, 0)}</div>
        <div class="s">your envelope at ${currentBits()}-bit</div>
      </div>
    </div>` : "";

  return `
    <div class="cohort">
      <div class="cohort-head">
        <div>
          <div class="t">Top on your rig</div>
          <div class="m">by run count · community pool</div>
        </div>
        <div class="live">live</div>
      </div>
      <ul class="top-list">${rows}</ul>
      ${stats}
    </div>`;
}

/* ---------------- TEST DRIVE (post-render fill) ---------------- */

let tdTimer = null;

function renderTestDrive() {
  const rig = currentRig();
  const info = tdInfo();
  if (!rig || !info) return;
  const { m, bits, est } = info;
  const need = vramNeededGb(m, bits);
  const usable = usableMemGb(rig);

  document.getElementById("tdName").textContent = m.displayName;
  document.getElementById("tdMeta").textContent = `${paramsLabel(m)} · ${bits}-bit · ${m.category}`;
  document.getElementById("tdSub").textContent = subCopy(est);

  const pct = need && usable ? (need.gb / usable) * 100 : 0;
  const fill = document.getElementById("tdVramFill");
  fill.style.width = `${pct}%`;
  fill.classList.toggle("warn", pct > 80);
  document.getElementById("tdVramLbl").textContent = `${need ? fmt(need.gb) : "—"} / ${fmt(usable)} GB`;

  const speedEl = document.getElementById("tdSpeed");
  if (!est) speedEl.textContent = "—";
  else animateSpeed(speedEl, est.value);

  const basisEl = document.getElementById("tdBasis");
  basisEl.innerHTML = "";
  basisEl.appendChild(basisBadge(est?.basis));

  renderPreview(m, est);
}

function animateSpeed(el, target) {
  let current = 0;
  const start = performance.now();
  const duration = 1200;
  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    current = target * (1 - Math.pow(1 - t, 3));
    el.textContent = current.toFixed(1);
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function renderPreview(m, est) {
  if (tdTimer) { clearInterval(tdTimer); tdTimer = null; }
  const text = document.getElementById("prevText");
  const canvas = document.getElementById("prevCanvas");
  if (!text || !canvas) return;
  canvas.style.display = "none";
  text.style.display = "block";
  let pos = 0;
  text.innerHTML = '<span class="cur"></span>';
  const speed = est ? Math.max(3, Math.floor(est.value * 0.4)) : 6;
  tdTimer = setInterval(() => {
    pos += speed;
    if (pos > SAMPLE_TEXT.length) pos = SAMPLE_TEXT.length;
    text.innerHTML = escapeHtml(SAMPLE_TEXT.slice(0, pos)) + '<span class="cur"></span>';
    if (pos >= SAMPLE_TEXT.length) clearInterval(tdTimer);
  }, 60);
}

/* ---------------- CONSTELLATION ---------------- */

let constTimer = null;

function renderConstellation() {
  const canvas = document.getElementById("constellationCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = canvas.offsetHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = canvas.offsetWidth, H = canvas.offsetHeight;
  if (!W || !H) return;

  const rig = currentRig();
  const litRatio = rig && MODELS.length ? Math.min(1, buildCandidates().length / MODELS.length) : 0.2;
  const N = 90;
  const points = [];
  for (let i = 0; i < N; i++) {
    const lit = Math.random() < litRatio;
    points.push({ x: Math.random() * W, y: Math.random() * H, r: lit ? 2 : 1, lit, vx: (Math.random() - 0.5) * 0.2, vy: (Math.random() - 0.5) * 0.2 });
  }

  if (constTimer) cancelAnimationFrame(constTimer);
  function frame() {
    ctx.fillStyle = "rgba(18,20,23,0.15)";
    ctx.fillRect(0, 0, W, H);
    points.forEach((p) => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
      ctx.fillStyle = p.lit ? "#E0A458" : "#4A4F57";
      ctx.globalAlpha = p.lit ? 0.9 : 0.4;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    constTimer = requestAnimationFrame(frame);
  }
  frame();
}

/* ---------------- EVENTS ---------------- */

function bindEvents() {
  document.querySelectorAll(".intent-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      state.output = btn.dataset.output;
      state.selectedModel = null;
      render();
      haptic();
    });
  });

  const mp = document.getElementById("machinePick") || document.getElementById("machinePick2");
  if (mp) mp.addEventListener("click", () => openMachineSheet());

  const ad = document.getElementById("autoDetectBtn");
  if (ad) ad.addEventListener("click", autoDetect);

  const pm = document.getElementById("pickMachineBtn");
  if (pm) pm.addEventListener("click", () => openMachineSheet());

  const cm = document.getElementById("changeMachine");
  if (cm) cm.addEventListener("click", () => openMachineSheet());

  document.querySelectorAll(".pillar").forEach((p) => {
    if (p.hasAttribute("aria-disabled")) return;
    p.addEventListener("click", () => {
      state.category = p.dataset.cat;
      state.selectedModel = null;
      render();
      haptic();
    });
  });

  document.querySelectorAll(".cat-btn").forEach((b) => {
    b.addEventListener("click", () => {
      state.sort = b.dataset.sort;
      render();
      haptic();
    });
  });

  document.querySelectorAll(".model-card, .spec-node").forEach((c) => {
    c.addEventListener("click", () => {
      const m = modelsBySlug.get(c.dataset.model);
      if (!m) return;
      state.selectedModel = m;
      render();
      haptic();
      setTimeout(() => {
        const td = document.getElementById("p-td");
        if (td) td.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    });
  });

  document.querySelectorAll("[data-quant]").forEach((b) => {
    b.addEventListener("click", () => {
      state.quant = quantBits(b.dataset.quant);
      state.selectedModel = null;
      render();
      haptic();
    });
  });

  const crc = document.getElementById("copyRunCmd");
  if (crc) crc.addEventListener("click", async () => {
    const info = tdInfo();
    if (!info?.m) return;
    try {
      await navigator.clipboard.writeText(info.m.hfId);
      toast(`Copied ${info.m.hfId}`);
    } catch {
      toast("Copy failed");
    }
    haptic();
  });

  const chm = document.getElementById("changeModel");
  if (chm) chm.addEventListener("click", () => openModelSheet());

  renderTestDrive();
  renderConstellation();
}

/* ---------------- BOTTOM SHEET ---------------- */

const sheet = document.getElementById("sheet");
const sheetTitle = document.getElementById("sheetTitle");
const sheetList = document.getElementById("sheetList");
let sheetCallback = null;

function openSheet(title, items, onSelect) {
  sheetTitle.textContent = title;
  sheetList.innerHTML = items.map((it) => `
    <button class="sheet-item ${it.active ? "on" : ""}${it.enabled === false ? " disabled" : ""}" data-id="${it.id}" ${it.enabled === false ? 'aria-disabled="true"' : ""}>
      <div class="ic">${it.icon || "·"}</div>
      <div class="txt">
        <div class="lbl">${escapeHtml(it.label)}</div>
        ${it.dsc ? `<div class="dsc">${escapeHtml(it.dsc)}</div>` : ""}
      </div>
    </button>
  `).join("");
  sheetCallback = onSelect;
  sheet.classList.add("on");
  haptic();
}

function closeSheet() {
  sheet.classList.remove("on");
  sheetCallback = null;
}

sheet.addEventListener("click", (e) => {
  if (e.target === sheet) closeSheet();
  const item = e.target.closest(".sheet-item");
  if (item && sheetCallback && item.getAttribute("aria-disabled") == null) {
    sheetCallback(item.dataset.id);
    closeSheet();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeSheet();
});

function openMachineSheet() {
  openSheet("Pick your machine", TOP.map((tr) => {
    const rig = rigByKey.get(tr.key);
    return {
      id: tr.key,
      label: tr.label,
      dsc: rig
        ? `${fmt(tr.runCount)} runs · ${rig.memGb != null ? `${rig.memGb} GB` : hwClassLabel(rig)}${rig.bandwidthGBs != null ? ` · ${fmtBw(rig.bandwidthGBs)}` : ""}`
        : `${fmt(tr.runCount)} runs`,
      icon: "▦",
      active: state.machine === tr.key,
    };
  }), (id) => setMachine(id, "selected"));
}

function openOutputSheet() {
  openSheet("Pick an output", OUTPUTS.map((o) => ({
    id: o.id,
    label: `${state.input} → ${o.label}`,
    dsc: o.enabled ? o.ex : "no community data yet",
    icon: o.g,
    enabled: o.enabled,
    active: state.output === o.id,
  })), (id) => {
    state.output = id;
    state.selectedModel = null;
    render();
    haptic();
  });
}

function openModelSheet() {
  const rig = currentRig();
  if (!rig) return;
  const pool = buildCandidates();
  sortCandidates(pool);
  const items = pool.slice(0, 40).map((x) => ({
    id: x.m.slug,
    label: x.m.displayName,
    dsc: `${paramsLabel(x.m)} · ${currentBits()}-bit · ${x.est ? `${fmt(x.est.value)} tok/s · ${x.est.basis}` : "no speed data"}`,
    icon: "▭",
    active: state.selectedModel?.slug === x.m.slug,
  }));
  if (!items.length) { toast("No models to pick right now"); return; }
  openSheet("Pick a model", items, (id) => {
    const m = modelsBySlug.get(id);
    if (m) {
      state.selectedModel = m;
      render();
      haptic();
      setTimeout(() => {
        const td = document.getElementById("p-td");
        if (td) td.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  });
}

function setMachine(key, source) {
  state.machine = key;
  state.machineSource = source;
  state.selectedModel = null;
  render();
  const rig = rigByKey.get(key);
  toast(`${rig?.label ?? "Machine"} · ready`);
}

/* ---------------- AUTO-DETECT (WebGPU, ported from S5) ---------------- */

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

async function autoDetect() {
  const btn = document.getElementById("autoDetectBtn");
  if (!btn) return;
  btn.innerHTML = `<div class="icon">…</div><div class="txt"><div class="lbl">Detecting…</div><div class="dsc">probing WebGPU — nothing leaves your browser</div></div>`;
  let guess = null;
  try {
    const gpu = navigator.gpu;
    if (gpu && gpu.requestAdapter) {
      const adapter = await gpu.requestAdapter();
      const info = adapter?.info ?? (adapter ? await adapter.requestAdapterInfo() : null);
      guess = guessRigByVendor(String(info?.vendor ?? ""));
    }
  } catch {
    guess = null;
  }
  if (guess) {
    setMachine(guess.key, "guess");
    toast(`Best guess: ${guess.label}`);
  } else {
    toast("No WebGPU detection here — pick a reference rig");
    openMachineSheet();
  }
}

/* ---------------- BOTTOM BAR / CTA ---------------- */

function updateBottomBar() {
  const chips = document.getElementById("bottomChips");
  const status = document.getElementById("bottomStatus");
  chips.innerHTML = "";
  const parts = [];
  if (state.journey === "goal") parts.push({ k: "output", label: `${state.input} → ${state.output}`, cls: "amber" });
  else parts.push({ k: null, label: "hardware-first", cls: "amber" });
  if (state.machine) {
    const rig = currentRig();
    parts.push({ k: "machine", label: rig.label.split(" ").slice(0, 2).join(" "), cls: "green" });
  }
  for (const p of parts) {
    const chip = el("button", { class: "mini-chip " + p.cls, "data-k": p.k }, p.label);
    if (p.k === "output") chip.addEventListener("click", () => openOutputSheet());
    else if (p.k === "machine") chip.addEventListener("click", () => openMachineSheet());
    chips.appendChild(chip);
  }
  status.classList.toggle("active", !!state.machine);
}

function updateFinalCTA() {
  const btn = document.getElementById("mainCta");
  const txt = document.getElementById("ctaText");
  if (!state.machine) {
    txt.textContent = state.journey === "goal" ? "Pick your machine" : "Detect your machine";
    btn.onclick = () => openMachineSheet();
  } else {
    txt.textContent = state.journey === "goal" ? "See my top 3 models" : "See all models";
    btn.onclick = () => {
      const target = state.journey === "goal" ? "p-recs" : "p-catalog";
      const el = document.getElementById(target);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      else document.getElementById("finalPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    };
  }
}

/* ---------------- JOURNEY SWITCHER / FOOTER / BOOT ---------------- */

function updateJourneySeg() {
  document.querySelectorAll(".journey-btn").forEach((b) => {
    const on = b.dataset.journey === state.journey;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
}

function renderFooter() {
  const foot = document.getElementById("footer");
  foot.replaceWith(attributionFooter(STATS));
}

async function boot() {
  const d = await loadDerived();
  RIGS = d.hardware.rigs;
  MODELS = d.models.models;
  CELLS = d.pool.cells;
  STATS = d.stats;
  TOP = STATS.topRigs;
  for (const r of RIGS) rigByKey.set(r.key, r);
  for (const m of MODELS) modelsBySlug.set(m.slug, m);

  // Check hash for journey (useful for ads deep links).
  const hash = window.location.hash.replace("#", "");
  if (hash === "hardware" || hash === "goal") state.journey = hash;
  updateJourneySeg();

  document.querySelectorAll(".journey-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".journey-btn").forEach((b) => {
        b.classList.remove("on");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("on");
      btn.setAttribute("aria-selected", "true");
      state.journey = btn.dataset.journey;
      state.selectedModel = null;
      render();
      window.scrollTo({ top: 0 });
      haptic();
      try { history.replaceState(null, "", "#" + state.journey); } catch {}
    });
  });

  document.getElementById("cpBtn").addEventListener("click", async () => {
    const cmd = document.getElementById("installCmd").textContent;
    try {
      await navigator.clipboard.writeText(cmd);
      const cp = document.getElementById("cpBtn");
      cp.textContent = "copied ✓";
      cp.classList.add("done");
      setTimeout(() => { cp.textContent = "copy"; cp.classList.remove("done"); }, 1800);
    } catch {
      toast("Copy failed");
    }
    haptic();
  });

  renderFooter();
  render();
}

boot().catch((err) => console.error("mobile-page:", err));
