from __future__ import annotations

from typing import Iterable


from engrama.services.memory.topics import SYNONYMS, normalize_topic, plain_text
from engrama.services.memory.store._util import (
    _term_regex)


class BlockingMixin:
    # ---- deletion / blocklist -----------------------------------------
    def _blocked(self, kind: str, ref: str, since: float | None = None) -> bool:
        row = self._db.execute(
            "SELECT t FROM blocklist WHERE kind=? AND ref=?", (kind, ref)).fetchone()
        if row is None:
            return False
        return since is None or since <= row[0]

    def is_blocked(self, kind: str, ref: str, since: float | None = None) -> bool:
        ref = normalize_topic(ref) if kind == "topic" else ref
        with self._lock:
            return self._blocked(kind, ref, since)

    def unblock_on_new_mention(self, kind: str, ref: str, t: float | None = None) -> bool:
        """Lift a block for a mention newer than it. With ``t`` given, a mention
        at or before the block time leaves the block in place."""
        ref = normalize_topic(ref) if kind == "topic" else ref
        with self._lock:
            if t is not None and self._blocked(kind, ref, t):
                return False
            self._db.execute("DELETE FROM blocklist WHERE kind=? AND ref=?", (kind, ref))
            self._db.commit()
            return True

    def _block(self, kind: str, ref: str, now: float) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO blocklist(kind, ref, t) VALUES(?,?,?)", (kind, ref, now))

    def _drop_episodes(self, ids: Iterable[int]) -> int:
        ids = sorted(set(ids))
        for i in range(0, len(ids), 500):
            chunk = [(x,) for x in ids[i:i + 500]]
            self._db.executemany("DELETE FROM episode_links WHERE episode_id=?", chunk)
            self._db.executemany("DELETE FROM episodes WHERE id=?", chunk)
            self._vdel_many("kind IN ('episode','ancestral') AND ref=?",
                            [(str(x),) for (x,) in chunk])
        return len(ids)

    def _episodes_about(self, kind: str, ref: str, terms: Iterable[str]) -> set[int]:
        ids = {r[0] for r in self._db.execute(
            "SELECT episode_id FROM episode_links WHERE kind=? AND ref=?", (kind, ref))}
        pats = [_term_regex(t) for t in terms if t]
        if pats:
            for eid, summary, topic in self._db.execute(
                    "SELECT id, summary, topic FROM episodes").fetchall():
                text = plain_text(f"{summary} {topic or ''}")
                if any(p.search(text) for p in pats):
                    ids.add(eid)
        return ids

    def delete_topic(self, name: str) -> int:
        key = normalize_topic(name)
        if not key:
            return 0
        terms = {key} | {k for k, v in SYNONYMS.items() if v == key}
        with self._lock:
            ids = self._episodes_about("topic", key, terms)
            n = self._drop_episodes(ids)
            self._db.execute("DELETE FROM topics WHERE name=?", (key,))
            self._vdel("kind='topic' AND ref=?", (key,))
            self._db.execute("DELETE FROM opinions WHERE topic=?", (key,))
            self._block("topic", key, self._now())
            self._db.commit()
            return n

    def delete_fact(self, key: str) -> int:
        with self._lock:
            row = self._db.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
            terms = [plain_text(row[0])] if row and plain_text(row[0]) else []
            ids = self._episodes_about("fact", key, terms)
            n = self._drop_episodes(ids)
            self._db.execute("DELETE FROM facts WHERE key=?", (key,))
            self._vdel("kind='fact' AND ref=?", (key,))
            self._block("fact", key, self._now())
            self._db.commit()
            return n

    def forget_all_about_user(self) -> None:
        with self._lock:
            now = self._now()
            for (name,) in self._db.execute("SELECT name FROM topics").fetchall():
                self._block("topic", name, now)
            for (key,) in self._db.execute("SELECT key FROM facts").fetchall():
                self._block("fact", key, now)
            for table in ("facts", "topics", "episodes", "episode_links", "app_categories"):
                self._db.execute(f"DELETE FROM {table}")
            self._vdel("1=1")       # every vector derives from the rows just deleted
            self._db.execute(
                "UPDATE opinions SET experience=0, confidence=0, phrase=NULL, phrase_lang=NULL")
            self._db.commit()
