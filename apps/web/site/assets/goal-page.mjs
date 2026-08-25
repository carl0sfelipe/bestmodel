// S6 — goal-first journey (site/index.html) page logic.
// All data comes from data/derived/* via loadDerived(); every displayed
// number carries a basis (CONTRATO §1). The engine does fit/speed; this
// module only wires DOM + the real pool. No formulas live here.
import { el, fmt, basisBadge, fitLabel, attributionFooter } from "./ui.mjs";
import { loadDerived } from "./load-data.mjs";
import {
  quantBits, usableMemGb, vramNeededGb, fitClass, estimateTokS, topPicks,
} from "./engine.mjs";

// Quant segment labels (CONTRATO §6): FP16/Q8/Q6/Q4 map via engine.quantBits.
const QUANT_SEG = ["FP16", "Q8", "Q6", "Q4"];

// Output options: text/code have real community data (CONTRATO §4); the rest
// stay disabled with the honest tooltip (§7.6).
const OUTPUTS = [
  { id: "text", label: "text", g: "▭", enabled: true },
  { id: "code", label: "code", g: "<", enabled: true },
  { id: "image", label: "image", g: "▦", enabled: false },
  { id: "audio", label: "audio", g: "∿", enabled: false },
  { id: "video", label: "video", g: "▶", enabled: false },
  { id: "embed", label: "embeddings", g: "•", enabled: false },
];

// Sample prose for the live preview (kept from the prototype).
const SAMPLE_TEXT = `The morning light settled across the workshop like a thin sheet of tin. She wiped the lens with the hem of her shirt, then aimed it at the engine block. "Tell me what this is," she said. The model hesitated, then began: a V-twin, cast iron, the kind that outlives the people who bolt it in. Each sentence arrived at a steady cadence — fast enough that the cursor barely flickered, slow enough to feel human.`;

const state = {
  output: "text",   // text | code
  machine: null,    // rig key (set at boot from stats.topRigs[0])
  quant: 4,         // bits
  query: "",
  listeners: [],
};

let RIGS = [];
let MODELS = [];
let CELLS = [];
let STATS = null;
let TOP = [];
let UNIV = [];
const rigByKey = new Map();
const modelsBySlug = new Map();

const currentRig = () => (state.machine ? rigByKey.get(state.machine) : null);
const currentCategory = () => (state.output === "code" ? "code" : "chat");
const currentBits = () => state.quant;

function setState(patch) {
  Object.assign(state, patch);
  state.listeners.forEach((fn) => fn(state));
}
function subscribe(fn) { state.listeners.push(fn); }

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

