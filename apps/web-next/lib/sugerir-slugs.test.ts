import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import { exactSuffixMatches, sugerirSlugs } from "./sugerir-slugs.ts";

const models = (
  JSON.parse(
    readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../public/data/derived/models.json"), "utf8"),
  ) as { models: { slug: string }[] }
).models;
const slugs = models.map((model) => model.slug);

describe("sugerirSlugs", () => {
  test("gemma-4-12b-it → google-gemma-4-12b-it", () => {
    const query = "gemma-4-12b-it";
    const suggestions = sugerirSlugs(query, slugs);
    assert.equal(suggestions.length, 5);
    assert.equal(suggestions[0], "google-gemma-4-12b-it");
    assert.deepEqual(exactSuffixMatches(query, slugs), ["google-gemma-4-12b-it"]);
  });

  test("qwen3-8-27b → qwen-qwen3-8-27b", () => {
    const query = "qwen3-8-27b";
    const suggestions = sugerirSlugs(query, slugs);
    assert.equal(suggestions.length, 5);
    assert.equal(suggestions[0], "qwen-qwen3-8-27b");
    assert.deepEqual(exactSuffixMatches(query, slugs), ["qwen-qwen3-8-27b"]);
  });
});
