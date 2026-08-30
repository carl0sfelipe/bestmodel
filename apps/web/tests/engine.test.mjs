import test from "node:test";
import assert from "node:assert/strict";
import {
  quantBits, usableMemGb, vramNeededGb, fitClass, estimateTokS, topPicks,
} from "../site/assets/engine.mjs";

// Fixtures (test-only, not product numbers).
const rig3090 = { key: "rtx-3090-24gb", hwClass: "DISCRETE_GPU", memGb: 24, gpuCount: 1, bandwidthGBs: 936.2 };
const rigMac = { key: "m3-ultra-512gb", hwClass: "UNIFIED", memGb: 512, gpuCount: 1, bandwidthGBs: 800 };
const rigNoBw = { key: "mystery-16gb", hwClass: "DISCRETE_GPU", memGb: 16, gpuCount: 1, bandwidthGBs: null };

const model7b = { slug: "qwen-7b", paramsB: 7, isMoE: false, vramMeasuredGb: {} };
const modelMeasured = { slug: "llama-13b", paramsB: 13, isMoE: false, vramMeasuredGb: { 4: { gb: 19, n: 5 } } };
const modelNoParams = { slug: "ghost", paramsB: null, isMoE: false, vramMeasuredGb: {} };

const cells = [
  { rigKey: "rtx-3090-24gb", modelSlug: "qwen-7b", bits: 4, n: 5, tokSOutMedian: 60 },
  { rigKey: "rtx-3090-24gb", modelSlug: "llama-13b", bits: 4, n: 1, tokSOutMedian: 34 },
  { rigKey: "m3-ultra-512gb", modelSlug: "qwen-7b", bits: 8, n: 4, tokSOutMedian: 40 },
];
const rigs = [rig3090, rigMac, rigNoBw];

test("quantBits: table + first-digit fallback", () => {
  assert.equal(quantBits("Q4_K_M"), 4);
  assert.equal(quantBits("Q8_0"), 8);
  assert.equal(quantBits("NVFP4"), 4);
  assert.equal(quantBits("fp16"), 16);
  assert.equal(quantBits("IQ3_XS"), 3);
  assert.equal(quantBits("Unsloth-Dynamic-Q4_K_M"), 4);
  assert.equal(quantBits("weird"), null);
  assert.equal(quantBits("AWQ"), 4);
  assert.equal(quantBits("Q1_0"), 1);
  assert.equal(quantBits(null), null);
});

test("usableMemGb: class fractions", () => {
  assert.equal(usableMemGb(rig3090), 24 * 0.90);
  assert.equal(usableMemGb(rigMac), 512 * 0.75);
  assert.equal(usableMemGb({ hwClass: "DISCRETE_GPU", memGb: null }), null);
});

test("vramNeededGb: measured (n>=2) beats formula; null when impossible", () => {
  assert.deepEqual(vramNeededGb(modelMeasured, 4), { gb: 19, basis: "measured" });
  const formula = vramNeededGb(model7b, 4);
  assert.equal(formula.basis, "formula");
  assert.equal(formula.gb, 0.15 * 4 * 7 + 2.0);
  const thin = { slug: "x", paramsB: 7, vramMeasuredGb: { 4: { gb: 5, n: 1 } } };
  assert.equal(vramNeededGb(thin, 4).basis, "formula"); // n=1 is not evidence enough
  assert.equal(vramNeededGb(modelNoParams, 4), null);
  assert.equal(vramNeededGb(model7b, null), null);
});

test("fitClass: monotonic in bits (formula path)", () => {
  const order = { no: 0, tight: 1, ok: 2, head: 3 };
  let prev = Infinity;
  for (const bits of [1, 2, 3, 4, 5, 6, 8, 16]) {
    const fit = order[fitClass(rig3090, model7b, bits)];
    assert.ok(fit <= prev, `bits=${bits} improved fit`);
    prev = fit;
  }
});

test("fitClass: monotonic in memGb", () => {
  const order = { no: 0, tight: 1, ok: 2, head: 3 };
  let prev = -Infinity;
  for (const memGb of [4, 8, 12, 16, 24, 48, 96]) {
    const rig = { ...rig3090, memGb };
    const fit = order[fitClass(rig, model7b, 4)];
    assert.ok(fit >= prev, `memGb=${memGb} worsened fit`);
    prev = fit;
  }
});

test("estimateTokS ladder: measured / reported / extrapolated / null", () => {
  const measured = estimateTokS(rig3090, model7b, 4, cells, rigs);
  assert.deepEqual(measured, { value: 60, basis: "measured", n: 5 });

  const reported = estimateTokS(rig3090, modelMeasured, 4, cells, rigs);
  assert.deepEqual(reported, { value: 34, basis: "reported", n: 1 });

  // No local cell for (qwen-7b, 8): scale Mac's 40 tok/s by bandwidth ratio.
  const extrapolated = estimateTokS(rig3090, model7b, 8, cells, rigs);
  assert.equal(extrapolated.basis, "extrapolated");
  assert.equal(extrapolated.value, Math.round(40 * (936.2 / 800) * 100) / 100);

  // Target rig without bandwidth: never guess.
  assert.equal(estimateTokS(rigNoBw, model7b, 8, cells, rigs), null);
  assert.equal(estimateTokS(rig3090, modelNoParams, 3, cells, rigs), null);
});

test("topPicks: slow measured outranks fast extrapolated; only ok/head fits", () => {
  const models = [model7b, modelMeasured];
  const picks = topPicks(rig3090, models, cells, rigs, 10);
  assert.ok(picks.length >= 2);
  assert.equal(picks[0].est.basis, "measured");
  assert.equal(picks[0].model.slug, "qwen-7b");
  for (const pick of picks) assert.ok(["ok", "head"].includes(pick.fit));
  // measured 60 tok/s ranks above any faster non-measured candidate
  const weights = { measured: 3, reported: 2, extrapolated: 1 };
  for (let i = 1; i < picks.length; i++) {
    assert.ok(weights[picks[i - 1].est.basis] >= weights[picks[i].est.basis]);
  }
});

test("purity: same inputs, same outputs", () => {
  const a = JSON.stringify(topPicks(rig3090, [model7b, modelMeasured], cells, rigs, 5));
  const b = JSON.stringify(topPicks(rig3090, [model7b, modelMeasured], cells, rigs, 5));
  assert.equal(a, b);
});

// S24: source-class badges — the honesty UI maps the product's run taxonomy.
test("S24 sourceText: taxonomy + honest unknown (engine, DOM-free)", async () => {
  const { sourceText } = await import("../site/assets/engine.mjs");
  assert.equal(sourceText("community_reported"), "community-reported");
  assert.equal(sourceText("measured_signed"), "measured · signed");
  assert.equal(sourceText("mock"), "mock");
  assert.equal(sourceText(undefined), "unknown source");
  assert.equal(sourceText("exotic"), "unknown source");
});