function escapeHtml(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

/* ---------------- MAD-LIB (s01) ---------------- */

function refreshHeroTokens() {
  const out = document.querySelector('.token[data-k="output"]');
  out.innerHTML = `${state.output}<span class="chev">⌄</span>`;
  const rig = currentRig();
  const mach = document.querySelector('.token[data-k="machine"]');
  mach.innerHTML = `${escapeHtml(rig ? rig.label : "this machine")}<span class="chev">⌄</span>`;
  document.getElementById("plateBT").textContent = `text → ${state.output}`;
}

/* ---------------- POPOVER / RAIL ---------------- */

function openPopoverFor(kind, anchor) {
  const pop = document.getElementById("popover");
  let items = [];
  let activeId = "";
  if (kind === "intent") {
    items = OUTPUTS.map((o) => ({ id: `text>${o.id}`, label: `text → ${o.label}`, enabled: o.enabled, g: o.g, disabledTip: !o.enabled ? "no community data yet" : null }));
    activeId = `text>${state.output}`;
  } else if (kind === "machine") {
    items = TOP.map((tr) => ({ id: tr.key, label: `${tr.label} · ${fmt(tr.runCount)} runs`, enabled: true }));
    activeId = state.machine;
  } else if (kind === "quant") {
    items = QUANT_SEG.map((q) => ({ id: q, label: `${q} · ${quantBits(q)}-bit`, enabled: true }));
    activeId = QUANT_SEG.find((q) => quantBits(q) === state.quant) || "Q4";
  }
  pop.innerHTML = items.map((i) => {
    const cls = ["pop-item", i.id === activeId ? "active" : "", i.enabled ? "" : "disabled"].filter(Boolean).join(" ");
    const tip = i.disabledTip ? ` title="${i.disabledTip}"` : "";
    const dis = i.enabled ? "" : ' data-disabled="1"';
    return `<div class="${cls}" data-id="${i.id}" data-kind="${kind}"${dis}${tip}><span class="g">${i.g || ""}</span><span>${i.label}</span></div>`;
  }).join("");
  pop.style.top = (anchor.bottom + 8) + "px";
  pop.style.left = Math.min(anchor.left, window.innerWidth - 320) + "px";
  pop.classList.add("on");
  pop.querySelectorAll(".pop-item").forEach((it) => {
    it.addEventListener("click", () => {
      const enabled = it.dataset.disabled == null;
      if (!enabled) return;
      const id = it.dataset.id;
      const kind = it.dataset.kind;
      if (kind === "intent") setState({ output: id.split(">")[1] });
      else if (kind === "machine") { setState({ machine: id }); syncRigSelect(); }
      else if (kind === "quant") setState({ quant: quantBits(id) });
      closePopover();
    });
  });
  setTimeout(() => document.addEventListener("click", onDoc, { once: true }), 0);
}
function onDoc(e) {
  const pop = document.getElementById("popover");
  if (!pop.contains(e.target)) closePopover();
  else document.addEventListener("click", onDoc, { once: true });
}
function closePopover() { document.getElementById("popover").classList.remove("on"); }

function renderRail() {
  const rail = document.getElementById("rail");
  const rig = currentRig();
  const quantLbl = QUANT_SEG.find((q) => quantBits(q) === state.quant) || "Q4";
  const chips = [
    { k: "intent", label: `text → ${state.output}` },
    { k: "machine", label: rig ? rig.label : "—" },
    { k: "quant", label: quantLbl },
  ];
  if (state.query) chips.push({ k: "query", label: `q: "${state.query}"` });
  rail.innerHTML = chips.map((c) => `<button class="chip" data-k="${c.k}"><span class="dot"></span>${escapeHtml(c.label)}<span class="x">×</span></button>`).join("");
  rail.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const rect = btn.getBoundingClientRect();
      if (btn.dataset.k === "query") { setState({ query: "" }); document.getElementById("modelSearch").value = ""; }
      else openPopoverFor(btn.dataset.k, rect);
    });
  });
  rail.classList.add("on");
}

/* ---------------- UNIVERSE (s02) ---------------- */

function buildUniverse() {
  // Node count = the REAL number of models (§7.2 — no UNIVERSE_FILL).
  UNIV = MODELS.map((m, i) => ({
    x: Math.random(), y: Math.random(),
    vx: (Math.random() - 0.5) * 0.0002, vy: (Math.random() - 0.5) * 0.0002,
    category: m.category, r: 1.4, seed: i,
  }));
}

const bg02 = document.getElementById("bg02");
const ctx02 = bg02.getContext("2d");
function sizeBg(c, ctx) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  c.width = c.clientWidth * dpr;
  c.height = c.clientHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
