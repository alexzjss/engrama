from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

import numpy as np

from engrama.services.memory import (
    SALIENCE_HALF_LIFE, SEM_MIN_SIM)
from engrama.services.memory.topics import plain_text

DAY = 86400.0
FORGET_AGE = 3 * DAY
FORGET_BELOW = 0.3
COMPACT_IMPORTANCE = 0.35
RECENCY_TAU = 7 * DAY

VECTOR_KINDS = ("episode", "fact", "topic", "ancestral")

_PT_WORDS = frozenset("de da do que com nao uma um para meu minha foi sobre muito vez dia".split())
_EN_WORDS = frozenset("the and you with was about of to for a an my many day".split())

# (with topic, without topic) per kind and language.
_KIND_LABELS = {
    "chat": {"pt": ("conversa sobre", "conversa"), "en": ("talked about", "chatted")},
    "feed": {"pt": ("comeu", "comeu"), "en": ("ate", "ate")},
    "play": {"pt": ("brincou", "brincou"), "en": ("played", "played")},
    "sleep": {"pt": ("dormiu", "dormiu"), "en": ("slept", "slept")},
}


def _sem(sim: float | None) -> float:
    """Cosine rescaled so SEM_MIN_SIM -> 0 and 1 -> 1; below the threshold counts as nothing."""
    if sim is None or not math.isfinite(sim):
        return 0.0
    return max(0.0, (float(sim) - SEM_MIN_SIM) / (1.0 - SEM_MIN_SIM))


def _vtext(s: str) -> str:
    """Text that becomes a vector: what is stored, digits removed (same cleaning as recall)."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", s or "")).strip()


def _vhash(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def _unit(v) -> np.ndarray | None:
    """float32 unit vector, or None if empty, not 1-D, non-finite or null."""
    try:
        a = np.asarray(v, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if a.ndim != 1 or a.size == 0 or not np.all(np.isfinite(a)):
        return None
    n = float(np.linalg.norm(a))
    if not math.isfinite(n) or n <= 0.0:
        return None
    return a / n


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _decay(salience: float, t_salience: float, now: float) -> float:
    # max(0, ...) keeps a backwards clock from inflating salience.
    return max(0.0, salience) * 0.5 ** (max(0.0, now - t_salience) / SALIENCE_HALF_LIFE)


def _term_regex(term: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?:s|es)?(?!\w)")


def _lang_of(texts: Iterable[str]) -> str:
    pt = en = 0
    for text in texts:
        for w in plain_text(text).split():
            pt += w in _PT_WORDS
            en += w in _EN_WORDS
    return "en" if en > pt else "pt"


def _compact_summary(kind: str, topic: str | None, ts: list[float], texts: list[str]) -> str:
    lang = _lang_of(texts)
    n = len(ts)
    days = len({int(t // DAY) for t in ts})
    span = int((max(ts) - min(ts)) // DAY) + 1
    if n >= 3 and span >= 2 and days / span >= 0.6:
        freq = "quase todo dia" if lang == "pt" else "almost every day"
    elif n >= 3:
        freq = "várias vezes" if lang == "pt" else "many times"
    else:
        freq = "às vezes" if lang == "pt" else "sometimes"
    labels = _KIND_LABELS.get(kind)
    if labels:
        with_topic, without = labels[lang]
        base = f"{with_topic} {topic}" if topic else without
    else:
        base = re.sub(r"\d+", "", kind.replace("_", " ")).strip() or "evento"
    return f"{base}, {freq}"

