// Single oracle runner: node scripts/check.mjs <target>
// Each session adds its target and appends it to DELIVERED (contract §8).
import { readFile } from "node:fs/promises";

const DELIVERED = ["raw", "derived", "engine", "uikit", "page:hardware", "page:goal", "page:mobile", "seo"];

const ATTRIBUTION = "community pool data via localmaxxing.com public API";

const fail = (msg) => { console.error(`CHECK FAIL: ${msg}`); process.exit(1); };
const ok = (msg) => console.log(`ok: ${msg}`);

async function loadJson(path) {
  try { return JSON.parse(await readFile(path, "utf8")); }
  catch (err) { fail(`${path}: ${err.message}`); }
}

function requireKeys(obj, keys, where) {
  for (const key of keys) {
    const parts = key.split(".");
    let cur = obj;
    for (const part of parts) {
      if (cur === null || cur === undefined || !(part in cur)) fail(`${where}: missing key "${key}"`);
      cur = cur[part];
    }
  }
}

async function checkRaw() {
  const st = await loadJson("data/raw/speed-tests.json");
  if (st.speedTests.length < 4500) fail(`speedTests ${st.speedTests.length} < 4500`);
  if (st.speedTests.length !== st.total) fail(`speedTests length ${st.speedTests.length} !== total ${st.total}`);
  requireKeys(st.speedTests[0], ["model.hfId", "hardware.hwClass", "engine.quantization", "tokSOut", "status"], "speed-tests[0]");
  const nonApproved = st.speedTests.filter((r) => r.status !== "APPROVED").length;
  ok(`speed-tests: ${st.total} runs (${nonApproved} non-APPROVED)`);

  const m = await loadJson("data/raw/models.json");
  if (m.models.length < 600) fail(`models ${m.models.length} < 600`);
  requireKeys(m.models[0], ["hfId", "displayName", "isMoE", "_count.benchmarkRuns"], "models[0]");
  ok(`models: ${m.models.length}`);

  const lb = await loadJson("data/raw/leaderboard.json");
  if (!Array.isArray(lb.rows) || lb.rows.length === 0) fail("leaderboard rows empty");
  ok(`leaderboard: ${lb.total} rows`);
}

async function checkDerived() {
  const text = {};
  const parsed = {};
  for (const name of ["hardware", "models", "pool", "stats"]) {
    text[name] = await readFile(`data/derived/${name}.json`, "utf8").catch((e) => fail(`${name}.json: ${e.message}`));
    if (/\bNaN\b|\bInfinity\b/.test(text[name])) fail(`${name}.json contains NaN/Infinity`);
    parsed[name] = JSON.parse(text[name]);
  }
  const { rigs } = parsed.hardware;
  const { models } = parsed.models;
  const { cells } = parsed.pool;
  const stats = parsed.stats;

  requireKeys(rigs[0], ["key", "label", "hwClass", "memGb", "gpuCount", "bandwidthGBs", "runCount"], "rigs[0]");
  requireKeys(models[0], ["slug", "hfId", "displayName", "paramsB", "isMoE", "category", "runCount", "medianTokS", "vramMeasuredGb"], "models[0]");
  requireKeys(cells[0], ["rigKey", "modelSlug", "bits", "n", "tokSOutMedian", "engines"], "cells[0]");

  const seed = JSON.parse(await readFile("data/seed/bandwidth.json", "utf8"));
  const allowed = new Set(Object.values(seed));
  for (const rig of rigs) {
    if (rig.bandwidthGBs !== null && !allowed.has(rig.bandwidthGBs)) fail(`rig ${rig.key}: bandwidth ${rig.bandwidthGBs} not in seed`);
  }
  if (cells.length < 500) fail(`cells ${cells.length} < 500`);
  const rigKeys = new Set(rigs.map((r) => r.key));
  const modelSlugs = new Set(models.map((m) => m.slug));
  for (const cell of cells) {
    if (!rigKeys.has(cell.rigKey)) fail(`cell points to unknown rig ${cell.rigKey}`);
    if (!modelSlugs.has(cell.modelSlug)) fail(`cell points to unknown model ${cell.modelSlug}`);
  }
  if (stats.totals.runs < 4500) fail(`stats.totals.runs ${stats.totals.runs} < 4500`);
  ok(`derived: ${rigs.length} rigs, ${models.length} models, ${cells.length} cells, ${stats.totals.runs} runs`);
}

