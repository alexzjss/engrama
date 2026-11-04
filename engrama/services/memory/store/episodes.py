from __future__ import annotations

import math
from typing import Iterable


from engrama.services.memory import (
    CURRENT_MIN_SALIENCE, PAST_MIN_AFFINITY,
    PAST_MIN_AGE, W_IMPORTANCE, W_RECENCY,
    W_RELEVANCE, W_SEM, W_WORD)
from engrama.services.memory.topics import normalize_topic
from engrama.services.memory.store._util import (
    RECENCY_TAU, _sem, _clamp, _decay)


class EpisodesMixin:
    # ---- episodes ------------------------------------------------------
    def add_episode(self, kind: str, summary: str, valence: float = 0.0,
                    importance: float = 0.3, topic: str | None = None,
                    topics: Iterable[str] = (), facts: Iterable[str] = ()) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                " VALUES(?,?,?,?,?,?)",
                (self._now(), kind, summary, valence, importance, topic))
            eid = int(cur.lastrowid)
            links = {("topic", normalize_topic(t)) for t in topics if t and normalize_topic(t)}
            links |= {("fact", f) for f in facts if f}
            self._db.executemany(
                "INSERT INTO episode_links(episode_id, kind, ref) VALUES(?,?,?)",
                [(eid, k, r) for k, r in sorted(links)])
            self._db.commit()
            return eid

    def link_episode(self, episode_id: int, topics: Iterable[str] = (), facts: Iterable[str] = ()) -> None:
        """Add topic/fact links to an already-written episode (no-op if it was deleted)."""
        with self._lock:
            if self._db.execute("SELECT 1 FROM episodes WHERE id=?", (episode_id,)).fetchone() is None:
                return
            links = {("topic", normalize_topic(t)) for t in topics if t and normalize_topic(t)}
            links |= {("fact", f) for f in facts if f}
            self._db.executemany(
                "INSERT INTO episode_links(episode_id, kind, ref) VALUES(?,?,?)",
                [(episode_id, k, r) for k, r in sorted(links)
                 if not self._db.execute(
                     "SELECT 1 FROM episode_links WHERE episode_id=? AND kind=? AND ref=?",
                     (episode_id, k, r)).fetchone()])
            self._db.commit()

    def retrieve(self, words: list[str], k: int = 5,
                 sims: dict[int, float] | None = None) -> list[str]:
        with self._lock:
            now = self._now()
            ws = [w.lower() for w in words if w]
            scored = []
            for _id, t, summary, importance, topic in self._db.execute(
                    "SELECT id, t, summary, importance, topic FROM episodes WHERE kind != 'ancestral'"):
                text = f"{summary} {topic or ''}".lower()
                overlap = sum(1 for w in ws if w in text) / len(ws) if ws else 0.0
                recency = math.exp(-max(0.0, now - t) / RECENCY_TAU)
                if sims is None:
                    score = 0.5 * importance + 0.3 * recency + 0.2 * overlap
                else:
                    relevance = W_SEM * _sem(sims.get(_id)) + W_WORD * overlap
                    score = (W_IMPORTANCE * importance + W_RECENCY * recency
                             + W_RELEVANCE * relevance)
                scored.append((score, _id, summary))
        scored.sort(key=lambda s: (-s[0], -s[1]))
        return [s[2] for s in scored[:k]]

    def recent(self, n: int = 8) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT summary FROM episodes ORDER BY t DESC, id DESC LIMIT ?", (n,)).fetchall()
        return [r[0] for r in rows]

    def recent_reflections(self, n: int = 3) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT summary FROM episodes WHERE kind='reflection'"
                " ORDER BY t DESC, id DESC LIMIT ?", (n,)).fetchall()
        return [r[0] for r in rows]

    # ---- facts ---------------------------------------------------------
    def upsert_fact(self, key: str, value: str, confidence: float, source: str) -> bool:
        with self._lock:
            if self._blocked("fact", key):
                return False
            now = self._now()
            row = self._db.execute(
                "SELECT value, confidence FROM facts WHERE key=?", (key,)).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO facts(key, value, confidence, source, t) VALUES(?,?,?,?,?)",
                    (key, value, confidence, source, now))
            else:
                old_v, old_c = row
                if old_v == value:
                    conf = min(1.0, old_c + 0.5 * (1.0 - old_c) * confidence)
                    self._db.execute(
                        "UPDATE facts SET confidence=?, source=?, t=? WHERE key=?",
                        (conf, source, now, key))
                elif confidence >= 0.5 or confidence >= old_c:
                    self._db.execute(
                        "UPDATE facts SET value=?, confidence=?, source=?, t=? WHERE key=?",
                        (value, confidence, source, now, key))
                    self._vdel("kind='fact' AND ref=?", (key,))   # the old vector encodes the old value
            self._db.commit()
            return True

    def facts(self, limit: int = 20) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT key, value FROM facts ORDER BY confidence DESC, t DESC, id DESC LIMIT ?",
                (limit,)).fetchall()
        return [(k, v) for k, v in rows]

    def fact_rows(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT key, value, confidence, source, t FROM facts"
                " ORDER BY confidence DESC, t DESC, id DESC").fetchall()
        return [dict(key=k, value=v, confidence=c, source=s, t=t) for k, v, c, s, t in rows]

    # ---- topics --------------------------------------------------------
    def bump_topic(self, name: str, delta: float, source: str = "chat") -> str:
        key = normalize_topic(name)
        if not key:
            return ""
        with self._lock:
            if self._blocked("topic", key):
                return ""
            now = self._now()
            row = self._db.execute(
                "SELECT affinity, salience, t_salience FROM topics WHERE name=?", (key,)).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO topics(name, affinity, t, salience, t_salience, first_t,"
                    " last_t, mentions, source) VALUES(?,?,?,?,?,?,?,?,?)",
                    (key, _clamp(delta), now, 1.0, now, now, now, 1, source))
            else:
                aff, sal, t_sal = row
                self._db.execute(
                    "UPDATE topics SET affinity=?, t=?, salience=?, t_salience=?, last_t=?,"
                    " mentions=mentions+1 WHERE name=?",
                    (_clamp(aff + delta), now, _decay(sal, t_sal, now) + 1.0, now, now, key))
            self._db.commit()
            return key

    def top_topics(self, n: int = 3) -> list[tuple[str, float]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT name, affinity FROM topics ORDER BY affinity DESC, t DESC LIMIT ?",
                (n,)).fetchall()
        return [(a, b) for a, b in rows]

    def topic_rows(self) -> list[dict]:
        with self._lock:
            now = self._now()
            rows = self._db.execute(
                "SELECT name, affinity, salience, t_salience, first_t, last_t, mentions, source"
                " FROM topics").fetchall()
        out = [dict(name=n, affinity=a, salience=_decay(s, ts, now), first_t=f, last_t=l,
                    mentions=m, source=src) for n, a, s, ts, f, l, m, src in rows]
        out.sort(key=lambda r: (-r["salience"], -r["affinity"], r["name"]))
        return out

    def current_topics(self, n: int = 3) -> list[str]:
        rows = [r for r in self.topic_rows() if r["salience"] >= CURRENT_MIN_SALIENCE]
        return [r["name"] for r in rows[:n]]

    def past_topics(self, n: int = 3) -> list[str]:
        now = self._now()
        rows = [r for r in self.topic_rows()
                if now - r["last_t"] >= PAST_MIN_AGE
                and r["affinity"] >= PAST_MIN_AFFINITY
                and r["salience"] < CURRENT_MIN_SALIENCE]
        rows.sort(key=lambda r: (-r["affinity"], -r["last_t"], r["name"]))
        return [r["name"] for r in rows[:n]]
