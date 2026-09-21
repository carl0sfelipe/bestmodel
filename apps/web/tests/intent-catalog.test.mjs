import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import test from "node:test";

import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { classifyModel, STORABLE_CATEGORIES } from "../scripts/intent-catalog.mjs";

const REAL_CATALOG = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../packages/intent-catalog/catalog.json",
);

const CASES = [
  ["MusicGen", "", "music"],
  ["MAGNeT", "", "music"],
  ["ACE-Step", "", "music"],
  ["YuE", "", "music"],
  ["DiffRhythm", "", "music"],
  ["Stable Audio", "", "music"],
  ["Whisper Large v3", "", "audio"],
  ["faster-whisper", "", "audio"],
  ["AudioGen", "", "audio"],
  ["Qwen2.5-Coder", "", "code"],
  ["Codestral", "", "code"],
  ["Llama-3-8B", "", "chat"],
];

test("real catalog classifies the canonical names and hides the fixture id", () => {
  delete process.env.BESTMODEL_INTENT_CATALOG;
  assert.equal(STORABLE_CATEGORIES().includes("zz-fixture"), false);
  assert.equal(STORABLE_CATEGORIES().includes("music"), true);
  assert.equal(STORABLE_CATEGORIES().includes("image-to-3d"), true);
  assert.equal(STORABLE_CATEGORIES().includes("vision"), false);
  for (const [display, hfId, expected] of CASES) {
    assert.equal(classifyModel(display, hfId), expected, display);
  }
});

test("BESTMODEL_INTENT_CATALOG adds a row without editing the loader", () => {
  const dir = mkdtempSync(join(tmpdir(), "intent-catalog-"));
  const previous = process.env.BESTMODEL_INTENT_CATALOG;
  try {
    const real = JSON.parse(readFileSync(REAL_CATALOG, "utf8"));
    real.intents.push({
      id: "zz-fixture",
      name: "Fixture",
      glyph: "?",
      desc: "fixture",
      modality: "video",
      storable: true,
      metric: { field: "zzPerSec", unit: "zz/s", label: "fixture", higherIsBetter: true },
      forbiddenFields: ["tokSOutMedian"],
      classify: "zz-fixture-model",
    });
    const path = join(dir, "catalog.json");
    writeFileSync(path, JSON.stringify(real));
    process.env.BESTMODEL_INTENT_CATALOG = path;
    assert.equal(STORABLE_CATEGORIES().includes("zz-fixture"), true);
    assert.equal(classifyModel("ZZ-Fixture-Model 7B", "x/y"), "zz-fixture");
  } finally {
    if (previous === undefined) delete process.env.BESTMODEL_INTENT_CATALOG;
    else process.env.BESTMODEL_INTENT_CATALOG = previous;
    rmSync(dir, { recursive: true, force: true });
  }
});
