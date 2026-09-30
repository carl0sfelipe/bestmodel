import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import { filterWallRows, unknownRig } from "./wall-filter.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

type Model = {
  slug: string;
  category: string;
  paramsB: number | null;
  displayName?: string | null;
  hfId?: string | null;
};

function loadRows() {
  const models = (JSON.parse(readFileSync(join(root, "public/data/derived/models.json"), "utf8")) as { models: Model[] }).models;
  const pool = (JSON.parse(readFileSync(join(root, "public/data/derived/pool.json"), "utf8")) as { cells: { modelSlug: string; rigKey: string }[] }).cells;
  const hardware = (JSON.parse(readFileSync(join(root, "public/data/derived/hardware.json"), "utf8")) as { rigs: { key: string }[] }).rigs;
  const byModel = new Map(models.map((model) => [model.slug, model]));
  const rows = pool.flatMap((cell) => {
    const model = byModel.get(cell.modelSlug);
    return model ? [{ cell, model }] : [];
  });
  return { rows, hardwareKeys: hardware.map((rig) => rig.key) };
}

describe("filterWallRows", () => {
  test("3090 does not return tinystories", () => {
    const { rows } = loadRows();
    const filtered = filterWallRows(rows, { rig: "rtx-3090-24gb" });
    assert.ok(filtered.length > 0);
    assert.ok(filtered.every((row) => row.cell.rigKey === "rtx-3090-24gb"));
    assert.ok(filtered.every((row) => !/tinystories|tiny-stories/i.test(`${row.model.slug} ${row.model.displayName} ${row.model.hfId}`)));
  });

  test("unknown rig is a miss with 10 similar slugs", () => {
    const { hardwareKeys } = loadRows();
    const missing = unknownRig("rtx-3090-99tb", hardwareKeys);
    assert.ok(missing);
    assert.equal(missing.queried, "rtx-3090-99tb");
    assert.equal(missing.similar.length, 10);
    assert.ok(missing.similar.every((key) => hardwareKeys.includes(key)));
    assert.ok(missing.similar.some((key) => key.includes("3090")));
    assert.equal(unknownRig("rtx-3090-24gb", hardwareKeys), null);
  });
});
