from __future__ import annotations

import math
import os
import re
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Iterable

from engrama.services.memory import (
    CURRENT_MIN_SALIENCE, MAX_EPISODES, MAX_FACTS, MAX_TOPICS, PAST_MIN_AFFINITY,
    PAST_MIN_AGE, SALIENCE_HALF_LIFE)
from engrama.services.memory import opinions
from engrama.services.perception import (
    ACTIVITY_EPISODE_EVERY_S, PERCEIVED_AFFINITY_CAP, PERCEIVED_AFFINITY_STEP)
from engrama.services.memory.topics import SYNONYMS, normalize_topic, plain_text

DAY = 86400.0
FORGET_AGE = 3 * DAY
FORGET_BELOW = 0.3
COMPACT_IMPORTANCE = 0.35
RECENCY_TAU = 7 * DAY

_BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes(
    id INTEGER PRIMARY KEY, t REAL, kind TEXT, summary TEXT,
    valence REAL, importance REAL, topic TEXT NULL);
CREATE TABLE IF NOT EXISTS facts(
    id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT,
    confidence REAL, source TEXT, t REAL);
CREATE TABLE IF NOT EXISTS topics(name TEXT PRIMARY KEY, affinity REAL, t REAL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
INSERT OR IGNORE INTO meta(k, v) VALUES('schema_version', '1');
CREATE TABLE IF NOT EXISTS app_categories(
    process TEXT PRIMARY KEY, category TEXT NOT NULL, source TEXT NOT NULL, t REAL NOT NULL DEFAULT 0);
"""

_V2_STATEMENTS = (
    "ALTER TABLE topics ADD COLUMN salience REAL NOT NULL DEFAULT 0",
    "ALTER TABLE topics ADD COLUMN t_salience REAL NOT NULL DEFAULT 0",
    "ALTER TABLE topics ADD COLUMN first_t REAL NOT NULL DEFAULT 0",
    "ALTER TABLE topics ADD COLUMN last_t REAL NOT NULL DEFAULT 0",
    "ALTER TABLE topics ADD COLUMN mentions INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE topics ADD COLUMN source TEXT NOT NULL DEFAULT 'chat'",
    "CREATE TABLE IF NOT EXISTS episode_links("
    " episode_id INTEGER, kind TEXT, ref TEXT)",
    "CREATE INDEX IF NOT EXISTS ix_links_ep ON episode_links(episode_id)",
    "CREATE INDEX IF NOT EXISTS ix_links_ref ON episode_links(kind, ref)",
    "CREATE TABLE IF NOT EXISTS opinions("
    " topic TEXT PRIMARY KEY, lean REAL NOT NULL DEFAULT 0,"
    " experience REAL NOT NULL DEFAULT 0, confidence REAL NOT NULL DEFAULT 0,"
    " phrase TEXT NULL, phrase_lang TEXT NULL, t REAL NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS blocklist("
    " kind TEXT, ref TEXT, t REAL, PRIMARY KEY(kind, ref))",
)

_PT_WORDS = frozenset("de da do que com nao uma um para meu minha foi sobre muito vez dia".split())
_EN_WORDS = frozenset("the and you with was about of to for a an my many day".split())

# (with topic, without topic) per kind and language.
_KIND_LABELS = {
    "chat": {"pt": ("conversa sobre", "conversa"), "en": ("talked about", "chatted")},
    "feed": {"pt": ("comeu", "comeu"), "en": ("ate", "ate")},
    "play": {"pt": ("brincou", "brincou"), "en": ("played", "played")},
    "sleep": {"pt": ("dormiu", "dormiu"), "en": ("slept", "slept")},
}


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


class MemoryStore:
    """SQLite-backed episodic and semantic memory (schema v2).

    The connection is shared across threads (``check_same_thread=False``);
    every operation runs under ``self._lock`` so callers may use the store
    from several threads at once.
    """

    schema_version = 2

    def __init__(self, db_path: Path, now_fn: Callable[[], float] = time.time) -> None:
        self._now = now_fn
        self._lock = threading.Lock()
        self._db = self._open(Path(db_path))

    def meta_get(self, k: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row[0] if row else None

    def meta_set(self, k: str, v: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (k, v))
            self._db.commit()

    # ---- open / migrate ------------------------------------------------
    def _open(self, path: Path) -> sqlite3.Connection:
        try:
            return self._init(path)
        except sqlite3.DatabaseError as exc:
            msg = str(exc).lower()
            if not any(m in msg for m in ("not a database", "malformed", "corrupt", "encrypted")):
                raise
        aside = path.with_name(f"{path.name}.corrupt-{int(self._now())}")
        os.replace(path, aside)
        return self._init(path)

    def _init(self, path: Path) -> sqlite3.Connection:
        db = sqlite3.connect(str(path), check_same_thread=False)
        try:
            db.executescript(_BASE_SCHEMA)
            row = db.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()
            if int(row[0]) < 2:
                self._migrate_v2(db)
            db.commit()
        except BaseException:
            db.close()
            raise
        return db

    @staticmethod
    def _migrate_v2(db: sqlite3.Connection) -> None:
        db.execute("BEGIN")
        try:
            for stmt in _V2_STATEMENTS:
                db.execute(stmt)
            merged: dict[str, list[float]] = {}
            for name, aff, t in db.execute("SELECT name, affinity, t FROM topics").fetchall():
                key = normalize_topic(name)
                if not key:
                    continue
                cur = merged.setdefault(key, [0.0, t, t])  # affinity, max t, min t
                cur[0] += aff or 0.0
                cur[1] = max(cur[1], t)
                cur[2] = min(cur[2], t)
            db.execute("DELETE FROM topics")
            for key, (aff, tmax, tmin) in merged.items():
                db.execute(
                    "INSERT INTO topics(name, affinity, t, salience, t_salience, first_t,"
                    " last_t, mentions, source) VALUES(?,?,?,?,?,?,?,?,?)",
                    (key, _clamp(aff), tmax, 0.0, tmax, tmin, tmax, 0, "chat"))
            db.execute("UPDATE meta SET v='2' WHERE k='schema_version'")
            db.commit()
        except BaseException:
            db.rollback()
            raise

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

    def retrieve(self, words: list[str], k: int = 5) -> list[str]:
        with self._lock:
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

    # ---- perceived themes (M5) ----------------------------------------
    def bump_perceived(self, theme: str, now: float) -> str:
        """Nudge a theme seen on the user's screen. Returns the topic key, or "" if
        silenced/blocked. Never stores anything but the extracted theme."""
        key = normalize_topic(theme)
        if not key:
            return ""
        with self._lock:
            if self._blocked("perceived", key) or self._blocked("topic", key):
                return ""
            row = self._db.execute(
                "SELECT affinity, salience, t_salience FROM topics WHERE name=?", (key,)).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO topics(name, affinity, t, salience, t_salience, first_t,"
                    " last_t, mentions, source) VALUES(?,?,?,?,?,?,?,?,?)",
                    (key, min(PERCEIVED_AFFINITY_CAP, PERCEIVED_AFFINITY_STEP), now, 0.5, now,
                     now, now, 1, "percepcao"))
            else:
                aff, sal, t_sal = row
                if aff < PERCEIVED_AFFINITY_CAP:
                    aff = min(PERCEIVED_AFFINITY_CAP, aff + PERCEIVED_AFFINITY_STEP)
                self._db.execute(
                    "UPDATE topics SET affinity=?, t=?, salience=?, t_salience=?, last_t=?,"
                    " mentions=mentions+1 WHERE name=?",
                    (aff, now, _decay(sal, t_sal, now) + 0.05, now, now, key))
            mk = f"activity_ep:{key}"
            last = self._db.execute("SELECT v FROM meta WHERE k=?", (mk,)).fetchone()
            due = last is None or now - float(last[0]) >= ACTIVITY_EPISODE_EVERY_S
            if due:
                self._db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (mk, repr(float(now))))
            self._db.commit()
        if due:
            self.add_episode("atividade", f"passou um tempo com {key}", 0.0, 0.2,
                             topic=key, topics=[key])
        return key

    def silence_theme(self, name: str) -> None:
        key = normalize_topic(name)
        if not key:
            return
        with self._lock:
            self._block("perceived", key, self._now())
            self._db.commit()

    def unsilence_theme(self, name: str) -> None:
        key = normalize_topic(name)
        with self._lock:
            self._db.execute("DELETE FROM blocklist WHERE kind='perceived' AND ref=?", (key,))
            self._db.commit()

    def silenced_themes(self) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ref FROM blocklist WHERE kind='perceived' ORDER BY ref").fetchall()
        return [r[0] for r in rows]

    # ---- app categories (M5) ------------------------------------------
    def app_category(self, process: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT category FROM app_categories WHERE process=?",
                ((process or "").strip().lower(),)).fetchone()
        return row[0] if row else None

    def set_app_category(self, process: str, category: str, source: str) -> bool:
        """Store a category; an LLM answer never overrides a user correction."""
        p = (process or "").strip().lower()
        if not p or not category:
            return False
        with self._lock:
            row = self._db.execute(
                "SELECT source FROM app_categories WHERE process=?", (p,)).fetchone()
            if row and row[0] == "user" and source != "user":
                return False
            self._db.execute(
                "INSERT OR REPLACE INTO app_categories(process, category, source, t) VALUES(?,?,?,?)",
                (p, category, source, self._now()))
            self._db.commit()
        return True

    def app_category_rows(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT process, category, source, t FROM app_categories ORDER BY process").fetchall()
        return [dict(process=p, category=c, source=s, t=t) for p, c, s, t in rows]

    def clear_app_categories(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM app_categories")
            self._db.commit()

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
            self._db.execute(
                "UPDATE opinions SET experience=0, confidence=0, phrase=NULL, phrase_lang=NULL")
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

    def close(self) -> None:
        with self._lock:
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
