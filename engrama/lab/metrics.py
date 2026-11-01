"""Run metrics computed from experience-log rows."""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np
from engrama import balance as B
from engrama.lab.explog import TickRow
from engrama.vocab import ACTIONS

_PAIN = 0.9


def _weighted(samples: list[tuple[float, float]]) -> float:
    """samples = (t, value); each holds until the next; the last holds zero time."""
    tot = acc = 0.0
    for (t0, v), (t1, _) in zip(samples, samples[1:]):
        acc += v * (t1 - t0); tot += t1 - t0
    return acc / tot if tot > 0 else (samples[0][1] if samples else 0.0)


def compute_metrics(rows: Iterable[TickRow]) -> dict:
    ticks = 0
    total_dt = 0.0
    time_by_action: dict[str, float] = {}
    asks = ignored = answered = 0
    prev_ask_open = False
    pain: list[tuple[float, float]] = []
    pads: list[np.ndarray] = []
    surprise: list[float] = []
    agree: dict[str, list[int]] = {}
    for r in rows:
        ticks += 1; total_dt += r.dt
        time_by_action[r.action] = time_by_action.get(r.action, 0.0) + r.dt
        ign = r.rewards.get("ignored", 0.0) > 0
        ans = r.rewards.get("user_response", 0.0) > 0
        ignored += ign; answered += ans
        if r.action == "ask_attention":
            if not prev_ask_open:
                asks += 1
            prev_ask_open = not (ign or ans)
        else:
            prev_ask_open = False
        c = r.channels
        if "body.needs" in c:
            pain.append((r.t, 1.0 if float(np.max(c["body.needs"])) >= _PAIN else 0.0))
        if "affect.pad" in c:
            pads.append(np.asarray(c["affect.pad"], dtype=float))
        if "temporal.surprise" in c:
            surprise.append(float(c["temporal.surprise"][0]))
        by_mod: dict[str, tuple[float, str]] = {}
        for p in r.shadow:
            cur = by_mod.get(p["source"])
            if cur is None or p["score"] > cur[0]:
                by_mod[p["source"]] = (p["score"], p["action"])
        for m, (_, a) in by_mod.items():
            agree.setdefault(m, []).append(int(a == r.action))
    share = {a: t / total_dt for a, t in time_by_action.items()} if total_dt > 0 else {}
    entropy = -sum(s * math.log2(s) for s in share.values() if s > 0)
    pad = np.array(pads) if pads else np.zeros((0, 3))
    out = {
        "wellbeing": 1.0 - _weighted(pain) if pain else 1.0,
        "ask_count": asks,
        "ignored_rate": ignored / max(1, asks),
        "answered_rate": answered / max(1, asks),
        "behavior_entropy": entropy,
        "action_share": {a: share[a] for a in sorted(share, key=lambda x: ACTIONS.index(x) if x in ACTIONS else 99)},
        "pad_mean": [float(x) for x in pad.mean(axis=0)] if len(pad) else [0.0, 0.0, 0.0],
        "pad_std": [float(x) for x in pad.std(axis=0)] if len(pad) else [0.0, 0.0, 0.0],
        "shadow_agreement": {m: sum(v) / len(v) for m, v in sorted(agree.items())},
        "days_simulated": total_dt / (24 * B.HOUR),
        "ticks": ticks,
    }
    if surprise:
        out["surprise_mean"] = float(np.mean(surprise))
    return out
