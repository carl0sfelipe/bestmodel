import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const publicLlms = join(here, "..", "public", "llms.txt");
const siteLlms = join(here, "..", "..", "web", "site", "llms.txt");
const statsPath = join(here, "..", "..", "web", "data", "derived", "stats.json");

function parseSnapshotSection(content: string): { date: string; runs: string; models: string; rigs: string } {
  const headingMatch = content.match(
    /^## Snapshot totals \(apps\/web\/data\/derived\/stats\.json, (\d{4}-\d{2}-\d{2})\)\s*$/m,
  );
  assert.ok(headingMatch, "Snapshot totals heading not found");
  const date = headingMatch[1]!;

  const runsMatch = content.match(/^-\s*runs:\s*(\d+)\s*$/m);
  const modelsMatch = content.match(/^-\s*models:\s*(\d+)\s*$/m);
  const rigsMatch = content.match(/^-\s*rigs:\s*(\d+)\s*$/m);
  assert.ok(runsMatch, "runs line not found");
  assert.ok(modelsMatch, "models line not found");
  assert.ok(rigsMatch, "rigs line not found");

  return { date, runs: runsMatch[1]!, models: modelsMatch[1]!, rigs: rigsMatch[1]! };
}

describe("llms.txt snapshot totals", () => {
  const stats = JSON.parse(readFileSync(statsPath, "utf-8")) as {
    snapshotAt: string;
    totals: { runs: number; models: number; rigs: number };
  };
  const expectedDate = stats.snapshotAt.slice(0, 10);
  const expected = {
    runs: String(stats.totals.runs),
    models: String(stats.totals.models),
    rigs: String(stats.totals.rigs),
  };

  it("public/llms.txt matches stats.json", () => {
    const content = readFileSync(publicLlms, "utf-8");
    const parsed = parseSnapshotSection(content);
    assert.equal(parsed.date, expectedDate, `date mismatch: got ${parsed.date}, want ${expectedDate}`);
    assert.equal(parsed.runs, expected.runs, `runs mismatch: got ${parsed.runs}, want ${expected.runs}`);
    assert.equal(parsed.models, expected.models, `models mismatch: got ${parsed.models}, want ${expected.models}`);
    assert.equal(parsed.rigs, expected.rigs, `rigs mismatch: got ${parsed.rigs}, want ${expected.rigs}`);
  });

  it("site/llms.txt matches public/llms.txt", () => {
    const publicContent = readFileSync(publicLlms, "utf-8");
    const siteContent = readFileSync(siteLlms, "utf-8");
    const pub = parseSnapshotSection(publicContent);
    const site = parseSnapshotSection(siteContent);
    assert.equal(site.date, pub.date, "site date differs from public");
    assert.equal(site.runs, pub.runs, "site runs differs from public");
    assert.equal(site.models, pub.models, "site models differs from public");
    assert.equal(site.rigs, pub.rigs, "site rigs differs from public");
  });
});