function drawBg02(p) {
  const w = bg02.clientWidth, h = bg02.clientHeight;
  if (!w || !h) return;
  ctx02.clearRect(0, 0, w, h);
  const sweep = p * 1.3 - 0.15;
  const cat = currentCategory();
  UNIV.forEach((n, i) => {
    n.x += n.vx; n.y += n.vy;
    if (n.x < 0 || n.x > 1) n.vx *= -1;
    if (n.y < 0 || n.y > 1) n.vy *= -1;
    const ioMatch = n.category === cat;
    const inSweep = n.x < sweep;
    let alpha, color;
    if (p < 0.25) { alpha = 0.22; color = "#4A4F57"; }
    else if (p < 0.6) {
      if (ioMatch && inSweep) { alpha = 0.85; color = "#E0A458"; }
      else if (inSweep) { alpha = 0.1; color = "#4A4F57"; }
      else { alpha = 0.22; color = "#4A4F57"; }
    } else if (p < 0.8) {
      const cx = 0.5, cy = 0.5;
      const t = (p - 0.6) / 0.2;
      n._nx = n.x + (cx - n.x) * t * 0.4;
      n._ny = n.y + (cy - n.y) * t * 0.4;
      if (ioMatch) { alpha = 0.85; color = "#E0A458"; }
      else { alpha = 0.08; color = "#4A4F57"; }
    } else {
      if (ioMatch) { alpha = 0.6; color = "#E0A458"; }
      else alpha = 0;
    }
    const px = (p < 0.6 || p >= 0.8 ? n.x : (n._nx || n.x)) * w;
    const py = (p < 0.6 || p >= 0.8 ? n.y : (n._ny || n.y)) * h;
    ctx02.globalAlpha = alpha;
    ctx02.fillStyle = color;
    ctx02.beginPath();
    ctx02.arc(px, py, n.r, 0, Math.PI * 2);
    ctx02.fill();
  });
  ctx02.globalAlpha = 1;
}

function renderUniverseCounts() {
  const total = STATS.totals.models;
  const cat = currentCategory();
  const match = MODELS.filter((m) => m.category === cat).length;
  document.getElementById("univTotal").textContent = fmt(total, 0);
  document.getElementById("univMatch").textContent = fmt(match, 0);
}

/* ---------------- MACHINE (s03) ---------------- */

let termLastMachine = null;
function typeTerm() {
  const rig = currentRig();
  if (!rig) return;
  if (termLastMachine === state.machine && termBody.dataset.done === "1") return;
  termLastMachine = state.machine;
  const termBody = document.getElementById("termBody");
  termBody.dataset.done = "0";
  termBody.innerHTML = "";
  const lines = [
    { t: `$ can-i-run-it detect`, c: "cmd" },
    { t: `[ok]  GPU   `, lbl: rig.label, v: "" },
    { t: `[ok]  VRAM  `, lbl: `${rig.memGb} GB`, v: "" },
    { t: `[ok]  CLASS `, lbl: hwClassLabel(rig), v: "" },
    { t: `[ok]  BW    `, lbl: fmtBw(rig.bandwidthGBs), v: "" },
    { t: `> ready`, c: "ok" },
  ];
  lines.forEach((L, i) => {
    const el2 = document.createElement("div");
    el2.className = "term-line";
    if (L.c === "cmd") el2.innerHTML = `<span class="cmd">${L.t}</span><span class="caret"></span>`;
    else if (L.c === "ok") el2.innerHTML = `<span class="ok">${L.t}</span>`;
    else el2.innerHTML = `<span class="ok">${L.t}</span><span class="val">${L.lbl}</span>`;
    termBody.appendChild(el2);
    setTimeout(() => {
      el2.classList.add("on");
      if (L.c === "cmd") el2.innerHTML = `<span class="cmd">${L.t}</span>`;
    }, 80 + i * 180);
  });
  setTimeout(() => { termBody.dataset.done = "1"; }, 80 + lines.length * 180 + 200);

  // schematic labels reflect the selected rig (spec S6 §3); missing -> "—"
  document.getElementById("mbLbl").textContent = "motherboard · " + hwClassLabel(rig);
  document.getElementById("gpuLbl").textContent = `${rig.label} · ${rig.memGb} GB VRAM`;
  document.getElementById("cpuLbl").textContent = "—";
  document.getElementById("ramLbl").textContent = "—";
  document.getElementById("ssdLbl").textContent = "—";

  const sch = document.getElementById("schematic");
  sch.querySelectorAll(".part").forEach((p, i) => {
    p.classList.remove("on");
    setTimeout(() => p.classList.add("on"), 300 + i * 140);
  });
  sch.classList.remove("on");
  setTimeout(() => sch.classList.add("on"), 500);
}
const termBody = document.getElementById("termBody");