async function checkEngine() {
  const { spawnSync } = await import("node:child_process");
  const { readdir } = await import("node:fs/promises");
  const testFiles = (await readdir("tests")).filter((f) => f.endsWith(".test.mjs")).map((f) => `tests/${f}`);
  const result = spawnSync("node", ["--test", ...testFiles], { stdio: "inherit" });
  if (result.status !== 0) fail("node --test failed");

  // Integration smoke: the top rig must yield at least one measured pick,
  // otherwise rigKey identity is broken between S2 and S3. Do not weaken.
  const { topPicks } = await import("../site/assets/engine.mjs");
  const { rigs } = await loadJson("data/derived/hardware.json");
  const { models } = await loadJson("data/derived/models.json");
  const { cells } = await loadJson("data/derived/pool.json");
  const topRig = rigs[0]; // sorted by runCount desc in S2
  const picks = topPicks(topRig, models, cells, rigs, 10);
  const measured = picks.filter((p) => p.est.basis === "measured");
  if (!measured.length) fail(`no measured pick for top rig ${topRig.key}`);
  ok(`engine: tests green; top rig ${topRig.key} -> ${picks.length} picks, ${measured.length} measured (best: ${measured[0].model.displayName} @ ${measured[0].est.value} tok/s)`);
}

async function checkUikit() {
  const { stat } = await import("node:fs/promises");
  const files = ["site/assets/theme.css", "site/assets/ui.mjs", "site/assets/load-data.mjs"];
  for (const f of files) {
    const st = await stat(f).catch(() => null);
    if (!st?.isFile()) fail(`missing ${f}`);
  }
  const css = await readFile("site/assets/theme.css", "utf8");
  if (!css.includes("--amber:#E0A458")) fail("theme.css missing token --amber:#E0A458");
  if (!css.includes("--bg:#0B0C0E")) fail("theme.css missing token --bg:#0B0C0E");
  const { spawnSync } = await import("node:child_process");
  for (const f of ["site/assets/ui.mjs", "site/assets/load-data.mjs"]) {
    const r = spawnSync("node", ["--check", f], { stdio: "pipe" });
    if (r.status !== 0) fail(`${f}: ${r.stderr}`);
  }
  const ui = await import("../site/assets/ui.mjs");
  for (const name of ["el", "fmt", "basisBadge", "fitLabel", "copyButton", "attributionFooter"]) {
    if (typeof ui[name] !== "function") fail(`ui.mjs missing export "${name}"`);
  }
  ok("uikit: 3 files present, tokens found, ui.mjs/load-data.mjs parse, 6 exports");
}

async function checkPageHardware() {
  const { stat, readFile } = await import("node:fs/promises");
  const file = "site/hardware.html";
  const st = await stat(file).catch(() => null);
  if (!st?.isFile()) fail(`missing ${file}`);
  const html = await readFile(file, "utf8");

  const ids = ["rigSelect", "specCard", "pillars", "catalogGrid", "tdName", "topList", "statRow"];
  for (const id of ids) {
    if (!html.includes(`id="${id}"`)) fail(`hardware.html missing id="${id}"`);
  }

  for (const bad of ["const MODELS", "14,320", "2,400+"]) {
    if (html.includes(bad)) fail(`hardware.html contains forbidden "${bad}"`);
  }

  const assets = [...html.matchAll(/(?:href|src)="\.\/assets\/([^"]+)"/g)].map((m) => m[1]);
  if (!assets.length) fail("hardware.html references no ./assets files");
  for (const a of assets) {
    const s = await stat(`site/assets/${a}`).catch(() => null);
    if (!s?.isFile()) fail(`referenced asset missing: site/assets/${a}`);
  }

  // The page's logic module must really import the engine + shared loader
  // (no stubs / declare-const workarounds). The HTML only references
  // hardware-page.mjs; the imports live there.
  const mod = "site/assets/hardware-page.mjs";
  const ms = await stat(mod).catch(() => null);
  if (!ms?.isFile()) fail(`missing ${mod}`);
  const src = await readFile(mod, "utf8");
  const { spawnSync } = await import("node:child_process");
  const r = spawnSync("node", ["--check", mod], { stdio: "pipe" });
  if (r.status !== 0) fail(`${mod}: ${r.stderr}`);
  if (!src.includes('from "./engine.mjs"')) fail(`${mod} does not import engine.mjs`);
  if (!src.includes('from "./load-data.mjs"')) fail(`${mod} does not import load-data.mjs`);
  if (!src.includes('from "./ui.mjs"')) fail(`${mod} does not import ui.mjs`);

  ok(`page:hardware: ${file} present, ${ids.length} ids, engine/load-data imported, ${assets.length} assets on disk, no mock claims`);
}

