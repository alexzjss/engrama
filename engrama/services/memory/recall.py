"""Word-based recall: facts, episodes, topics and opinion relevant to a user message."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from engrama.services.memory.topics import normalize_topic, plain_text

_STOP = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem que qual quais quem como quando onde
seu sua seus suas meu minha meus minhas teu tua eu tu ele ela voce voces mas ou se ao aos isso isto esse essa
este esta aquilo foi ser estou tem tenho tinha vai vou muito mais menos sobre ja so
the and for you your are was were what which who how when where this that these those with from about have has had
his her its our their not but can will would could should does did him she they them there here just very more
""".split())

_STAGES_OPINION = {"adult", "perfect", "final"}
_STAGES_PAST = {"perfect", "final"}

_STANCE_FALLBACK = {
    "pt": ("detesta", "não curte muito", "não tem opinião forte sobre", "gosta de", "adora"),
    "en": ("hates", "isn't fond of", "has no strong feelings about", "likes", "loves"),
}


@dataclass
class RecallContext:
    facts: list[str] = field(default_factory=list)
    episodes: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    past: list[str] = field(default_factory=list)
    opinion: str | None = None
    ancestral: list[str] = field(default_factory=list)   # dreams from before birth


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", s or "")).strip()


def _words(text: str) -> list[str]:
    out = []
    for w in re.split(r"[^a-z]+", plain_text(text)):
        if len(w) >= 3 and w not in _STOP and w not in out:
            out.append(w)
    return out


def _stance_word(stance: float, lang: str) -> str:
    try:
        from engrama.services.memory.opinions import stance_word
        return stance_word(stance, lang)
    except Exception:
        t = _STANCE_FALLBACK["pt" if lang == "pt" else "en"]
        if stance <= -0.5:
            return t[0]
        if stance < -0.15:
            return t[1]
        if stance <= 0.15:
            return t[2]
        return t[3] if stance < 0.5 else t[4]


def _facts(memory, words: list[str]) -> list[str]:
    rows = memory.fact_rows()
    hits = [r for r in rows
            if any(w in plain_text(f"{r['key']} {r['value']}".replace("_", " ")) for w in words)]
    chosen = hits[:3] if hits else rows[:2]
    return [c for c in (_clean(f"{r['key']}: {r['value']}") for r in chosen) if c]


def _opinion(memory, words: list[str], lang: str) -> str | None:
    cands = list(dict.fromkeys(normalize_topic(w) for w in words))
    getter = getattr(memory, "opinion", None)
    found = None
    if getter is not None:
        for c in cands:
            found = getter(c)
            if found:
                break
    else:
        by = {normalize_topic(r["topic"]): r for r in memory.opinion_rows()}
        found = next((by[c] for c in cands if c in by), None)
    if not found:
        return None
    if found.get("phrase") and found.get("phrase_lang") == lang:
        return _clean(found["phrase"]) or None
    return _clean(f"{_stance_word(found['stance'], lang)} {found['topic']}") or None


def recall(memory, text: str, stage: str, lang: str) -> RecallContext:
    try:
        if stage == "egg":
            return RecallContext()
        lang = "pt" if lang == "pt" else "en"
        words = _words(text)
        ctx = RecallContext()
        ctx.facts = _facts(memory, words)
        ctx.episodes = [c for c in (_clean(e) for e in memory.retrieve(words, 2)) if c]
        getter = getattr(memory, "retrieve_ancestral", None)
        if getter is not None:
            ctx.ancestral = [c for c in (_clean(e) for e in getter(words, 1)) if c]
        ctx.current = [c for c in (_clean(t) for t in memory.current_topics(2)) if c]
        if stage in _STAGES_PAST:
            ctx.past = [c for c in (_clean(t) for t in memory.past_topics(1)) if c]
        if stage in _STAGES_OPINION:
            ctx.opinion = _opinion(memory, words, lang)
        return ctx
    except Exception:
        return RecallContext()
