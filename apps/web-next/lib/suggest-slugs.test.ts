import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import { exactSuffixMatches, suggestRigs, suggestSlugs } from "./suggest-slugs.ts";

const models = (
  JSON.parse(
    readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../public/data/derived/models.json"), "utf8"),
  ) as { models: { slug: string }[] }
).models;
const slugs = models.map((model) => model.slug);

describe("suggestSlugs", () => {
  test("gemma-4-12b-it -> google-gemma-4-12b-it", () => {
    const query = "gemma-4-12b-it";
    const suggestions = suggestSlugs(query, slugs);
    assert.equal(suggestions.length, 5);
    assert.equal(suggestions[0], "google-gemma-4-12b-it");
    assert.deepEqual(exactSuffixMatches(query, slugs), ["google-gemma-4-12b-it"]);
  });

  test("qwen3-8-27b -> qwen-qwen3-8-27b", () => {
    const query = "qwen3-8-27b";
    const suggestions = suggestSlugs(query, slugs);
    assert.equal(suggestions.length, 5);
    assert.equal(suggestions[0], "qwen-qwen3-8-27b");
    assert.deepEqual(exactSuffixMatches(query, slugs), ["qwen-qwen3-8-27b"]);
  });
});

describe("suggestRigs", () => {
  const rigKeys = ["pro-64gb", "h100-80gb", "h200-sxm-141gb", "rtx-3090-24gb", "rtx-3090-24gb-x2"];

  test("a100-80gb -> h100-80gb (same memory, single GPU)", () => {
    assert.equal(suggestRigs("a100-80gb", rigKeys)[0], "h100-80gb");
  });

  test("rtx-3090-24gb-x4 ranks rtx-3090-24gb-x2 above pro-64gb", () => {
    const ranked = suggestRigs("rtx-3090-24gb-x4", [...rigKeys, "rtx-3090-24gb-x4b"]);
    assert.ok(ranked.includes("rtx-3090-24gb-x2"));
    assert.ok(ranked.includes("pro-64gb"));
    assert.ok(ranked.indexOf("rtx-3090-24gb-x2") < ranked.indexOf("pro-64gb"));
  });
});