async function checkPageGoal() {
  const { stat, readFile } = await import("node:fs/promises");
  const file = "site/index.html";
  const st = await stat(file).catch(() => null);
  if (!st?.isFile()) fail(`missing ${file}`);
  const html = await readFile(file, "utf8");

  const ids = ["univTotal", "univMatch", "specNodes", "quantSeg", "recGrid", "modelSearch"];
  for (const id of ids) {
    if (!html.includes(`id="${id}"`)) fail(`index.html missing id="${id}"`);
  }

  for (const bad of ["const MODELS", "1,247"]) {
    if (html.includes(bad)) fail(`index.html contains forbidden "${bad}"`);
  }

  const assets = [...html.matchAll(/(?:href|src)="\.\/assets\/([^"]+)"/g)].map((m) => m[1]);
  if (!assets.length) fail("index.html references no ./assets files");
  for (const a of assets) {
    const s = await stat(`site/assets/${a}`).catch(() => null);
    if (!s?.isFile()) fail(`referenced asset missing: site/assets/${a}`);
  }

  // The page's logic module must really import the engine + shared loader
  // (no stubs / declare-const workarounds). The HTML only references
  // goal-page.mjs; the imports live there.
  const mod = "site/assets/goal-page.mjs";
  const ms = await stat(mod).catch(() => null);
  if (!ms?.isFile()) fail(`missing ${mod}`);
  const src = await readFile(mod, "utf8");
  const { spawnSync } = await import("node:child_process");
  const r = spawnSync("node", ["--check", mod], { stdio: "pipe" });
  if (r.status !== 0) fail(`${mod}: ${r.stderr}`);
  if (!src.includes('from "./engine.mjs"')) fail(`${mod} does not import engine.mjs`);
  if (!src.includes('from "./load-data.mjs"')) fail(`${mod} does not import load-data.mjs`);
  if (!src.includes('from "./ui.mjs"')) fail(`${mod} does not import ui.mjs`);

  ok(`page:goal: ${file} present, ${ids.length} ids, engine/load-data imported, ${assets.length} assets on disk, no mock claims`);
}

