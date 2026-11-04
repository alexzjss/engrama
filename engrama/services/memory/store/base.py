from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np

from engrama.services.memory.topics import normalize_topic
from engrama.services.memory.store._util import (
    _clamp)

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

_V3_STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS vectors("
    " kind TEXT NOT NULL, ref TEXT NOT NULL, model TEXT NOT NULL, dim INTEGER NOT NULL,"
    " h TEXT NOT NULL, vec BLOB NOT NULL, t REAL NOT NULL, PRIMARY KEY(kind, ref))",
)


class BaseMixin:
    def __init__(self, db_path: Path, now_fn: Callable[[], float] = time.time) -> None:
        self._now = now_fn
        self._lock = threading.Lock()
        self._vec_version = 0
        self._vec_cache: dict[tuple[str, int], tuple[int, list[str], np.ndarray]] = {}
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
            db.execute("PRAGMA secure_delete = ON")
            db.executescript(_BASE_SCHEMA)
            row = db.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()
            if int(row[0]) < 2:
                self._migrate_v2(db)
                row = (2,)
            if int(row[0]) < 3:
                self._migrate_v3(db)
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

    @staticmethod
    def _migrate_v3(db: sqlite3.Connection) -> None:
        """v2 -> v3: add the vectors table only; no other table is touched."""
        db.execute("BEGIN")
        try:
            for stmt in _V3_STATEMENTS:
                db.execute(stmt)
            db.execute("UPDATE meta SET v='3' WHERE k='schema_version'")
            db.commit()
        except BaseException:
            db.rollback()
            raise

    def close(self) -> None:
        with self._lock:
            self._db.close()
