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
    # Tick 0 is never logged (the log starts one tick behind); prime the module with an event-free
    # step on the first logged channels so stateful modules start from the live trajectory.
    if rows and per_row[0]:
        mod.step(_board(per_row[0], TickRow(rows[0].t, rows[0].dt, "", 1.0, {}, [], [], [], {})), rows[0].dt)
    # Live order per tick j: learn(exp_j), then step with tick j's events/dt on the channels as they
    # stand after tick j's step (= the channels logged on row j+1). Outputs are stamped with row j+1's t,
    # so they line up with the logged channels at sampled rows.
    for j in range(len(rows) - 1):
        r, board_ch = rows[j], per_row[j + 1]
        if not board_ch or not per_row[j]:
            continue
        evs = _board(board_ch, r).events
        mod.learn(Experience(r.t, r.dt, evs, per_row[j], r.action, r.prob, r.rewards, board_ch))
        bb = _board(board_ch, r)
        mod.step(bb, r.dt)
        out["t"].append(rows[j + 1].t)
        for c in mod.writes:
            v = bb.get(c)
            out[c].append(None if v is None else v.tolist())
        props = mod.propose(bb)
        out["proposals_top"].append(max(props, key=lambda p: p.score).action if props else None)
    return out
