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
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, recipe TEXT, seed INTEGER, started REAL,
  recipe_version INTEGER);
CREATE TABLE IF NOT EXISTS ticks(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, t REAL, dt REAL,
  action TEXT, prob REAL, rewards_json TEXT, events_json TEXT, proposals_json TEXT, shadow_json TEXT,
  decided INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS ix_ticks_run_t ON ticks(run_id, t);
CREATE TABLE IF NOT EXISTS channels(run_id TEXT, t REAL, name TEXT, blob BLOB);
CREATE INDEX IF NOT EXISTS ix_channels_run_t ON channels(run_id, t);
"""


def _enc(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def _dumps(o) -> str:
    return json.dumps(o, default=_enc)


def _prop(p: Proposal) -> dict:
    return {"action": p.action, "score": p.score, "reason": p.reason, "source": p.source}


class ExperienceLog:
    def __init__(self, path: Path, run_id: str, recipe: str, seed: int,
                 sample_s: float = B.EXPLOG_CHANNEL_SAMPLE_S, max_rows: int = B.EXPLOG_MAX_ROWS,
                 recipe_version: int | None = None) -> None:
        """run_id should be unique per run (the lab uses a uuid4); reopening an existing run_id resumes it."""
        self.run_id, self.sample_s, self.max_rows = run_id, sample_s, max_rows
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA temp_store=MEMORY")     # sorts / rotation never spill to %TEMP% on C:
        self._db.executescript(_SCHEMA)
        if "recipe_version" not in [r[1] for r in self._db.execute("PRAGMA table_info(runs)")]:
            self._db.execute("ALTER TABLE runs ADD COLUMN recipe_version INTEGER")
        self._db.execute("INSERT OR IGNORE INTO runs(run_id,recipe,seed,started,recipe_version) VALUES(?,?,?,?,?)",
                         (run_id, recipe, seed, time.time(), recipe_version))
        cols = [r[1] for r in self._db.execute("PRAGMA table_info(ticks)")]
        if "decided" not in cols:
            self._db.execute("ALTER TABLE ticks ADD COLUMN decided INTEGER NOT NULL DEFAULT 1")
        self._db.commit()
        self._rows = self._db.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
        self._last_sample = float("-inf")
        self._pending = 0

    def write(self, exp: Experience, proposals: list[Proposal], shadow: list[Proposal],
              decided: bool = True) -> None:
        events = [{"t": o.t, "kind": o.kind,
                   "data": {"private": True} if o.data.get("private") else dict(o.data)}
                  for o in exp.events]
        self._db.execute(
            "INSERT INTO ticks(run_id,t,dt,action,prob,rewards_json,events_json,proposals_json,shadow_json,decided)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, exp.t, exp.dt, exp.action, exp.action_prob, _dumps(exp.rewards),
             _dumps(events), _dumps([_prop(p) for p in proposals]),
             _dumps([_prop(p) for p in shadow]), int(decided)))
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
    decided: bool = True   # a fresh arbiter decision was made for this row's action
    # Note: `channels` (when sampled) are the blackboard as it stood before this tick's modules ran, i.e. the
    # state left by the previous tick, and `rewards` are the raw per-tick values: ask-window rewards sit on the
    # row where the window closed, not on the ask (see contracts.credit_rows for the credited view).


def list_runs(path: Path) -> list[dict]:
    db = sqlite3.connect(str(path))
    try:
        has_v = any(r[1] == "recipe_version" for r in db.execute("PRAGMA table_info(runs)"))
        cur = db.execute("SELECT run_id, recipe, seed, started, " + ("recipe_version" if has_v else "NULL")
                         + " FROM runs ORDER BY started, rowid")
        return [dict(zip(("run_id", "recipe", "seed", "started", "recipe_version"), r)) for r in cur]
    finally:
        db.close()


def run_identity(path: Path, run_id: str | None = None) -> dict:
    """{run_id, recipe, recipe_version} of a logged run (the latest one by default)."""
    runs = list_runs(path)
    if run_id is not None:
        runs = [r for r in runs if r["run_id"] == run_id]
    if not runs:
        return {}
    r = runs[-1]
    return {"run_id": r["run_id"], "recipe": r["recipe"], "recipe_version": r["recipe_version"]}


def read_log(path: Path, run_id: str | None = None) -> Iterator[TickRow]:
    runs = list_runs(path)
    if run_id is None:
        if not runs:
            return
        run_id = runs[-1]["run_id"]
    db = sqlite3.connect(str(path))
    try:
        chan_cur = db.execute("SELECT t, name, blob FROM channels WHERE run_id=? ORDER BY t, rowid", (run_id,))
        ahead = chan_cur.fetchone()
        group_t: float | None = None
        group: dict[str, np.ndarray] = {}
        has_dec = any(r[1] == "decided" for r in db.execute("PRAGMA table_info(ticks)"))
        cur = db.execute("SELECT t,dt,action,prob,rewards_json,events_json,proposals_json,shadow_json,"
                         + ("decided" if has_dec else "1") + " FROM ticks WHERE run_id=? ORDER BY t, id", (run_id,))
        for t, dt, action, prob, rw, ev, pr, sh, dec in cur:
            if group_t != t:
                group_t, group = t, {}
                while ahead is not None and ahead[0] < t:
                    ahead = chan_cur.fetchone()
                while ahead is not None and ahead[0] == t:
                    group[ahead[1]] = np.frombuffer(ahead[2], dtype=np.float32).copy()
                    ahead = chan_cur.fetchone()
            yield TickRow(t, dt, action, prob, json.loads(rw), json.loads(ev), json.loads(pr),
                          json.loads(sh), dict(group), bool(dec))
    finally:
        db.close()
