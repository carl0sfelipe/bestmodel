// S8 — generate static SEO answer pages from the derived pool.
// Deterministic: same derived inputs -> identical bytes on every run.
// Every number shown is a measured pool fact (CONTRATO §1 honesty): no
// engine estimation, no extrapolation. A page exists only for a rig x model
// pair with at least one cell of n >= 2 (a single run is too weak to answer).
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const ATTRIBUTION = "community pool data via localmaxxing.com public API";
const DOMAIN = "https://REPLACE-DOMAIN/"; // [A DEFINIR] production domain
const FONT_LINKS = `<link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Inter+Tight:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">`;

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const d1 = (x) => (x == null ? null : Math.round(x * 10) / 10);
const int = (x) => (x == null ? null : Math.round(x).toLocaleString("en-US"));
const show = (x, suffix = "") => (x == null ? "—" : `${x}${suffix}`);

const PAGE_CSS = `/* S8 static answer pages — layout only; tokens/components from theme.css. */
.page{max-width:780px;margin:0 auto;padding:0 24px 120px}
.nav-top{
  position:sticky;top:0;z-index:20;
  display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding:20px 56px;
  background:rgba(11,12,14,.85);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  border-bottom:1px solid var(--hair);
  font-family:var(--mono);font-size:13px;letter-spacing:-.01em;
}
.wordmark{color:var(--ink);display:flex;align-items:center;gap:10px}
.wordmark .prompt{color:var(--muted)}
.nav-top .links{display:flex;gap:20px;color:var(--muted);flex-wrap:wrap}
.nav-top .links a{color:inherit;text-decoration:none;transition:color .25s}
.nav-top .links a:hover{color:var(--ink)}
.hero{padding:72px 0 32px}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--amber);margin-bottom:20px}
h1{font-family:var(--display);font-weight:600;font-size:clamp(30px,4.6vw,54px);line-height:1.04;letter-spacing:-.03em;max-width:720px}
.answer{margin-top:24px;font-family:var(--display);font-weight:500;font-size:clamp(18px,2.2vw,24px);letter-spacing:-.01em}
.answer .yes{color:var(--green)}
.answer .em{color:var(--amber)}
.sub{margin-top:12px;color:var(--muted);font-size:15px;max-width:600px}
.data-table{margin-top:44px;width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--hair);border-radius:12px;overflow:hidden}
.data-table th,.data-table td{padding:14px 18px;text-align:left;font-family:var(--mono);font-size:12px}
.data-table thead th{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:500;border-bottom:1px solid var(--hair);background:var(--surface-2)}
.data-table tbody tr{border-top:1px solid var(--hair)}
.data-table tbody tr:first-child{border-top:0}
.data-table td.num{font-variant-numeric:tabular-nums;color:var(--ink)}
.journeys{margin-top:44px;display:flex;flex-direction:column;gap:12px;padding:22px;border:1px solid var(--hair);border-radius:12px;background:var(--surface)}
.j-head{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin-bottom:4px}
.journeys a{color:var(--amber);text-decoration:none;font-family:var(--mono);font-size:13px;transition:color .25s}
.journeys a:hover{color:#E9B36F}
.rig-group{margin-top:56px}
.rig-name{font-family:var(--display);font-weight:600;font-size:22px;letter-spacing:-.02em;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.rig-count{font-family:var(--mono);font-size:11px;color:var(--dim);font-weight:400}
.model-list{list-style:none;margin-top:16px;display:flex;flex-direction:column}
.model-list li{padding:10px 0;border-top:1px solid var(--hair)}
.model-list a{color:var(--ink);text-decoration:none;font-family:var(--mono);font-size:13px;transition:color .25s}
.model-list a:hover{color:var(--amber)}
@media (max-width:900px){
  .nav-top{padding:16px 20px}
  .page{padding:0 20px 80px}
  .hero{padding:48px 0 24px}
}
@media (prefers-reduced-motion:reduce){*{transition-duration:.01ms!important;animation-duration:.01ms!important}}`;

