"""NeedDrives: sigmoid urgency per need."""
from __future__ import annotations
import numpy as np
import engrama.balance as B
from engrama.mind.contracts import Module, Blackboard, VizSpec
from engrama.vocab import NEED_KEYS

_MID = np.array([B.DRIVE_MIDPOINTS[k] for k in NEED_KEYS])


class NeedDrives(Module):
    reads = ("body.needs",)
    writes = ("drives",)
    rate_hz = 1.0

    def __init__(self, params: dict, rng) -> None:
        super().__init__(params, rng)
        self._last = np.zeros(len(NEED_KEYS))

    def step(self, bb: Blackboard, dt: float) -> None:
        n = bb.read("body.needs")
        self._last = 1.0 / (1.0 + np.exp(-(n - _MID) / B.DRIVE_SLOPE))
        bb.write("drives", self._last)

    def viz(self) -> list[VizSpec]:
        return [VizSpec("bars", "drives", {k: float(v) for k, v in zip(NEED_KEYS, self._last)})]
