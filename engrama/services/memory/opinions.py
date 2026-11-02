from __future__ import annotations

import hashlib

_U64_MAX = float(2 ** 64 - 1)


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def innate_lean(seed: int, topic: str, traits: dict[str, float] | None = None) -> float:
    """Deterministic starting position of the creature on a topic, in [-1, 1].

    The base comes from a hash of (seed, topic); curiosity nudges it by at most 0.2.
    """
    digest = hashlib.blake2b(f"{seed}:{topic}".encode("utf-8"), digest_size=8).digest()
    base = int.from_bytes(digest, "big") / _U64_MAX * 2.0 - 1.0
    mod = 0.0
    if traits:
        curiosity = float(traits.get("curiosidade", 50.0))
        mod = _clamp(0.15 * (curiosity - 50.0) / 50.0, -0.2, 0.2)
    return _clamp(base + mod)


def stance(lean: float, experience: float) -> float:
    """Current opinion: mostly the innate lean, partly lived experience."""
    return _clamp(0.7 * lean + 0.3 * experience)


_WORDS = {
    "pt": ("detesta", "não curte muito", "não tem opinião forte sobre", "gosta de", "adora"),
    "en": ("hates", "isn't fond of", "has no strong feelings about", "likes", "loves"),
}


def stance_word(stance_value: float, lang: str) -> str:
    """Verb phrase for a stance, without digits. Unknown languages fall back to PT."""
    hates, dislikes, neutral, likes, loves = _WORDS["en" if lang == "en" else "pt"]
    if stance_value <= -0.5:
        return hates
    if stance_value < -0.15:
        return dislikes
    if stance_value <= 0.15:
        return neutral
    if stance_value < 0.5:
        return likes
    return loves