function fillRigSelect() {
  const sel = document.getElementById("rigSelect");
  sel.innerHTML = TOP.map((tr) => `<option value="${tr.key}">${tr.label} · ${fmt(tr.runCount)} runs</option>`).join("");
  sel.value = state.machine;
}
function syncRigSelect() {
  const sel = document.getElementById("rigSelect");
  if (sel.value !== state.machine) sel.value = state.machine;
}

/* ---------------- SPECTRUM (s04) ---------------- */

const specNodes = document.getElementById("specNodes");
let specNodeEls = [];
let lastSpectrumKey = "";

function categoryModels() {
  const cat = currentCategory();
  return MODELS.filter((m) => m.category === cat);
}

function fitList() {
  const rig = currentRig();
  const bits = currentBits();
  return categoryModels().map((m) => ({ m, fit: fitClass(rig, m, bits) }));
}

function renderSpectrum() {
  const rig = currentRig();
  if (!rig) return;
  const bits = currentBits();
  const data = fitList();
  const key = `${state.machine}|${bits}|${state.output}`;

  if (specNodeEls.length !== data.length) {
    specNodes.innerHTML = "";
    specNodeEls = data.map((d) => {
      const node = document.createElement("div");
      node.className = "snode";
      node.dataset.fit = d.fit ?? "none";
      specNodes.appendChild(node);
      node.addEventListener("mouseenter", (e) => showTip(e, d));
      node.addEventListener("mousemove", moveTip);
      node.addEventListener("mouseleave", hideTip);
      return node;
    });
  }
  data.forEach((d, i) => {
    const node = specNodeEls[i];
    node.dataset.fit = d.fit ?? "none";
    let leftPct;
    if (d.fit == null) leftPct = 2 + Math.random() * 6;
    else if (d.fit === "no") leftPct = 5 + Math.random() * 18;
    else if (d.fit === "tight") leftPct = 30 + Math.random() * 22;
    else if (d.fit === "ok") leftPct = 58 + Math.random() * 22;
    else leftPct = 82 + Math.random() * 14;
    node.style.left = leftPct + "%";
    node.style.top = (20 + (Math.random() * 40 - 20)) + "%";
    node.classList.add("on");
  });
  lastSpectrumKey = key;

  const match = data.filter((d) => d.fit != null && d.fit !== "no").length;
  const ok = data.filter((d) => d.fit === "ok" || d.fit === "head").length;
  document.getElementById("mcMatch").textContent = fmt(match, 0);
  document.getElementById("mcOk").textContent = fmt(ok, 0);

  const plateA = document.getElementById("plateA");
  plateA.querySelector(".t").textContent = `${rig.label}`;
  plateA.querySelector(".m").textContent = `bandwidth ${fmtBw(rig.bandwidthGBs)} · ${QUANT_SEG.find((q) => quantBits(q) === bits) || bits}-bit`;
}

const tip = document.getElementById("tip");
function showTip(e, d) {
  const rig = currentRig();
  const bits = currentBits();
  const need = vramNeededGb(d.m, bits);
  const est = estimateTokS(rig, d.m, bits, CELLS, RIGS);
  const fitLbl = fitLabel(d.fit).text;
  tip.textContent = `${d.m.displayName}\n${paramsLabel(d.m)} · ${bits}-bit · ${fitLbl}\n${need ? need.gb.toFixed(1) : "?"} GB · ${est ? est.value.toFixed(1) + " tok/s (" + est.basis + ")" : "no speed data"}`;
  tip.classList.add("on");
  moveTip(e);
}
function moveTip(e) {
  tip.style.left = (e.clientX + 14) + "px";
  tip.style.top = (e.clientY + 14) + "px";
}
function hideTip() { tip.classList.remove("on"); }

/* ---------------- SIMULATION (s05) ---------------- */

let simTimer = null;
function bestPick() {
  const rig = currentRig();
  if (!rig) return null;
  const picks = topPicks(rig, categoryModels(), CELLS, RIGS, 1);
  return picks[0] ?? null;
}

