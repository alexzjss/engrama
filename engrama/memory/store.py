from __future__ import annotations

import math
import sqlite3
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable

DAY = 86400.0
FORGET_AGE = 3 * DAY
FORGET_BELOW = 0.3
COMPACT_IMPORTANCE = 0.35
RECENCY_TAU = 7 * DAY

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes(
    id INTEGER PRIMARY KEY, t REAL, kind TEXT, summary TEXT,
    valence REAL, importance REAL, topic TEXT NULL);
CREATE TABLE IF NOT EXISTS facts(
    id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT,
    confidence REAL, source TEXT, t REAL);
CREATE TABLE IF NOT EXISTS topics(name TEXT PRIMARY KEY, affinity REAL, t REAL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
INSERT OR IGNORE INTO meta(k, v) VALUES('schema_version', '1');
"""


def _dm(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%d/%m")


class MemoryStore:
    def __init__(self, db_path: Path, now_fn: Callable[[], float] = time.time) -> None:
        self._now = now_fn
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def add_episode(self, kind: str, summary: str, valence: float = 0.0,
                    importance: float = 0.3, topic: str | None = None) -> int:
        cur = self._db.execute(
            "INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
            " VALUES(?,?,?,?,?,?)",
            (self._now(), kind, summary, valence, importance, topic))
        self._db.commit()
        return int(cur.lastrowid)

    def upsert_fact(self, key: str, value: str, confidence: float, source: str) -> None:
        self._db.execute(
            "INSERT INTO facts(key, value, confidence, source, t) VALUES(?,?,?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
            " confidence=excluded.confidence, source=excluded.source, t=excluded.t"
            " WHERE excluded.confidence >= facts.confidence",
            (key, value, confidence, source, self._now()))
        self._db.commit()

    def facts(self, limit: int = 20) -> list[tuple[str, str]]:
        rows = self._db.execute(
            "SELECT key, value FROM facts ORDER BY confidence DESC, t DESC, id DESC LIMIT ?",
            (limit,)).fetchall()
        return [(k, v) for k, v in rows]

    def bump_topic(self, name: str, delta: float) -> None:
        row = self._db.execute("SELECT affinity FROM topics WHERE name=?", (name,)).fetchone()
        value = max(-1.0, min(1.0, (row[0] if row else 0.0) + delta))
        self._db.execute(
            "INSERT INTO topics(name, affinity, t) VALUES(?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET affinity=excluded.affinity, t=excluded.t",
            (name, value, self._now()))
        self._db.commit()

    def top_topics(self, n: int = 3) -> list[tuple[str, float]]:
        rows = self._db.execute(
            "SELECT name, affinity FROM topics ORDER BY affinity DESC, t DESC LIMIT ?",
            (n,)).fetchall()
        return [(a, b) for a, b in rows]

    def retrieve(self, words: list[str], k: int = 5) -> list[str]:
        now = self._now()
        ws = [w.lower() for w in words if w]
        scored = []
        for _id, t, summary, importance, topic in self._db.execute(
                "SELECT id, t, summary, importance, topic FROM episodes"):
            text = f"{summary} {topic or ''}".lower()
            overlap = sum(1 for w in ws if w in text) / len(ws) if ws else 0.0
            recency = math.exp(-max(0.0, now - t) / RECENCY_TAU)
            score = 0.5 * importance + 0.3 * recency + 0.2 * overlap
            scored.append((score, _id, summary))
        scored.sort(key=lambda s: (-s[0], -s[1]))
        return [s[2] for s in scored[:k]]

    def recent(self, n: int = 8) -> list[str]:
        rows = self._db.execute(
            "SELECT summary FROM episodes ORDER BY t DESC, id DESC LIMIT ?", (n,)).fetchall()
        return [r[0] for r in rows]

    def forget(self, now: float | None = None) -> int:
        now = self._now() if now is None else now
        rows = self._db.execute(
            "SELECT id, kind, t FROM episodes WHERE importance < ? AND t < ?",
            (FORGET_BELOW, now - FORGET_AGE)).fetchall()
        if not rows:
            return 0
        groups: dict[str, list[float]] = {}
        for _id, kind, t in rows:
            groups.setdefault(kind, []).append(t)
        self._db.executemany("DELETE FROM episodes WHERE id=?", [(r[0],) for r in rows])
        for kind, ts in groups.items():
            summary = f"{kind} ×{len(ts)} ({_dm(min(ts))}–{_dm(max(ts))})"
            self._db.execute(
                "INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                " VALUES(?,?,?,?,?,NULL)",
                (now, kind, summary, 0.0, COMPACT_IMPORTANCE))
        self._db.commit()
        return len(rows)

    def close(self) -> None:
        self._db.close()


class WorkingMemory:
    def __init__(self, maxlen: int = 12) -> None:
        self._msgs: deque[dict] = deque(maxlen=maxlen)

    def add(self, role: str, content: str) -> None:
        self._msgs.append({"role": role, "content": content})

    def messages(self) -> list[dict]:
        return list(self._msgs)

    def clear(self) -> None:
        self._msgs.clear()
