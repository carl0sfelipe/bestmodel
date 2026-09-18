"""Pool category (user intent) taxonomy.

`category` is the user intent stored on `lm_model` / derived models.json.
Physical modality is derived from intent — it is not a second CHECK column.

    chat, code  → text
    image       → image
    audio       → audio   (STT / TTS / SFX; e.g. Whisper, AudioGen)
    music       → audio   (text-to-music / song gen; same waveform domain)
    video       → video

`music` is not a third LLM intent beside chat/code. It is the generation
intent of the audio modality. Whisper-style STT stays `audio`; MusicGen /
MAGNeT / JASCO / ACE-Step / YuE / DiffRhythm / Stable Audio land as `music`.

Multimodal cells (audio + music) use RTF / ×realtime / wall / peak VRAM /
durationS — never decode_tok_s.
"""

from __future__ import annotations

import re

# Product intents accepted by the SQLite CHECK, API filter, and derive.
# `vision` is listed in the UI but has no category yet (no collection plan).
MODEL_CATEGORIES = ("chat", "code", "image", "audio", "music", "video")

TEXT_CATEGORIES = frozenset({"chat", "code"})
# Intents that share the audio waveform domain (STT/SFX vs song gen).
AUDIO_MODALITY_CATEGORIES = frozenset({"audio", "music"})
MULTIMODAL_CATEGORIES = frozenset({"image", "audio", "music", "video"})

INTENT_MODALITY = {
    "chat": "text",
    "code": "text",
    "image": "image",
    "audio": "audio",
    "music": "audio",
    "video": "video",
}

_MUSIC_RE = re.compile(
    r"musicgen|jasco|ace-?step|acestep|diffrhythm|stable[\s_-]?audio"
    r"|\bmagnet\b|magnet-|yue2|\byue\b|text-to-music|text2music",
    re.I,
)
_AUDIO_RE = re.compile(
    r"whisper|wav2vec|audiogen|faster-whisper|distil-whisper"
    r"|speech[\s_-]?to[\s_-]?text|\bstt\b|\btts\b",
    re.I,
)
_CODE_RE = re.compile(r"coder|starcoder|codestral|code", re.I)


def category_check_sql() -> str:
    """Literal CHECK tuple for the lm_model.category column."""
    inner = ",".join(f"'{name}'" for name in MODEL_CATEGORIES)
    return f"({inner})"


def modality_of(category: str) -> str | None:
    return INTENT_MODALITY.get(category)


def is_multimodal_category(category: str | None) -> bool:
    return category in MULTIMODAL_CATEGORIES


def validate_category_filter(category: str | None) -> str | None:
    """Return the filter value, or None for 'no filter'. Invalid → ValueError."""
    if category is None:
        return None
    if category not in MODEL_CATEGORIES:
        raise ValueError(f"invalid category {category!r}")
    return category


def model_category(display_name: str, hf_id: str = "") -> str:
    """Classify a catalog row into a pool intent.

    Music is matched before audio so MusicGen does not fall through to chat.
    Audio (Whisper / AudioGen) is matched before the legacy code/chat split
    so STT is never labelled as an LLM intent. Unknown names stay `chat`.
    """
    text = f"{display_name or ''} {hf_id or ''}"
    if _MUSIC_RE.search(text):
        return "music"
    if _AUDIO_RE.search(text):
        return "audio"
    if _CODE_RE.search(text):
        return "code"
    return "chat"