function renderSim() {
  const rig = currentRig();
  const pick = bestPick();
  if (!rig || !pick) {
    document.getElementById("simName").textContent = "—";
    document.getElementById("simMeta").textContent = "no candidates for this machine yet";
    document.getElementById("speedSub").textContent = "";
    document.getElementById("ctxRibbon").style.display = "none";
    return;
  }
  const m = pick.model;
  const bits = pick.bits;
  const est = pick.est;
  const need = vramNeededGb(m, bits);
  const usable = usableMemGb(rig);

  document.getElementById("simName").textContent = m.displayName;
  document.getElementById("simMeta").textContent = `${paramsLabel(m)} · ${m.category} · ${bits}-bit · ${fitLabel(pick.fit).text}`;

  const pct = need && usable ? (need.gb / usable) * 100 : 0;
  const fill = document.getElementById("vramFill");
  fill.style.width = `${pct}%`;
  fill.classList.toggle("warn", pct > 80);
  document.getElementById("vramLbl").textContent = `${need ? fmt(need.gb) : "—"} / ${fmt(usable)} GB`;

  // context ribbon (§7.5): community-tested context, never extrapolated.
  const cell = CELLS.find((c) => c.rigKey === rig.key && c.modelSlug === m.slug && c.bits === bits);
  const maxCtx = cell?.maxContextTested ?? m.maxContextTested ?? null;
  const ribbon = document.getElementById("ctxRibbon");
  if (maxCtx == null) {
    ribbon.style.display = "none";
  } else {
    ribbon.style.display = "";
    const ref = 131072; // ticks go to 128k
    const reachPct = Math.min(100, (maxCtx / ref) * 100);
    document.getElementById("ctxReach").style.width = reachPct + "%";
    const ghost = document.getElementById("ctxGhost");
    ghost.style.display = "block";
    ghost.style.left = reachPct + "%";
    ghost.style.width = (100 - reachPct) + "%";
    document.getElementById("ctxCap").textContent = `community-tested up to ${fmt(maxCtx, 0)}`;
  }

  // speed odometer (animated like S5)
  const speedEl = document.getElementById("speedNum");
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
  document.getElementById("speedUnit").textContent = "tokens / sec";
  document.getElementById("speedSub").textContent = subCopy(est);
  renderSimPreview(m, est);
}

function subCopy(est) {
  if (!est) return "No community speed data for this exact rig + quant yet — fit is estimated from VRAM.";
  if (est.basis === "measured" || est.basis === "reported") {
    return `Based on ${est.n} community ${est.n === 1 ? "run" : "runs"} on this exact rig. Real speed may vary with drivers, power state, and concurrent workloads.`;
  }
  return `Extrapolated from ${est.n} community ${est.n === 1 ? "run" : "runs"} on a similar rig, scaled by memory bandwidth. Real speed may vary.`;
}

function renderSimPreview(m, est) {
  if (simTimer) { clearInterval(simTimer); simTimer = null; }
  const text = document.getElementById("prevText");
  const canvas = document.getElementById("prevCanvas");
  document.getElementById("prevMode").textContent = "text → text";
  document.getElementById("prevSteps").textContent = "";
  canvas.style.display = "none";
  text.style.display = "block";
  let pos = 0;
  text.innerHTML = '<span class="cur"></span>';
  const speed = est ? Math.max(3, Math.floor(est.value * 0.4)) : 6;
  simTimer = setInterval(() => {
    pos += speed;
    if (pos > SAMPLE_TEXT.length) pos = SAMPLE_TEXT.length;
    text.innerHTML = escapeHtml(SAMPLE_TEXT.slice(0, pos)) + '<span class="cur"></span>';
    if (pos >= SAMPLE_TEXT.length) clearInterval(simTimer);
  }, 60);
}

/* ---------------- ANSWER (s06) ---------------- */

