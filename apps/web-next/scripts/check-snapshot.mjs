// check-snapshot.mjs — the front's snapshot must describe itself.
//
// The derived files that ship to the front are copied by hand, and one of
// them (stats.json) was never regenerated after the anchor rigs landed: the
// site said "8,230 runs / 686 models / 184 rigs" while the files next to it
// held 8,246 / 692 / 185. A reader comparing the home page with the
// hardware index would find the site contradicting itself.
//
// This check recomputes the totals from the files that sit next to
// stats.json and fails when they disagree. It is a check, not a generator:
// the fix is to regenerate the file, never to weaken this.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const derived = path.join(here, "..", "public", "data", "derived");

const readJson = async (name) => JSON.parse(await readFile(path.join(derived, name), "utf8"));

const hardware = await readJson("hardware.json");
const models = await readJson("models.json");
const stats = await readJson("stats.json");

const rigCount = hardware.rigs.length;
const modelCount = models.models.length;
// Every run belongs to exactly one rig, so the rigs' own counts add up to
// the number of runs in the pool.
const runCount = hardware.rigs.reduce((total, rig) => total + (rig.runCount ?? 0), 0);

const problems = [];
const check = (label, actual, expected) => {
  if (actual !== expected) problems.push(`${label}: stats.json says ${expected}, the files say ${actual}`);
};

check("runs", runCount, stats.totals.runs);
check("models", modelCount, stats.totals.models);
check("rigs", rigCount, stats.totals.rigs);

if (stats.snapshotAt !== hardware.snapshotAt) {
  problems.push(`snapshotAt: stats.json ${stats.snapshotAt} vs hardware.json ${hardware.snapshotAt}`);
}

if (problems.length) {
  console.error("snapshot check FAILED:");
  for (const problem of problems) console.error(`  - ${problem}`);
  console.error("Regenerate stats.json from the files beside it; never edit the totals by hand.");
  process.exit(1);
}

console.log(`snapshot ok: ${rigCount} rigs, ${modelCount} models, ${runCount} runs (${stats.snapshotAt})`);
