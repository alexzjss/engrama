"""Digital requests (M7): the creature sometimes asks for a joke maintenance item. Pure UI/host state, no pygame."""
from __future__ import annotations
import random
from engrama import balance, vocab


class DigitalRequests:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(int(seed))
        self.open: str = ""
        self.opened_t: float = 0.0
        self.last_t: float | None = None     # when the last request opened (None = never)

    def tick(self, t: float) -> None:
        if self.open and t - self.opened_t >= balance.DIGITAL_REQUEST_TTL_S:
            self.open = ""

    def on_action_start(self, action: str, t: float) -> str:
        self.tick(t)
        if action != "ask_attention" or self.open:
            return ""
        if self.last_t is not None and t - self.last_t < balance.DIGITAL_REQUEST_MIN_GAP_S:
            return ""
        if self._rng.random() >= balance.DIGITAL_REQUEST_P:
            return ""
        self.open = self._rng.choice(vocab.DIGITAL_IDS)
        self.opened_t = self.last_t = t
        return self.open

    def fulfill(self, id: str, t: float) -> bool:
        self.tick(t)
        if self.open and id == self.open:
            self.open = ""
            return True
        return False

    def state_dict(self) -> dict:
        v, internal, gauss = self._rng.getstate()
        return {"open": self.open, "opened_t": self.opened_t, "last_t": self.last_t,
                "rng": [v, list(internal), gauss]}

    def load_state_dict(self, d: dict) -> None:
        d = d or {}
        op = d.get("open", "")
        self.open = op if op in vocab.DIGITAL_IDS else ""
        self.opened_t = float(d.get("opened_t", 0.0))
        lt = d.get("last_t")
        self.last_t = None if lt is None else float(lt)
        r = d.get("rng")
        if r:
            try:
                self._rng.setstate((r[0], tuple(r[1]), r[2]))
            except (TypeError, ValueError, IndexError):
                pass
