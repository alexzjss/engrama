"""Off-policy evaluation of an arbiter policy from logged ticks (clipped IPS)."""
from __future__ import annotations
from typing import Callable, Iterable
from engrama.lab.explog import TickRow
from engrama.mind.contracts import reward_combine


def ips_estimate(rows: Iterable[TickRow], target_probs: Callable[[TickRow], dict[str, float]],
                 clip: float = 10.0) -> dict:
    rows = list(rows)
    ws: list[float] = []
    rs: list[float] = []
    for r, nxt in zip(rows, rows[1:]):
        pb = max(float(r.prob), 1e-12)
        ws.append(min(float(target_probs(r).get(r.action, 0.0)) / pb, clip))
        rs.append(reward_combine(nxt.rewards))
    n = len(ws)
    if n == 0:
        return {"value": 0.0, "logged_value": 0.0, "n": 0, "ess": 0.0}
    sw = sum(ws)
    sw2 = sum(w * w for w in ws)
    return {"value": sum(w * x for w, x in zip(ws, rs)) / n, "logged_value": sum(rs) / n, "n": n,
            "ess": sw * sw / sw2 if sw2 > 0 else 0.0}
