// S2 — aggregate the raw snapshot into the derived JSONs the site consumes.
// Rules: CONTRATO-GLOBAL.md §4 (schemas, identity §4.1), §6 (quant bits, seed).
import { mkdir, readFile, writeFile } from "node:fs/promises";

const round2 = (x) => Math.round(x * 100) / 100;
const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

export function quantBits(quant) {
  if (!quant) return null;
  const q = quant.trim();
  if (/^(fp16|bf16|f16)$/i.test(q)) return 16;
  if (/^fp8$/i.test(q)) return 8;
  if (/^(awq|gptq)$/i.test(q)) return 4;
  const digit = q.match(/[1-8]/);
  return digit ? Number(digit[0]) : null;
}

function normalizeGpuName(raw) {
  let name = (raw ?? "").trim();
  let prev;
  do { prev = name; name = name.replace(/^(NVIDIA|AMD|Intel|GeForce)\s+/i, ""); } while (name !== prev);
  return name.replace(/\s+\d+(\.\d+)?\s*GB$/i, "").trim();
}

function unifiedCanonicalName(hw) {
  const text = `${hw.chipVariant ?? ""} ${hw.chipFamily ?? ""}`;
  if (/gb10|dgx\s*spark/i.test(text)) return "GB10 Grace Blackwell";
  if (/ryzen|strix|ai\s*max/i.test(text)) {
    if (/395/.test(text)) return "Ryzen AI Max 395";
    if (/385/.test(text)) return "Ryzen AI Max 385";
  }
  return (hw.chipVariant ?? hw.chipFamily ?? "unknown").trim();
}

function buildVramModals(runs) {
  const counts = new Map(); // name -> Map(vram -> n) over gpuCount==1 runs
  for (const run of runs) {
    const hw = run.hardware;
    if (hw.hwClass !== "DISCRETE_GPU" || (hw.gpuCount ?? 1) !== 1 || hw.vramGb == null) continue;
    const name = normalizeGpuName(hw.gpuName);
    if (!counts.has(name)) counts.set(name, new Map());
    const perName = counts.get(name);
    perName.set(hw.vramGb, (perName.get(hw.vramGb) ?? 0) + 1);
  }
  const modals = new Map();
  for (const [name, perName] of counts) {
    const best = [...perName.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0];
    modals.set(name, best[0]);
  }
  return modals;
}

function perCardVram(hw, modals, name) {
  const vram = hw.vramGb, count = hw.gpuCount ?? 1, modal = modals.get(name);
  if (vram == null) return null;
  if (modal != null) {
    if (count > 1 && Math.abs(vram - modal * count) <= 1) return modal;
    if (Math.abs(vram - modal) <= 2) return modal;
  }
  return Math.round(vram);
}

function rigIdentity(hw, modals) {
  const count = hw.gpuCount ?? 1;
  if (hw.hwClass === "DISCRETE_GPU") {
    const name = normalizeGpuName(hw.gpuName);
    const perCard = perCardVram(hw, modals, name);
    const suffix = count > 1 ? ` x${count}` : "";
    return {
      key: slugify(`${name} ${perCard ?? "na"}gb${suffix}`),
      label: `${name} ${perCard ?? "?"}GB${count > 1 ? ` \u00d7${count}` : ""}`,
      matchName: name, memGb: perCard != null ? perCard * count : null, gpuCount: count,
    };
  }
  if (hw.hwClass === "UNIFIED") {
    const name = unifiedCanonicalName(hw);
    return {
      key: slugify(`${name} ${hw.unifiedMemoryGb ?? "na"}gb`),
      label: `${name} ${hw.unifiedMemoryGb ?? "?"}GB`,
      matchName: name, memGb: hw.unifiedMemoryGb ?? null, gpuCount: 1,
    };
  }
  const cpu = (hw.cpu ?? "unknown").trim();
  return { key: slugify(`cpu ${cpu}`), label: cpu, matchName: cpu, memGb: hw.ramGb ?? null, gpuCount: 1 };
}