async function checkPageMobile() {
  const { stat, readFile } = await import("node:fs/promises");
  const file = "site/m/index.html";
  const st = await stat(file).catch(() => null);
  if (!st?.isFile()) fail(`missing ${file}`);
  const html = await readFile(file, "utf8");

  const ids = ["main", "sheet", "bottomStatus", "mainCta"];
  for (const id of ids) {
    if (!html.includes(`id="${id}"`)) fail(`m/index.html missing id="${id}"`);
  }

  for (const bad of ["const MODELS", "14,320", "2,400+", "1,247"]) {
    if (html.includes(bad)) fail(`m/index.html contains forbidden "${bad}"`);
  }

  const assets = [...html.matchAll(/(?:href|src)="\.\.\/assets\/([^"]+)"/g)].map((m) => m[1]);
  if (!assets.length) fail("m/index.html references no ../assets files");
  for (const a of assets) {
    const s = await stat(`site/assets/${a}`).catch(() => null);
    if (!s?.isFile()) fail(`referenced asset missing: site/assets/${a}`);
  }

  // The page's logic module must really import the engine + shared loader
  // (no stubs / declare-const workarounds). The HTML only references
  // mobile-page.mjs; the imports live there.
  const mod = "site/assets/mobile-page.mjs";
  const ms = await stat(mod).catch(() => null);
  if (!ms?.isFile()) fail(`missing ${mod}`);
  const src = await readFile(mod, "utf8");
  const { spawnSync } = await import("node:child_process");
  const r = spawnSync("node", ["--check", mod], { stdio: "pipe" });
  if (r.status !== 0) fail(`${mod}: ${r.stderr}`);
  if (!src.includes('from "./engine.mjs"')) fail(`${mod} does not import engine.mjs`);
  if (!src.includes('from "./load-data.mjs"')) fail(`${mod} does not import load-data.mjs`);
  if (!src.includes('from "./ui.mjs"')) fail(`${mod} does not import ui.mjs`);

  ok(`page:mobile: ${file} present, ${ids.length} ids, engine/load-data imported, ${assets.length} assets on disk, no mock claims`);
}

async function checkSeo() {
  const { readdir, stat } = await import("node:fs/promises");
  const pRoot = "site/p";
  const st = await stat(pRoot).catch(() => null);
  if (!st?.isDirectory()) fail(`missing ${pRoot}`);
  const entries = await readdir(pRoot, { withFileTypes: true });
  const pages = [];
  for (const dir of entries.filter((e) => e.isDirectory()).sort((a, b) => a.name.localeCompare(b.name))) {
    const files = (await readdir(`${pRoot}/${dir.name}`)).filter((f) => f.endsWith(".html")).sort();
    for (const f of files) pages.push(`${dir.name}/${f}`);
  }
  if (pages.length < 50) fail(`seo pages ${pages.length} < 50`);

  const sitemap = await readFile("site/sitemap.xml", "utf8").catch((e) => fail(`sitemap.xml: ${e.message}`));
  if (!sitemap.startsWith("<?xml")) fail("sitemap.xml does not start with <?xml");
  const locs = (sitemap.match(/<loc>/g) ?? []).length;
  if (locs !== pages.length + 1) fail(`sitemap <loc> ${locs} !== pages(${pages.length}) + index(1)`);

  const samples = [pages[0], pages[Math.floor(pages.length / 2)], pages[pages.length - 1]];
  for (const rel of samples) {
    const html = await readFile(`${pRoot}/${rel}`, "utf8").catch((e) => fail(`${rel}: ${e.message}`));
    if (!html.includes(ATTRIBUTION)) fail(`${rel}: missing ATTRIBUTION`);
    if (/\bundefined\b|\bNaN\b/.test(html)) fail(`${rel}: contains undefined/NaN`);
  }

  const { cells } = await loadJson("data/derived/pool.json");
  const solid = new Set(cells.filter((c) => c.n >= 2).map((c) => `${c.rigKey}/${c.modelSlug}`));
  for (const rel of pages) {
    const pairKey = rel.replace(/\.html$/, "");
    if (!solid.has(pairKey)) fail(`page ${rel} has no cell with n >= 2`);
  }

  ok(`seo: ${pages.length} pages, sitemap ${locs} locs, samples clean, all pages backed by n>=2 cells`);
}

const TARGETS = {
  raw: checkRaw, derived: checkDerived, engine: checkEngine, uikit: checkUikit,
  "page:hardware": checkPageHardware, "page:goal": checkPageGoal,
  "page:mobile": checkPageMobile, seo: checkSeo,
};

async function run(target) {
  if (target === "all") {
    for (const t of DELIVERED) { console.log(`== ${t} ==`); await TARGETS[t](); }
    return;
  }
  if (!TARGETS[target]) fail(`unknown target "${target}" (valid: ${Object.keys(TARGETS).join(", ")}, all)`);
  await TARGETS[target]();
}

await run(process.argv[2] ?? "all");
console.log("CHECK GREEN");
