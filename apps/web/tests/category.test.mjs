import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  modelCategory,
  modalityOf,
  isMultimodalCategory,
  MODEL_CATEGORIES,
  AUDIO_MODALITY_CATEGORIES,
  multimodalMetricOf,
} from "../scripts/category.mjs";

const here = dirname(fileURLToPath(import.meta.url));

test("music nests under the audio modality", () => {
  assert.equal(modalityOf("music"), "audio");
  assert.equal(modalityOf("audio"), "audio");
  assert.equal(modalityOf("chat"), "text");
  assert.ok(AUDIO_MODALITY_CATEGORIES.has("music"));
  assert.ok(MODEL_CATEGORIES.includes("music"));
  assert.ok(MODEL_CATEGORIES.includes("audio"));
  assert.ok(isMultimodalCategory("music"));
  assert.equal(isMultimodalCategory("chat"), false);
});

const CASES = [
  ["MusicGen Small", "facebook/musicgen-small", "music"],
  ["MAGNeT small", "facebook/magnet-small-10secs", "music"],
  ["JASCO 400M", "facebook/jasco-chords-drums-400M", "music"],
  ["ACE-Step 1.5", "ACE-Step/ACE-Step-1.5", "music"],
  ["YuE2 3B", "map/YuE2-3B", "music"],
  ["DiffRhythm full", "ASLP-lab/DiffRhythm-1.2", "music"],
  ["Stable Audio Open", "stabilityai/stable-audio-open-1.0", "music"],
  ["Whisper Large v3", "openai/whisper-large-v3", "audio"],
  ["AudioGen", "facebook/audiogen-medium", "audio"],
  ["Qwen2.5 Coder 7B", "unsloth/Qwen2.5-Coder-7B-Instruct-GGUF", "code"],
  ["Llama 3.1 8B Instruct", "unsloth/Llama-3.1-8B-Instruct-GGUF", "chat"],
];

test("modelCategory classifies music / audio / code / chat", () => {
  for (const [display, hfId, expected] of CASES) {
    assert.equal(modelCategory(display, hfId), expected, `${display} ${hfId}`);
  }
});

test("multimodalMetricOf: music uses RTF/xrealtime, never tok/s", () => {
  const music = multimodalMetricOf({
    category: "music",
    rtf: 0.5,
    peakVramGb: 1,
    n: 1,
    sourceClass: "fixture_stub",
  });
  assert.deepEqual(music, { value: 2, unit: "×real", label: "realtime" });

  const whisper = multimodalMetricOf({
    category: "audio",
    audioXReal: 4.0,
    n: 1,
    sourceClass: "fixture_stub",
  });
  assert.deepEqual(whisper, { value: 4.0, unit: "×real", label: "realtime" });

  const text = multimodalMetricOf({
    category: "chat",
    tokSOutMedian: 60,
    n: 3,
  });
  assert.equal(text, null);
});

test("fixture keeps music distinct from Whisper audio", async () => {
  const raw = JSON.parse(
    await readFile(join(here, "../../../tests/fixtures/music_audio_intent.json"), "utf8"),
  );
  assert.equal(raw.sourceClass, "fixture_stub");
  const bySlug = Object.fromEntries(raw.models.map((m) => [m.slug, m]));
  assert.equal(bySlug["whisper-large-v3"].category, "audio");
  assert.equal(bySlug["facebook-musicgen-small"].category, "music");
  assert.equal(bySlug["facebook-musicgen-small"].modality, "audio");
  const cells = Object.fromEntries(raw.cells.map((c) => [c.modelSlug, c]));
  assert.equal(cells["whisper-large-v3"].tokSOutMedian, undefined);
  assert.equal(cells["facebook-musicgen-small"].tokSOutMedian, undefined);
  assert.ok(cells["facebook-musicgen-small"].rtf != null);
});
