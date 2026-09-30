import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { FEATURES_EM_BREVE, featureEmBreve } from "./em-breve.ts";

const KNOWN = ["comparar-duas-gpus", "melhor-modelo-por-tarefa", "rodar-na-nuvem"] as const;

describe("featureEmBreve", () => {
  it("knows the three initial slugs", () => {
    for (const slug of KNOWN) {
      const entry = featureEmBreve(slug);
      assert.ok(entry, `expected an entry for ${slug}`);
      assert.equal(entry.slug, slug);
      assert.ok(entry.titulo.length > 0);
      assert.ok(entry.oQueFaz.length > 0);
    }
    assert.equal(FEATURES_EM_BREVE.length, 3);
  });

  it("returns null for an unknown slug", () => {
    assert.equal(featureEmBreve("nao-existe"), null);
    assert.equal(featureEmBreve(""), null);
  });

  it("each entry has at least three ways to help", () => {
    for (const entry of FEATURES_EM_BREVE) {
      assert.ok(
        entry.comoAjudar.length >= 3,
        `${entry.slug} has ${entry.comoAjudar.length} help items, need ≥ 3`,
      );
    }
  });
});