function pageHead(title, description, cssRel) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
${FONT_LINKS}
<link rel="stylesheet" href="${cssRel}/theme.css">
<style>${PAGE_CSS}</style>
</head>
<body>`;
}

function pageFoot() {
  return `<footer>
  <div>can-i-run-it</div>
  <div>${ATTRIBUTION} · snapshot ${snapshotDate}</div>
</footer>
</body>
</html>
`;
}

function renderPage(pair, rig, model) {
  const buckets = pair.buckets; // already sorted by bits asc
  const rep = [...buckets].sort((a, b) => b.n - a.n || a.bits - b.bits)[0];
  const title = `Can the ${rig.label} run ${model.displayName}?`;
  const description = `Community-verified: the ${rig.label} runs ${model.displayName} at ${show(d1(rep.tokSOutMedian))} tok/s (${rep.n} runs, ${rep.bits}-bit) on the localmaxxing pool.`;
  const rows = buckets
    .map((b) => `    <tr>
      <td>${b.bits}-bit</td>
      <td class="num">${show(d1(b.tokSOutMedian))}</td>
      <td class="num">${show(d1(b.ttftMsMedian))}</td>
      <td class="num">${show(d1(b.peakVramGbMedian), " GB")}</td>
      <td class="num">${show(int(b.maxContextTested))}</td>
      <td>${b.engines.length ? esc([...b.engines].join(", ")) : "—"}</td>
    </tr>`)
    .join("\n");
  return `${pageHead(title, description, "../../assets")}
<header class="nav-top">
  <div class="wordmark"><span class="prompt">$</span>can-i-run-it</div>
  <div class="links">
    <a href="../../index.html">I have a goal</a>
    <a href="../../hardware.html">I have hardware</a>
    <a href="../index.html">All answers</a>
  </div>
</header>
<main class="page">
  <section class="hero">
    <div class="kicker">community-verified · measured pool data</div>
    <h1>Can the ${esc(rig.label)} run ${esc(model.displayName)}?</h1>
    <p class="answer"><span class="yes">Yes</span> — community-measured at <span class="em">${show(d1(rep.tokSOutMedian))} tok/s</span> (${rep.n} runs at ${rep.bits}-bit).</p>
    <p class="sub">Verified single-stream runs on the ${esc(rig.label)} from the localmaxxing public pool. Every number on this page is measured — nothing here is estimated.</p>
  </section>
  <table class="data-table">
    <thead>
      <tr>
        <th>Quantization</th>
        <th>Median tok/s</th>
        <th>TTFT (ms)</th>
        <th>Peak VRAM</th>
        <th>Max context tested</th>
        <th>Engines</th>
      </tr>
    </thead>
    <tbody>
${rows}
    </tbody>
  </table>
  <div class="journeys">
    <div class="j-head">Go deeper</div>
    <a href="../../index.html">I have a goal — find models that fit my use case →</a>
    <a href="../../hardware.html">I have hardware — browse everything my rig can run →</a>
    <a href="../index.html">All machine × model answer pages →</a>
  </div>
</main>
${pageFoot()}`;
}

function renderIndex(pairs, rigByKey, modelBySlug) {
  const groups = new Map();
  for (const pair of pairs) {
    if (!groups.has(pair.rigKey)) groups.set(pair.rigKey, { rigKey: pair.rigKey, pairs: [], totalRuns: 0 });
    const g = groups.get(pair.rigKey);
    g.pairs.push(pair);
    g.totalRuns += pair.buckets.reduce((s, b) => s + b.n, 0);
  }
  const ordered = [...groups.values()].sort((a, b) => b.totalRuns - a.totalRuns || a.rigKey.localeCompare(b.rigKey));
  const sections = ordered
    .map((g) => {
      const label = rigByKey.get(g.rigKey)?.label ?? g.rigKey;
      const items = g.pairs
        .map((p) => `      <li><a href="./${esc(p.rigKey)}/${esc(p.modelSlug)}.html">${esc(modelBySlug.get(p.modelSlug)?.displayName ?? p.modelSlug)}</a></li>`)
        .join("\n");
      return `  <section class="rig-group">
    <h2 class="rig-name">${esc(label)}<span class="rig-count">${g.totalRuns.toLocaleString("en-US")} verified runs</span></h2>
    <ul class="model-list">