function recCard(pick, rank) {
  const rig = currentRig();
  const bits = pick.bits;
  const need = vramNeededGb(pick.model, bits);
  const usable = usableMemGb(rig);
  const headPct = need && usable ? Math.max(4, Math.min(100, ((usable - need.gb) / usable) * 100)) : 4;
  const warn = headPct < 15;
  const fitLbl = fitLabel(pick.fit);
  const tag = rank === 0 ? "Best fit" : rank === 1 ? "Runner-up" : "Also great";
  const est = pick.est;
  return el("div", { class: "rec" + (rank === 0 ? " best" : "") }, [
    el("div", { class: "badge" }, tag),
    el("div", { class: "name" }, pick.model.displayName),
    el("div", { class: "meta" }, `${paramsLabel(pick.model)} · ${pick.model.category} · ${bits}-bit · ${fitLbl.text}`),
    el("div", { class: "hd-room" }, [el("div", { class: "hd-fill" + (warn ? " warn" : ""), style: `width:${headPct}%` })]),
    el("div", { class: "reason" }, [
      est
        ? `${fmt(est.value)} tok/s `
        : "no speed data yet",
      basisBadge(est?.basis),
      est ? ` · ${est.n} ${est.n === 1 ? "run" : "runs"}` : "",
    ]),
  ]);
}

function renderRecs() {
  const rig = currentRig();
  const grid = document.getElementById("recGrid");
  grid.innerHTML = "";
  if (!rig) return;
  const q = state.query.trim().toLowerCase();
  if (q) {
    // Search across ALL derived models (spec S6 §6).
    const matches = MODELS.filter(
      (m) => m.displayName.toLowerCase().includes(q) || m.hfId.toLowerCase().includes(q)
    ).slice(0, 12);
    if (!matches.length) {
      grid.innerHTML = `<div class="rec" style="grid-column:1/-1"><div class="name" style="color:var(--muted)">No models match</div><div class="reason">Nothing named "${escapeHtml(state.query)}" is in the pool yet.</div></div>`;
      return;
    }
    const bits = currentBits();
    matches.forEach((m) => {
      const fit = fitClass(rig, m, bits);
      grid.appendChild(searchCard(m, fit, bits));
    });
    return;
  }
  const picks = topPicks(rig, categoryModels(), CELLS, RIGS, 3);
  if (!picks.length) {
    grid.innerHTML = `<div class="rec" style="grid-column:1/-1"><div class="name" style="color:var(--muted)">No candidates</div><div class="reason">Try a different intent, machine, or quantization.</div></div>`;
    return;
  }
  picks.forEach((p, i) => grid.appendChild(recCard(p, i)));
}

function searchCard(m, fit, bits) {
  const rig = currentRig();
  const fitLbl = fitLabel(fit);
  const card = el("div", { class: "rec" }, [
    el("div", { class: "badge" }, m.displayName === state.query ? "exact match" : "search"),
    el("div", { class: "name" }, m.displayName),
    el("div", { class: "meta" }, `${paramsLabel(m)} · ${m.category} · hf ${m.hfId}`),
  ]);
  if (fit === "no") {
    // Found but doesn't fit: suggest the largest quant that would fit, if any.
    const suggest = largestFitQuant(m);
    card.appendChild(el("div", { class: "reason" }, [
      el("span", { class: "fit-badge " + fitLbl.cssClass }, fitLbl.text),
      " at ",
      `${QUANT_SEG.find((qq) => quantBits(qq) === bits) || bits}-bit on ${rig.label}`,
      suggest ? el("div", { style: "margin-top:6px" }, `Fits at ${QUANT_SEG.find((qq) => quantBits(qq) === suggest)} (${suggest}-bit) — switch the quant switcher.`) : "",
    ]));
  } else {
    const est = estimateTokS(rig, m, bits, CELLS, RIGS);
    card.appendChild(el("div", { class: "hd-room" }, [el("div", { class: "hd-fill" + (fit === "tight" ? " warn" : ""), style: "width:60%" })]));
    card.appendChild(el("div", { class: "reason" }, [
      `Fits at ${bits}-bit (${fitLbl.text}). `,
      est ? `${fmt(est.value)} tok/s ` : "no speed data yet",
      basisBadge(est?.basis),
      est ? ` · ${est.n} ${est.n === 1 ? "run" : "runs"}` : "",
    ]));
  }
  return card;
}

