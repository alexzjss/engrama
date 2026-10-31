"""Replay a logged run through a single module, offline."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from engrama.lab.explog import TickRow, read_log
from engrama.mind import registry
from engrama.mind.contracts import Blackboard, Experience, Observation
from engrama.mind.recipe import ModuleSpec
from engrama.vocab import ACTIONS


def _board(chans: dict[str, np.ndarray], row: TickRow) -> Blackboard:
    bb = Blackboard()
    for n, v in chans.items():
        bb.write(n, v)
    bb.events = tuple(Observation(float(e.get("t", row.t)), e["kind"], dict(e.get("data", {})))
                      for e in row.events)
    bb.t, bb.available_actions = row.t, ACTIONS
    return bb


def replay_module(log_path: Path, spec: ModuleSpec, seed: int = 0,
                  run_id: str | None = None) -> dict[str, list]:
    rows = list(read_log(Path(log_path), run_id))
    mod = registry.build(spec, np.random.default_rng([seed, 2]))
    carried: dict[str, np.ndarray] = {}
    per_row: list[dict[str, np.ndarray]] = []
    for r in rows:
        if r.channels:
            carried = {n: v.astype(np.float64) for n, v in r.channels.items()}
        per_row.append(dict(carried))
    out: dict[str, list] = {"t": []}
    for c in mod.writes:
        out[c] = []
    out["proposals_top"] = []
    for i, r in enumerate(rows):
        if not per_row[i]:
            continue
        bb = _board(per_row[i], r)
        mod.step(bb, r.dt)
        out["t"].append(r.t)
        for c in mod.writes:
            v = bb.get(c)
            out[c].append(None if v is None else v.tolist())
        props = mod.propose(bb)
        out["proposals_top"].append(max(props, key=lambda p: p.score).action if props else None)
        if i + 1 < len(rows) and per_row[i + 1]:
            mod.learn(Experience(r.t, r.dt, bb.events, per_row[i], r.action, r.prob, r.rewards,
                                 per_row[i + 1]))
    return out
