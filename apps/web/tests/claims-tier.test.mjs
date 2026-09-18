import test from "node:test";
import assert from "node:assert/strict";
import { claimFor, estimateTokS } from "../site/assets/engine.mjs";

// Fixtures (test-only, not product numbers).
const rig3090 = { key: "rtx-3090-24gb", hwClass: "DISCRETE_GPU", memGb: 24, gpuCount: 1, bandwidthGBs: 936.2 };
const rigMac = { key: "m3-ultra-512gb", hwClass: "UNIFIED", memGb: 512, gpuCount: 1, bandwidthGBs: 800 };
const rigNoBw = { key: "mystery-16gb", hwClass: "DISCRETE_GPU", memGb: 16, gpuCount: 1, bandwidthGBs: null };

const model = { slug: "qwen-7b", paramsB: 7, isMoE: false, vramMeasuredGb: {} };
const modelGhost = { slug: "ghost", paramsB: null, isMoE: false, vramMeasuredGb: {} };

const cells = [
  { rigKey: "rtx-3090-24gb", modelSlug: "qwen-7b", bits: 4, n: 5, tokSOutMedian: 60 },
  { rigKey: "a100-40gb", modelSlug: "qwen-7b", bits: 4, n: 2, tokSOutMedian: 45 },
  { rigKey: "m3-ultra-512gb", modelSlug: "qwen-7b", bits: 8, n: 4, tokSOutMedian: 40 },
];

test("claimFor: never the rig itself, strongest first, same bits preferred", () => {
  // On the Mac at 8-bit: the Mac's OWN 8-bit cell is excluded (it is this
  // rig's number, not a claim), so the strongest claim is the 3090's
  // 4-bit cell (n=5) — carried with ITS bits, labeled in the UI.
  const onMac = claimFor(rigMac, model, 8, cells);
  assert.equal(onMac.rigKey, "rtx-3090-24gb");
  assert.equal(onMac.bits, 4);
  assert.equal(onMac.value, 60);
  assert.equal(onMac.n, 5);
  assert.equal(onMac.basis, "claim");

  // On the 3090 at 4-bit the 3090's OWN cell is excluded; the remaining
  // 4-bit claim (a100, n=2) wins over the 8-bit one with n=4.
  const on3090 = claimFor(rig3090, model, 4, cells);
  assert.equal(on3090.rigKey, "a100-40gb");
  assert.equal(on3090.value, 45);
  assert.equal(on3090.n, 2);

  // On a rig with no bandwidth (no extrapolation possible) the claim is
  // still available — that is the whole point of the tier.
  const onMystery = claimFor(rigNoBw, model, 4, cells);
  assert.equal(onMystery.rigKey, "rtx-3090-24gb");
  assert.equal(onMystery.value, 60);
});

test("claimFor: falls back to other bits when same bits have no claims", () => {
  const only8 = [{ rigKey: "m3-ultra-512gb", modelSlug: "qwen-7b", bits: 8, n: 1, tokSOutMedian: 33 }];
  const claim = claimFor(rig3090, model, 4, only8);
  assert.equal(claim.bits, 8);
  assert.equal(claim.value, 33);
});

test("claimFor: null when the model has no cells anywhere (nothing to claim)", () => {
  assert.equal(claimFor(rig3090, modelGhost, 4, cells), null);
  assert.equal(claimFor(rig3090, model, 4, []), null);
});

test("claimFor: deterministic ties and null-median cells are skipped", () => {
  const tied = [
    { rigKey: "b-rig", modelSlug: "qwen-7b", bits: 4, n: 1, tokSOutMedian: 50 },
    { rigKey: "a-rig", modelSlug: "qwen-7b", bits: 4, n: 1, tokSOutMedian: 50 },
    { rigKey: "c-rig", modelSlug: "qwen-7b", bits: 4, n: 9, tokSOutMedian: null },
  ];
  const claim = claimFor(rig3090, model, 4, tied);
  assert.equal(claim.rigKey, "a-rig"); // alphabetical tie-break, null median skipped
});

test("claims tier complements (never replaces) the basis ladder", () => {
  // Where an estimate exists, the page shows the estimate; the claim tier
  // is only for the empty combos. Sanity: the Mac HAS its own 8-bit cell,
  // so at 8-bit the page shows measured, not a claim.
  const est = estimateTokS(rigMac, model, 8, cells, [rig3090, rigMac]);
  assert.equal(est.basis, "measured");
});
