from __future__ import annotations

from typing import Callable


from engrama.services.memory import opinions
from engrama.services.memory.topics import normalize_topic
from engrama.services.memory.store._util import (
    _clamp)


class OpinionsMixin:
    # ---- opinions ------------------------------------------------------
    def opinion_rows(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT topic, lean, experience, confidence, phrase, phrase_lang, t"
                " FROM opinions ORDER BY confidence DESC, topic").fetchall()
        return [dict(topic=tp, lean=ln, experience=ex, confidence=c, phrase=ph,
                     phrase_lang=pl, t=t, stance=opinions.stance(ln, ex))
                for tp, ln, ex, c, ph, pl, t in rows]

    def update_opinion(self, topic: str, lean_fn: Callable[[str], float], valence: float) -> None:
        """Create the opinion with a frozen lean on first contact, then move experience.

        The user's affinity never enters the update.
        """
        key = normalize_topic(topic)
        if not key:
            return
        with self._lock:
            if self._blocked("topic", key):
                return
            now = self._now()
            row = self._db.execute(
                "SELECT experience, confidence FROM opinions WHERE topic=?", (key,)).fetchone()
            if row is None:
                lean = _clamp(float(lean_fn(key)))
                exp, conf = 0.0, 0.0
                self._db.execute(
                    "INSERT INTO opinions(topic, lean, experience, confidence, phrase,"
                    " phrase_lang, t) VALUES(?,?,?,?,NULL,NULL,?)",
                    (key, lean, exp, conf, now))
            else:
                exp, conf = row
            exp = _clamp(exp + 0.1 * (_clamp(valence) - exp))
            conf = min(1.0, conf + 0.05)
            self._db.execute(
                "UPDATE opinions SET experience=?, confidence=?, t=? WHERE topic=?",
                (exp, conf, now, key))
            self._db.commit()

    def opinion(self, topic: str) -> dict | None:
        key = normalize_topic(topic)
        with self._lock:
            row = self._db.execute(
                "SELECT lean, experience, confidence, phrase, phrase_lang FROM opinions"
                " WHERE topic=?", (key,)).fetchone()
        if row is None:
            return None
        lean, exp, conf, phrase, phrase_lang = row
        return dict(topic=key, lean=lean, experience=exp, stance=opinions.stance(lean, exp),
                    confidence=conf, phrase=phrase, phrase_lang=phrase_lang)

    def set_opinion_phrase(self, topic: str, phrase: str, lang: str) -> None:
        key = normalize_topic(topic)
        if not key:
            return
        with self._lock:
            if self._blocked("topic", key):
                return
            now = self._now()
            self._db.execute(
                "UPDATE opinions SET phrase=?, phrase_lang=?, t=? WHERE topic=?",
                (phrase, lang, now, key))
            self._db.commit()