${items}
    </ul>
  </section>`;
    })
    .join("\n\n");
  const title = `Every machine × model answer, from real runs`;
  const description = `Community-verified answers: can a given machine run a given model, and how fast? Measured single-stream runs from the localmaxxing public pool.`;
  return `${pageHead(title, description, "../assets")}
<header class="nav-top">
  <div class="wordmark"><span class="prompt">$</span>can-i-run-it</div>
  <div class="links">
    <a href="../index.html">I have a goal</a>
    <a href="../hardware.html">I have hardware</a>
  </div>
</header>
<main class="page">
  <section class="hero">
    <div class="kicker">answer pages · ${pairs.length} combinations</div>
    <h1>Every machine × model answer, from real runs.</h1>
    <p class="sub">One page per rig × model pair, aggregated from verified community runs with n ≥ 2. Grouped by machine below.</p>
  </section>
${sections}
  <div class="journeys">
    <div class="j-head">Go deeper</div>
    <a href="../index.html">I have a goal — find models that fit my use case →</a>
    <a href="../hardware.html">I have hardware — browse everything my rig can run →</a>
  </div>
</main>
${pageFoot()}`;
}

function renderSitemap(pairs) {
  const locs = [`  <url><loc>${DOMAIN}p/index.html</loc></url>`];
  for (const p of pairs) locs.push(`  <url><loc>${DOMAIN}p/${esc(p.rigKey)}/${esc(p.modelSlug)}.html</loc></url>`);
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${locs.join("\n")}
</urlset>
`;
}

const readJson = async (file) => JSON.parse(await readFile(file, "utf8"));

const pool = await readJson("data/derived/pool.json");
const { models } = await readJson("data/derived/models.json");
const { rigs } = await readJson("data/derived/hardware.json");
const snapshotDate = String(pool.snapshotAt).slice(0, 10);

const rigByKey = new Map(rigs.map((r) => [r.key, r]));
const modelBySlug = new Map(models.map((m) => [m.slug, m]));

const byPair = new Map();
for (const cell of pool.cells) {
  if (cell.n < 2) continue;
  const key = `${cell.rigKey}\u0000${cell.modelSlug}`;
  if (!byPair.has(key)) byPair.set(key, { rigKey: cell.rigKey, modelSlug: cell.modelSlug, buckets: [] });
  byPair.get(key).buckets.push(cell);
}
const pairs = [...byPair.values()]
  .map((p) => ({ ...p, buckets: [...p.buckets].sort((a, b) => a.bits - b.bits) }))
  .sort((a, b) => a.rigKey.localeCompare(b.rigKey) || a.modelSlug.localeCompare(b.modelSlug));

await rm("site/p", { recursive: true, force: true });
await mkdir("site/p", { recursive: true });

for (const pair of pairs) {
  const rig = rigByKey.get(pair.rigKey);
  const model = modelBySlug.get(pair.modelSlug);
  if (!rig || !model) throw new Error(`pair missing rig/model: ${pair.rigKey}/${pair.modelSlug}`);
  const dir = path.join("site/p", pair.rigKey);
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, `${pair.modelSlug}.html`), renderPage(pair, rig, model), "utf8");
}

await writeFile("site/p/index.html", renderIndex(pairs, rigByKey, modelBySlug), "utf8");
await writeFile("site/sitemap.xml", renderSitemap(pairs), "utf8");
console.log(`seo: ${pairs.length} pages + site/p/index.html + site/sitemap.xml`);