function seedBandwidth(seed, identity, hwClass) {
  if (hwClass === "CPU_ONLY" || identity.gpuCount > 1) return null;
  const matches = Object.keys(seed)
    .filter((name) => identity.matchName.toLowerCase().includes(name.toLowerCase()))
    .sort((a, b) => b.length - a.length);
  return matches.length ? seed[matches[0]] : null;
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? round2(s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null;
};

function isSingleStream(run) {
  const flags = run.engineFlags ?? {};
  return (run.batchSize ?? 1) <= 1 && (flags.concurrency ?? 1) <= 1 && (flags.numParallel ?? 1) <= 1;
}

const raw = JSON.parse(await readFile("data/raw/speed-tests.json", "utf8"));
const rawModels = JSON.parse(await readFile("data/raw/models.json", "utf8"));
const seed = JSON.parse(await readFile("data/seed/bandwidth.json", "utf8"));

const runs = raw.speedTests.filter((r) => r.status === "APPROVED" && r.tokSOut > 0);
const singleStream = runs.filter(isSingleStream);
const modals = buildVramModals(runs);
const snapshotAt = raw.fetchedAt;

// --- rigs
const rigMap = new Map();
for (const run of runs) {
  const identity = rigIdentity(run.hardware, modals);
  if (!rigMap.has(identity.key)) {
    rigMap.set(identity.key, {
      key: identity.key, label: identity.label, hwClass: run.hardware.hwClass,
      memGb: identity.memGb, gpuCount: identity.gpuCount,
      bandwidthGBs: seedBandwidth(seed, identity, run.hardware.hwClass), runCount: 0,
    });
  }
  rigMap.get(identity.key).runCount += 1;
  run._rigKey = identity.key;
}

// --- models
const byHfId = new Map(rawModels.models.map((m) => [m.hfId, m]));
const modelMap = new Map();
for (const run of runs) {
  const hfId = run.model.hfId, slug = slugify(hfId);
  if (!modelMap.has(slug)) {
    const cat = byHfId.get(hfId);
    const display = cat?.displayName ?? run.model.displayName;
    modelMap.set(slug, {
      slug, hfId, displayName: display,
      family: cat?.family ?? run.model.family ?? null,
      paramsB: cat?.params ?? run.model.params ?? null,
      activeParamsB: cat?.activeParams ?? null,
      isMoE: cat?.isMoE ?? false,
      category: /coder|starcoder|codestral|code/i.test(display) ? "code" : "chat",
      runCount: 0, medianTokS: cat?.speedStats?.medianTokS != null ? round2(cat.speedStats.medianTokS) : null,
      // S24: data provenance badge — every run in the current pool comes from
      // the localmaxxing community harvest (APPROVED speedTests), so the whole
      // derived set is community_reported. When bestmodel's own signed runs
      // flow in, this becomes per-run (measured_signed) and derive mixes them.
      sourceClass: "community_reported",
      evalScore: cat?.evalScore ?? null, vramMeasuredGb: {}, maxContextTested: null,
      _vramSamples: new Map(), _tokS: [],
    });
  }
  const model = modelMap.get(slug);
  model.runCount += 1;
  model._tokS.push(run.tokSOut);
  run._modelSlug = slug;
}
for (const run of singleStream) {
  const model = modelMap.get(run._modelSlug);
  const bits = quantBits(run.engine?.quantization);
  if (run.contextLength != null) model.maxContextTested = Math.max(model.maxContextTested ?? 0, run.contextLength);
  if (bits != null && run.peakVramGb > 0) {
    if (!model._vramSamples.has(bits)) model._vramSamples.set(bits, []);
    model._vramSamples.get(bits).push(run.peakVramGb);
  }
}
for (const model of modelMap.values()) {
  for (const [bits, samples] of model._vramSamples) {
    model.vramMeasuredGb[String(bits)] = { gb: median(samples), n: samples.length };
  }
  if (model.medianTokS == null && model._tokS.length) model.medianTokS = median(model._tokS);
  delete model._vramSamples; delete model._tokS;
}

// --- pool cells (single-stream only)
const cellMap = new Map();
for (const run of singleStream) {
  const bits = quantBits(run.engine?.quantization);
  if (bits == null) continue;
  const key = `${run._rigKey}\u0000${run._modelSlug}\u0000${bits}`;
  if (!cellMap.has(key)) {
    cellMap.set(key, { rigKey: run._rigKey, modelSlug: run._modelSlug, bits,
      _out: [], _prefill: [], _ttft: [], _vram: [], _ctx: [], _engines: new Set() });
  }
  const cell = cellMap.get(key);
  cell._out.push(run.tokSOut);
  if (run.tokSPrefill > 0) cell._prefill.push(run.tokSPrefill);
  if (run.ttftMs > 0) cell._ttft.push(run.ttftMs);
  if (run.peakVramGb > 0) cell._vram.push(run.peakVramGb);
  if (run.contextLength != null) cell._ctx.push(run.contextLength);
  if (run.engine?.engineName) cell._engines.add(run.engine.engineName);
}
const cells = [...cellMap.values()].map((c) => ({
  rigKey: c.rigKey, modelSlug: c.modelSlug, bits: c.bits, n: c._out.length,
  tokSOutMedian: median(c._out), tokSPrefillMedian: median(c._prefill),
  ttftMsMedian: median(c._ttft), peakVramGbMedian: median(c._vram),
  maxContextTested: c._ctx.length ? Math.max(...c._ctx) : null,
  engines: [...c._engines].sort(),
}));

// --- deterministic ordering
const rigs = [...rigMap.values()].sort((a, b) => b.runCount - a.runCount || a.key.localeCompare(b.key));
const models = [...modelMap.values()].sort((a, b) => b.runCount - a.runCount || a.slug.localeCompare(b.slug));
cells.sort((a, b) => a.rigKey.localeCompare(b.rigKey) || a.modelSlug.localeCompare(b.modelSlug) || a.bits - b.bits);

const stats = {
  snapshotAt,
  totals: { runs: runs.length, models: models.length, rigs: rigs.length },
  topRigs: rigs.slice(0, 8).map(({ key, label, runCount }) => ({ key, label, runCount })),
  topModels: models.slice(0, 10).map(({ slug, displayName, runCount }) => ({ slug, displayName, runCount })),
};

await mkdir("data/derived", { recursive: true });
await writeFile("data/derived/hardware.json", JSON.stringify({ snapshotAt, rigs }, null, 1));
await writeFile("data/derived/models.json", JSON.stringify({ snapshotAt, models }, null, 1));
await writeFile("data/derived/pool.json", JSON.stringify({ snapshotAt, cells }, null, 1));
await writeFile("data/derived/stats.json", JSON.stringify(stats, null, 1));
console.log(`derived: ${rigs.length} rigs, ${models.length} models, ${cells.length} cells (${singleStream.length}/${runs.length} single-stream runs)`);
