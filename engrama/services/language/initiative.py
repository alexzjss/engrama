"""Rare, stage-gated self-initiated remarks (quota of active use, never when resting)."""
from __future__ import annotations
import logging
import random
from typing import Callable

from engrama.services.memory import INITIATIVE_PER_ACTIVE_S, OPPORTUNITY_EVERY_S

log = logging.getLogger("engrama.initiative")

FIRE_PROBABILITY = 0.25
MIN_OPINION_CONFIDENCE = 0.2
_OPPORTUNITY_ACTIONS = ("ask_attention", "show_something")
_LATE = ("perfect", "final")
_ADULT_PLUS = ("adult", "perfect", "final")
_CHILD_PLUS = ("child", "adult", "perfect", "final")


class InitiativePolicy:
    def __init__(self, memory, now_fn: Callable[[], float], rng: random.Random | None = None) -> None:
        self.memory = memory
        self._now = now_fn
        self._rng = rng or random.Random(0)
        self._last_call: float | None = None
        self._since_check = 0.0
        self._usage = self._load("initiative_usage")
        self._last_fire = self._load("initiative_last")

    def _load(self, key: str) -> float:
        try:
            v = self.memory.meta_get(key)
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def _save(self) -> None:
        try:
            self.memory.meta_set("initiative_usage", repr(self._usage))
            self.memory.meta_set("initiative_last", repr(self._last_fire))
        except Exception:
            log.exception("initiative persist failed")

    def _pick(self, stage: str) -> tuple[str, str | None] | None:
        m = self.memory
        if stage in _LATE:
            past = m.past_topics(1)
            if past:
                return "past", past[0]
        if stage in _ADULT_PLUS:
            rows = [r for r in m.opinion_rows() if r["confidence"] >= MIN_OPINION_CONFIDENCE]
            if rows:
                best = max(rows, key=lambda r: r["confidence"])
                return "opinion", best["topic"]
        if stage in _CHILD_PLUS:
            cur = m.current_topics(1)
            if cur:
                return "current", cur[0]
        return None

    def update(self, now: float, *, stage: str, user_active: bool, llm_ready: bool,
               resting: bool, fullscreen: bool, action: str) -> tuple[str, str | None] | None:
        delta = 0.0 if self._last_call is None else max(0.0, now - self._last_call)
        self._last_call = now
        if user_active:
            step = min(delta, OPPORTUNITY_EVERY_S)
            self._usage += step
            self._since_check += step
        if stage in ("egg", "baby") or not llm_ready or resting or fullscreen:
            return None
        if self._usage < INITIATIVE_PER_ACTIVE_S:
            return None
        if not (action in _OPPORTUNITY_ACTIONS or self._since_check >= OPPORTUNITY_EVERY_S):
            return None
        self._since_check = 0.0
        if self._rng.random() >= FIRE_PROBABILITY:
            return None
        choice = self._pick(stage)
        if choice is None:
            return None
        self._usage = 0.0
        self._last_fire = now
        self._save()
        return choice
