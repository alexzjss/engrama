"""Primitive reward signals derived from kernel events and need changes."""
import numpy as np

from engrama.balance import ASK_ANSWER_WINDOW
from engrama.kernel.sensors import Obs
from engrama.vocab import REWARD_KEYS

_ANSWERS = ("answered", "message", "pet", "click")
PAIN_LEVEL = 0.8
RELIEF_FLOOR = 0.5


class RewardTracker:
    def __init__(self) -> None:
        self._ask_t: float | None = None
        self._acc = {k: 0.0 for k in REWARD_KEYS}

    def on_action_started(self, action: str, t: float) -> None:
        if action == "ask_attention":
            self._ask_t = t

    def on_events(self, events: list[Obs], t: float) -> None:
        for e in events:
            if e.kind == "pet":
                self._acc["petting"] += 1.0
            elif e.kind == "message":
                self._acc["msg_valence"] += float(e.data.get("valence", 0.0))
            if (e.kind in _ANSWERS and self._ask_t is not None
                    and 0.0 <= e.t - self._ask_t <= ASK_ANSWER_WINDOW):
                self._acc["user_response"] = 1.0
                self._ask_t = None

    def on_needs(self, before: np.ndarray, after: np.ndarray, dt: float) -> None:
        drop = before - after
        self._acc["need_relief"] += float(drop[(before >= RELIEF_FLOOR) & (drop > 0)].sum())
        crossed = (before < PAIN_LEVEL) & (after >= PAIN_LEVEL)
        self._acc["need_pain"] += float(crossed.sum())

    def on_novel(self) -> None:
        self._acc["novelty"] += 1.0

    def collect(self, t: float) -> dict[str, float]:
        out = dict(self._acc)
        if self._ask_t is not None and t - self._ask_t > ASK_ANSWER_WINDOW:
            out["ignored"] = 1.0
            self._ask_t = None
        self._acc = {k: 0.0 for k in REWARD_KEYS}
        return out

    def to_dict(self) -> dict:
        return {"ask_t": self._ask_t, "acc": dict(self._acc)}

    @classmethod
    def from_dict(cls, d: dict) -> "RewardTracker":
        r = cls()
        r._ask_t = d["ask_t"]
        r._acc = {k: float(d["acc"][k]) for k in REWARD_KEYS}
        return r
