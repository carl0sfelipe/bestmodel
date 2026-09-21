// Pool category (user intent) taxonomy. Keep in lockstep with
// apps/pool-backend/src/category.py — tests assert the same names classify
// the same way on both sides.
//
// category is the user intent. Physical modality is derived:
//   chat, code  → text
//   image       → image
//   audio       → audio   (STT / TTS / SFX; e.g. Whisper, AudioGen)
//   music       → audio   (text-to-music / song gen; same waveform domain)
//   video       → video
//
// music is not a third LLM intent beside chat/code. It is the generation
// intent of the audio modality. Multimodal cells use RTF / ×realtime /
// wall / peak VRAM / durationS — never decode_tok_s.

export const MODEL_CATEGORIES = Object.freeze([
  "chat", "code", "image", "audio", "music", "video",
]);

export const TEXT_CATEGORIES = Object.freeze(new Set(["chat", "code"]));
export const AUDIO_MODALITY_CATEGORIES = Object.freeze(new Set(["audio", "music"]));
export const MULTIMODAL_CATEGORIES = Object.freeze(new Set(["image", "audio", "music", "video"]));

export const INTENT_MODALITY = Object.freeze({
  chat: "text",
  code: "text",
  image: "image",
  audio: "audio",
  music: "audio",
  video: "video",
});

const MUSIC_RE = /musicgen|jasco|ace-?step|acestep|diffrhythm|stable[\s_-]?audio|\bmagnet\b|magnet-|yue2|\byue\b|text-to-music|text2music/i;
const AUDIO_RE = /whisper|wav2vec|audiogen|faster-whisper|distil-whisper|speech[\s_-]?to[\s_-]?text|\bstt\b|\btts\b/i;
const CODE_RE = /coder|starcoder|codestral|code/i;

export function modalityOf(category) {
  return INTENT_MODALITY[category] ?? null;
}

export function isMultimodalCategory(category) {
  return MULTIMODAL_CATEGORIES.has(category);
}

export function modelCategory(displayName, hfId = "") {
  const text = `${displayName ?? ""} ${hfId ?? ""}`;
  if (MUSIC_RE.test(text)) return "music";
  if (AUDIO_RE.test(text)) return "audio";
  if (CODE_RE.test(text)) return "code";
  return "chat";
}

/** Sortable realtime factor (higher = faster). Music RTF (wall/audio) inverts to ×real. */
export function audioRealtimeValue(cell) {
  if (cell == null) return null;
  if (cell.audioXReal != null) return cell.audioXReal;
  if (cell.rtf != null && cell.rtf > 0) return 1 / cell.rtf;
  return null;
}

/** Multimodal metric path. Text cells (tok/s) return null — callers keep decode_tok_s. */
export function multimodalMetricOf(cell) {
  if (cell == null || cell.category == null) return null;
  if (cell.category === "image" && cell.imagesPerSec != null) {
    return { value: cell.imagesPerSec, unit: "img/s", label: "images" };
  }
  if (AUDIO_MODALITY_CATEGORIES.has(cell.category)) {
    const value = audioRealtimeValue(cell);
    if (value != null) return { value, unit: "×real", label: "realtime" };
  }
  if (cell.category === "video" && cell.videoFramesPerSec != null) {
    return { value: cell.videoFramesPerSec, unit: "f/s", label: "frames" };
  }
  return null;
}
