// S1 — freeze a local snapshot of the localmaxxing public pool.
// Contract: CONTRATO-GLOBAL.md §3 (endpoints, envelopes, etiquette).
import { mkdir, writeFile } from "node:fs/promises";

const API_BASE = "https://www.localmaxxing.com/api";
const THROTTLE_MS = 350;
const USER_AGENT = "bestmodel-harvest/0.1";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getJson(path) {
  const url = `${API_BASE}${path}`;
  for (let attempt = 0; attempt <= 2; attempt++) {
    const res = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
    if (res.ok) return res.json();
    if (attempt === 2) {
      console.error(`FATAL: ${url} -> HTTP ${res.status} after retries`);
      process.exit(1);
    }
    console.log(`retry ${attempt + 1} for ${path} (HTTP ${res.status})`);
    await sleep(2000);
  }
}

function dedupeById(items) {
  const seen = new Map();
  for (const item of items) seen.set(item.id, item);
  return [...seen.values()];
}

async function harvestSpeedTests() {
  const limit = 100;
  let offset = 0, remoteTotal = Infinity;
  const collected = [];
  while (offset < remoteTotal) {
    const page = await getJson(`/speed-tests?limit=${limit}&offset=${offset}`);
    remoteTotal = page.total;
    collected.push(...page.speedTests);
    offset += limit;
    console.log(`speed-tests ${Math.min(offset, remoteTotal)}/${remoteTotal}`);
    await sleep(THROTTLE_MS);
  }
  const speedTests = dedupeById(collected);
  if (speedTests.length !== remoteTotal) {
    console.log(`note: remote total ${remoteTotal}, deduped ${speedTests.length} (pool moved mid-harvest)`);
  }
  return { fetchedAt: new Date().toISOString(), total: speedTests.length, remoteTotal, speedTests };
}

async function harvestModels() {
  const limit = 200;
  let offset = 0;
  const collected = [];
  while (true) {
    const page = await getJson(`/models?limit=${limit}&offset=${offset}`);
    collected.push(...page);
    offset += limit;
    console.log(`models ${collected.length}`);
    await sleep(THROTTLE_MS);
    if (page.length < limit) break;
  }
  return { fetchedAt: new Date().toISOString(), models: dedupeById(collected) };
}

async function harvestLeaderboard() {
  const limit = 200;
  let offset = 0, remoteTotal = Infinity;
  const collected = [];
  while (offset < remoteTotal) {
    const page = await getJson(`/leaderboard?limit=${limit}&offset=${offset}`);
    remoteTotal = page.total;
    collected.push(...page.rows);
    offset += limit;
    console.log(`leaderboard ${Math.min(offset, remoteTotal)}/${remoteTotal}`);
    await sleep(THROTTLE_MS);
  }
  const rows = dedupeById(collected);
  return { fetchedAt: new Date().toISOString(), total: rows.length, remoteTotal, rows };
}

await mkdir("data/raw", { recursive: true });
const speedTests = await harvestSpeedTests();
await writeFile("data/raw/speed-tests.json", JSON.stringify(speedTests));
const models = await harvestModels();
await writeFile("data/raw/models.json", JSON.stringify(models));
const leaderboard = await harvestLeaderboard();
await writeFile("data/raw/leaderboard.json", JSON.stringify(leaderboard));
console.log(`done: ${speedTests.total} runs, ${models.models.length} models, ${leaderboard.total} leaderboard rows`);
