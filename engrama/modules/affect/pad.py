"""PadAffect: pleasure/arousal/dominance with trait baseline, decay and appraisal."""
from __future__ import annotations
from collections import deque
import numpy as np
import engrama.balance as B
from engrama.mind.contracts import Module, Blackboard, VizSpec
from engrama.mind.helpers import default_traits, read_traits
from engrama.vocab import NEED_KEYS

_SERIES_LEN = 300


def baseline(tr: dict[str, float]) -> np.ndarray:
    return np.array([0.1 + 0.2 * (tr["sociabilidade"] - 0.5),
                     0.2 * (tr["curiosidade"] - 0.5),
                     0.3 * (tr["independencia"] - 0.5)])


def pad_label(pad) -> str:
    p = np.asarray(pad, dtype=float)
    if float(np.linalg.norm(p)) < B.PAD_NEUTRAL_RADIUS:
        return "neutral"
    key = "".join("+" if x >= 0 else "-" for x in p)
    return {"+++": "exuberant", "++-": "excited", "+-+": "relaxed", "+--": "content",
            "-++": "angry", "-+-": "anxious", "--+": "bored", "---": "sad"}[key]


class PadAffect(Module):
    reads = ("drives", "traits", "temporal.surprise")
    writes = ("affect.pad",)
    rate_hz = 1.0

    def __init__(self, params: dict, rng) -> None:
        super().__init__(params, rng)
        self.pad = baseline(default_traits())
        self._series: deque = deque(maxlen=_SERIES_LEN)

    def step(self, bb: Blackboard, dt: float) -> None:
        tr = read_traits(bb)
        base = baseline(tr)
        k = 0.5 ** (dt / B.PAD_HALF_LIFE_S)
        pad = base + (self.pad - base) * k
        arousal_scale = 1.2 - tr["paciencia"]
        for ev in bb.events:
            ap = B.APPRAISAL.get(ev.kind)
            if ap is None:
                continue
            dp, da, dd = ap
            if ev.kind == "message":
                dp *= float(ev.data.get("valence", 0.0))
            pad += np.array([dp, da * arousal_scale, dd])
        drives = bb.get("drives")
        if drives is not None:
            h = dt / B.HOUR
            pad[0] -= B.PAD_PRESSURE_P_PER_H * float(np.max(drives)) * h
            pad[1] += B.PAD_PRESSURE_A_PER_H * float(
                drives[NEED_KEYS.index("tedio")] - drives[NEED_KEYS.index("sono")]) * h
        s = bb.get("temporal.surprise")
        if s is not None:
            pad[1] += B.PAD_SURPRISE_GAIN * float(s[0]) * dt / 60.0
        self.pad = np.clip(pad, -1.0, 1.0)
        bb.write("affect.pad", self.pad)
        self._series.append((bb.t, *map(float, self.pad)))

    def state_dict(self) -> dict:
        return {"pad": [float(x) for x in self.pad]}

    def load_state_dict(self, d: dict) -> None:
        self.pad = np.array(d["pad"], dtype=float)

    def viz(self) -> list[VizSpec]:
        return [VizSpec("pad3d", "pad", {"pad": [float(x) for x in self.pad], "label": pad_label(self.pad)}),
                VizSpec("series", "pad history", {"names": ["P", "A", "D"], "rows": list(self._series)})]
