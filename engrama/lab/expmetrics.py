"""Comparison metrics that live only in the experiment suite (compute_metrics stays pinned by its fixture).

Modules may expose an optional ``lab_metrics(self) -> dict`` (duck typing, outside the Module contract):
numeric values (or nested dicts of numbers) describing the life that is ending. Anything else is ignored."""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np
from engrama import balance as B
from engrama.lab.explog import TickRow
from engrama.mind.contracts import credit_rows
from engrama.vocab import EVENT_KINDS

_EXPECT = "temporal.expectation"
_ERROR = "world.error"
_DAY = 24 * B.HOUR


def _is_num(x) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, (bool, np.bool_)) \
        and math.isfinite(float(x))


def _flatten(d: dict, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "/"))
        elif _is_num(v):
            out[key] = float(v)
    return out


class Probe:
    """Reads the blackboard tick by tick: next-bin Brier, need satisfaction, world error, module metrics."""

    def __init__(self, start_t: float, days: float) -> None:
        self._half_t = start_t + days * _DAY / 2.0
        self._prev_t = start_t
        self._prev_exp: dict[str, np.ndarray] = {}
        self._brier: dict[str, list[float]] = {}
        self._err: dict[str, list[float]] = {}
        self._sat_acc = self._sat_w = 0.0
        self._sat_last = None
        self._life_ticks = 0
        self._lab: dict[str, dict[str, list[float]]] = {}   # module -> key -> [sum(w*v), sum(w)]

    def after_tick(self, rt, reborn: bool) -> None:
        """reborn: this tick is the first of a new life; the previous expectation belongs to the old one."""
        bb = rt.bb
        t = float(bb.t)
        w = max(0.0, t - self._prev_t)
        self._prev_t = t
        self._life_ticks += 1
        needs = bb.get("body.needs")
        if needs is not None:
            s = 1.0 - float(np.mean(needs))
            self._sat_acc += s * w; self._sat_w += w; self._sat_last = s
        kinds = {o.kind for o in bb.events}
        y = np.array([1.0 if k in kinds else 0.0 for k in EVENT_KINDS])
        snap = bb.snapshot()
        cur: dict[str, np.ndarray] = {}
        for name, v in snap.items():
            if name.endswith(_EXPECT):
                cur[name] = np.asarray(v, dtype=float)
                prev = self._prev_exp.get(name)
                if prev is not None and not reborn and t >= self._half_t:
                    self._brier.setdefault(name, []).append(float(np.mean((prev - y) ** 2)))
            elif name.endswith(_ERROR):
                self._err.setdefault(name, []).append(float(np.asarray(v, dtype=float)[0]))
        self._prev_exp = cur

    def _collect(self, rt) -> None:
        n = self._life_ticks
        self._life_ticks = 0
        if n <= 0:
            return
        for name, mod in rt.scheduler.modules().items():
            fn = getattr(mod, "lab_metrics", None)
            if not callable(fn):
                continue
            try:
                got = fn()
            except Exception:
                continue
            if not isinstance(got, dict):
                continue
            acc = self._lab.setdefault(name, {})
            for k, v in _flatten(got).items():
                a = acc.setdefault(k, [0.0, 0.0])
                a[0] += v * n; a[1] += n

    def before_rebirth(self, rt) -> None:
        self._collect(rt)

    def result(self, rt) -> dict:
        self._collect(rt)
        sat = self._sat_acc / self._sat_w if self._sat_w > 0 else (self._sat_last if self._sat_last is not None else 1.0)
        return {"pred_brier": {k: float(np.mean(v)) for k, v in sorted(self._brier.items())},
                "need_satisfaction": float(sat),
                "world_error_mean": {k: float(np.mean(v)) for k, v in sorted(self._err.items())},
                "lab_metrics": {m: {k: a[0] / a[1] for k, a in sorted(d.items())}
                                for m, d in sorted(self._lab.items()) if d}}


def experiment_metrics(rows: Iterable[TickRow], days: float) -> dict:
    rows = list(rows)
    days = max(days, 1e-12)
    credited = credit_rows((r.action, r.rewards) for r in rows)
    decided = [r.action for r in rows if r.decided]
    counts: dict[str, int] = {}
    for a in decided:
        counts[a] = counts.get(a, 0) + 1
    n = len(decided)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values()) if n else 0.0
    switches = sum(a != b for a, b in zip(decided, decided[1:]))
    return {"return_per_day": float(sum(credited)) / days,
            "novelty_per_day": float(sum(r.rewards.get("novelty", 0.0) for r in rows)) / days,
            "decision_entropy": entropy,
            "switch_rate": switches / (n - 1) if n > 1 else 0.0}
