"""SQLite experience log: ticks, sampled channel snapshots, privacy redaction, rotation."""
from __future__ import annotations
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Experience, Proposal

_COMMIT_EVERY = 500
_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, recipe TEXT, seed INTEGER, started REAL);
CREATE TABLE IF NOT EXISTS ticks(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, t REAL, dt REAL,
  action TEXT, prob REAL, rewards_json TEXT, events_json TEXT, proposals_json TEXT, shadow_json TEXT);
CREATE INDEX IF NOT EXISTS ix_ticks_run_t ON ticks(run_id, t);
CREATE TABLE IF NOT EXISTS channels(run_id TEXT, t REAL, name TEXT, blob BLOB);
CREATE INDEX IF NOT EXISTS ix_channels_run_t ON channels(run_id, t);
"""


def _prop(p: Proposal) -> dict:
    return {"action": p.action, "score": p.score, "reason": p.reason, "source": p.source}


class ExperienceLog:
    def __init__(self, path: Path, run_id: str, recipe: str, seed: int,
                 sample_s: float = B.EXPLOG_CHANNEL_SAMPLE_S, max_rows: int = B.EXPLOG_MAX_ROWS) -> None:
        self.run_id, self.sample_s, self.max_rows = run_id, sample_s, max_rows
        self._db = sqlite3.connect(str(path))
        self._db.executescript(_SCHEMA)
        self._db.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?,?)", (run_id, recipe, seed, time.time()))
        self._db.commit()
        self._rows = self._db.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
        self._last_sample = float("-inf")
        self._pending = 0

    def write(self, exp: Experience, proposals: list[Proposal], shadow: list[Proposal]) -> None:
        events = [{"t": o.t, "kind": o.kind,
                   "data": {"private": True} if o.data.get("private") else dict(o.data)}
                  for o in exp.events]
        self._db.execute(
            "INSERT INTO ticks(run_id,t,dt,action,prob,rewards_json,events_json,proposals_json,shadow_json)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (self.run_id, exp.t, exp.dt, exp.action, exp.action_prob, json.dumps(exp.rewards),
             json.dumps(events), json.dumps([_prop(p) for p in proposals]),
             json.dumps([_prop(p) for p in shadow])))
        self._rows += 1
        if exp.events or exp.t - self._last_sample >= self.sample_s:
            self._last_sample = exp.t
            self._db.executemany(
                "INSERT INTO channels VALUES(?,?,?,?)",
                [(self.run_id, exp.t, n, np.asarray(v, dtype=np.float32).tobytes())
                 for n, v in exp.channels.items()])
        if self._rows > self.max_rows:
            self._rotate()
        self._pending += 1
        if self._pending >= _COMMIT_EVERY:
            self._db.commit()
            self._pending = 0

    def _rotate(self) -> None:
        n = max(1, self._rows // 10)
        cur = self._db.execute("DELETE FROM ticks WHERE id IN (SELECT id FROM ticks ORDER BY id LIMIT ?)", (n,))
        self._rows -= cur.rowcount
        self._db.execute(
            "DELETE FROM channels WHERE t < COALESCE("
            "(SELECT MIN(t) FROM ticks WHERE ticks.run_id = channels.run_id), 1e308)")

    def close(self) -> None:
        self._db.commit()
        self._db.close()


@dataclass(frozen=True)
class TickRow:
    t: float
    dt: float
    action: str
    prob: float
    rewards: dict
    events: list[dict]
    proposals: list[dict]
    shadow: list[dict]
    channels: dict[str, np.ndarray]


def list_runs(path: Path) -> list[dict]:
    db = sqlite3.connect(str(path))
    try:
        cur = db.execute("SELECT run_id, recipe, seed, started FROM runs ORDER BY started, rowid")
        return [dict(zip(("run_id", "recipe", "seed", "started"), r)) for r in cur]
    finally:
        db.close()


def read_log(path: Path, run_id: str | None = None) -> Iterator[TickRow]:
    runs = list_runs(path)
    if run_id is None:
        if not runs:
            return
        run_id = runs[-1]["run_id"]
    db = sqlite3.connect(str(path))
    try:
        chans: dict[float, dict[str, np.ndarray]] = {}
        for t, name, blob in db.execute("SELECT t, name, blob FROM channels WHERE run_id=?", (run_id,)):
            chans.setdefault(t, {})[name] = np.frombuffer(blob, dtype=np.float32).copy()
        cur = db.execute("SELECT t,dt,action,prob,rewards_json,events_json,proposals_json,shadow_json"
                         " FROM ticks WHERE run_id=? ORDER BY t, id", (run_id,))
        for t, dt, action, prob, rw, ev, pr, sh in cur:
            yield TickRow(t, dt, action, prob, json.loads(rw), json.loads(ev), json.loads(pr),
                          json.loads(sh), chans.get(t, {}))
    finally:
        db.close()
