from __future__ import annotations

import math
import re
import sqlite3
from pathlib import Path


from engrama.balance import ANCESTRAL_MAX
from engrama.services.memory import (
    MAX_EPISODES, MAX_FACTS, MAX_TOPICS, SEM_MIN_SIM, W_SEM, W_WORD)
from engrama.services.memory.topics import plain_text
from engrama.services.memory.store._util import (
    FORGET_AGE, FORGET_BELOW, COMPACT_IMPORTANCE, _sem, _term_regex, _compact_summary)


class GenerationsMixin:
    # ---- generations / ancestral memory --------------------------------
    def ancestral_candidates(self, k: int = ANCESTRAL_MAX) -> list[str]:
        """Summaries of the most striking episodes: no digits, nothing blocked, no user facts."""
        with self._lock:
            refs = [r[0] for r in self._db.execute(
                "SELECT ref FROM blocklist WHERE kind IN ('topic','perceived')")]
            pats = [_term_regex(r) for r in refs if r]
            fact_eps = {r[0] for r in self._db.execute(
                "SELECT episode_id FROM episode_links WHERE kind='fact'")}
            blocked_eps = {r[0] for r in self._db.execute(
                "SELECT l.episode_id FROM episode_links l JOIN blocklist b"
                " ON b.kind='topic' AND b.ref=l.ref WHERE l.kind='topic'")}
            rows = self._db.execute(
                "SELECT id, summary, topic FROM episodes WHERE kind NOT IN ('ancestral','arquivo')"
                " ORDER BY importance DESC, ABS(valence) DESC, t DESC, id DESC").fetchall()
        out: list[str] = []
        for eid, summary, topic in rows:
            summary = (summary or "").strip()
            if not summary or re.search(r"\d", summary) or eid in fact_eps or eid in blocked_eps:
                continue
            text = plain_text(f"{summary} {topic or ''}")
            if any(p.search(text) for p in pats):
                continue
            out.append(summary)
            if len(out) >= k:
                break
        return out

    def ancestral_rows(self, n: int = 1) -> list[str]:
        """Ancestral summaries, newest first (n <= 0: all)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT summary FROM episodes WHERE kind='ancestral' ORDER BY id DESC").fetchall()
        out = [r[0] for r in rows]
        return out[:n] if n > 0 else out

    def retrieve_ancestral(self, words: list[str], k: int = 1,
                           sims: dict[int, float] | None = None) -> list[str]:
        """Ancestral episodes whose text matches at least one word (or, with ``sims``, by meaning)."""
        ws = [w.lower() for w in words if w]
        if sims is None:
            if not ws:
                return []
            with self._lock:
                rows = self._db.execute(
                    "SELECT id, summary FROM episodes WHERE kind='ancestral'").fetchall()
            scored = []
            for _id, summary in rows:
                text = plain_text(summary)
                hit = sum(1 for w in ws if w in text)
                if hit:
                    scored.append((-hit, -_id, summary))
            scored.sort()
            return [x[2] for x in scored[:k]]
        with self._lock:
            rows = self._db.execute(
                "SELECT id, summary FROM episodes WHERE kind='ancestral'").fetchall()
        scored = []
        for _id, summary in rows:
            text = plain_text(summary)
            hit = sum(1 for w in ws if w in text)
            sim = sims.get(_id)
            sim = float(sim) if sim is not None and math.isfinite(sim) else 0.0
            if hit or sim >= SEM_MIN_SIM:
                overlap = hit / len(ws) if ws else 0.0
                scored.append((-(W_SEM * _sem(sim) + W_WORD * overlap), -_id, summary))
        scored.sort()
        return [x[2] for x in scored[:k]]

    def archive_to(self, path: Path) -> None:
        """Consistent copy of the database (sqlite3 backup API); creates parent folders.

        The copy carries the memory of the finished life but no vectors (they are a derived index
        of the current model and are not kept in the archive)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._db.commit()
            dest = sqlite3.connect(str(path))
            try:
                self._db.backup(dest)
                dest.execute("PRAGMA secure_delete = ON")
                dest.execute("DELETE FROM vectors")
                dest.execute("DELETE FROM meta WHERE k='vector_model'")
                dest.commit()
                dest.execute("VACUUM")
            finally:
                dest.close()

    def new_generation(self, ancestral: list[str]) -> None:
        """Wipe the generation's memory; keep blocklist and app_categories; seed ancestral episodes."""
        with self._lock:
            now = self._now()
            for table in ("episodes", "episode_links", "facts", "topics", "opinions"):
                self._db.execute(f"DELETE FROM {table}")
            self._vdel("1=1")
            self._db.execute("DELETE FROM meta WHERE k NOT IN ('schema_version', 'vector_model')")
            for summary in ancestral:
                summary = (summary or "").strip()
                if summary:
                    self._db.execute(
                        "INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                        " VALUES(?,?,?,?,?,?)", (now, "ancestral", summary, 0.0, 0.6, None))
            self._db.commit()

    # ---- compaction / caps --------------------------------------------
    def enforce_caps(self) -> None:
        with self._lock:
            self._enforce_caps()
            self._db.commit()

    def _enforce_caps(self) -> None:
        n = self._db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        if n > MAX_EPISODES:
            ids = [r[0] for r in self._db.execute(
                "SELECT id FROM episodes ORDER BY importance ASC, t ASC, id ASC LIMIT ?",
                (n - MAX_EPISODES,))]
            self._drop_episodes(ids)
        n = self._db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        if n > MAX_FACTS:
            self._db.execute(
                "DELETE FROM facts WHERE id IN (SELECT id FROM facts"
                " ORDER BY confidence ASC, t ASC, id ASC LIMIT ?)", (n - MAX_FACTS,))
        n = self._db.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        if n > MAX_TOPICS:
            self._db.execute(
                "DELETE FROM topics WHERE name IN (SELECT name FROM topics"
                " ORDER BY mentions ASC, last_t ASC, name ASC LIMIT ?)", (n - MAX_TOPICS,))
        # Facts and topics above go by SQL, not through a helper: sweep what no longer exists.
        self._vdel("(kind='fact' AND ref NOT IN (SELECT key FROM facts))"
                   " OR (kind='topic' AND ref NOT IN (SELECT name FROM topics))"
                   " OR (kind='episode' AND ref NOT IN"
                   "  (SELECT CAST(id AS TEXT) FROM episodes WHERE kind != 'ancestral'))"
                   " OR (kind='ancestral' AND ref NOT IN"
                   "  (SELECT CAST(id AS TEXT) FROM episodes WHERE kind = 'ancestral'))"
                   " OR kind NOT IN ('episode','fact','topic','ancestral')")

    def forget(self, now: float | None = None) -> int:
        with self._lock:
            now = self._now() if now is None else now
            rows = self._db.execute(
                "SELECT id, kind, t, topic, summary FROM episodes WHERE importance < ? AND t < ?",
                (FORGET_BELOW, now - FORGET_AGE)).fetchall()
            if not rows:
                self._enforce_caps()
                self._db.commit()
                return 0
            groups: dict[tuple[str, str | None], list[tuple[float, str]]] = {}
            for _id, kind, t, topic, summary in rows:
                gk = (kind, topic if kind == "chat" and topic else None)
                groups.setdefault(gk, []).append((t, summary))
            self._drop_episodes(r[0] for r in rows)
            for (kind, topic), items in groups.items():
                summary = _compact_summary(
                    kind, topic, [t for t, _ in items], [s for _, s in items])
                self._db.execute(
                    "INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                    " VALUES(?,?,?,?,?,?)",
                    (now, kind, summary, 0.0, COMPACT_IMPORTANCE, topic))
            self._enforce_caps()
            self._db.commit()
            return len(rows)