function largestFitQuant(model) {
  const rig = currentRig();
  if (!rig) return null;
  const candidates = QUANT_SEG.map((q) => quantBits(q)).sort((a, b) => b - a); // 16,8,6,4
  for (const bits of candidates) {
    const f = fitClass(rig, model, bits);
    if (f !== "no" && f != null) return bits;
  }
  return null;
}

/* ---------------- SCROLL ENGINE (reused from prototype) ---------------- */

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
  renderAll();
}
let ticking = false;
function tick() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { calcProgress(); ticking = false; });
}
window.addEventListener("scroll", tick, { passive: true });
window.addEventListener("resize", tick);

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

function renderAll() {
  sceneState.forEach((s) => {
    if (s.progress > 0.02) s.el.classList.add("on");
  });
  const s02 = sceneState.find((s) => s.el.id === "s02");
  if (s02) { sizeBg(bg02, ctx02); drawBg02(s02.progress); }
  const s03 = sceneState.find((s) => s.el.id === "s03");
  if (s03 && s03.progress > 0.05) typeTerm();
  const s04 = sceneState.find((s) => s.el.id === "s04");
  if (s04 && s04.progress > 0.1 && lastSpectrumKey !== `${state.machine}|${state.quant}|${state.output}`) renderSpectrum();
  const s05 = sceneState.find((s) => s.el.id === "s05");
  if (s05 && s05.progress > 0.05) renderSim();
  const s06 = sceneState.find((s) => s.el.id === "s06");
  if (s06 && s06.progress > 0.05) renderRecs();
}

/* ---------------- WIRE-UP / BOOT ---------------- */

function wireButtons() {
  document.querySelectorAll(".token").forEach((t) => {
    t.addEventListener("click", () => {
      if (t.dataset.k === "input") return; // input is fixed text
      const r = t.getBoundingClientRect();
      if (t.dataset.k === "output") openPopoverFor("intent", r);
      else if (t.dataset.k === "machine") openPopoverFor("machine", r);
    });
  });

  document.getElementById("rigSelect").addEventListener("change", (e) => {
    if (e.target.value) setState({ machine: e.target.value });
  });

  document.getElementById("quantSeg").addEventListener("click", (e) => {
    const b = e.target.closest(".qbtn");
    if (!b) return;
    document.querySelectorAll("#quantSeg .qbtn").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    setState({ quant: quantBits(b.dataset.q) });
  });

  document.getElementById("modelSearch").addEventListener("input", (e) => {
    setState({ query: e.target.value });
  });

  document.getElementById("ghostMachine").addEventListener("click", () => {
    document.getElementById("rigSelect").scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById("rigSelect").focus();
  });
  document.getElementById("ghostIntent").addEventListener("click", () => {
    const t = document.querySelector('.token[data-k="output"]');
    if (t) { t.scrollIntoView({ behavior: "smooth", block: "center" }); const r = t.getBoundingClientRect(); setTimeout(() => openPopoverFor("intent", r), 500); }
  });

  document.getElementById("cpBtn").addEventListener("click", async () => {
    const cmd = document.getElementById("installCmd").textContent;
    try {
      await navigator.clipboard.writeText(cmd);
      const cp = document.getElementById("cpBtn");
      cp.textContent = "copied";
      cp.classList.add("done");
      setTimeout(() => { cp.textContent = "copy"; cp.classList.remove("done"); }, 1600);
    } catch {
      document.getElementById("cpBtn").textContent = "copy failed";
    }
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
  state.machine = TOP[0]?.key ?? null;

  buildUniverse();
  fillRigSelect();
  wireButtons();
  renderUniverseCounts();
  renderSpectrum();
  renderFooter();
  renderRail();
  refreshHeroTokens();
  calcProgress();
}

subscribe(() => {
  renderRail();
  refreshHeroTokens();
  renderSpectrum();
  renderSim();
  renderRecs();
});

boot().catch((err) => console.error("goal-page:", err));
