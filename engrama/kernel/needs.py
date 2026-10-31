"""Needs (high = urge)."""
import numpy as np

from engrama import balance as B
from engrama.vocab import NEED_KEYS


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class Needs:
    def __init__(self, values: dict[str, float] | None = None):
        self.values: dict[str, float] = {k: 0.0 for k in NEED_KEYS}
        if values:
            for k, v in values.items():
                if k in self.values:
                    self.values[k] = _clamp(float(v))

    def decay(self, dt: float, awake: bool, interacting: bool) -> None:
        h = dt / B.HOUR
        v = self.values
        if awake:
            for k, rate in B.NEED_RATES_PER_H.items():
                if interacting and k in ("tedio", "carinho"):
                    continue
                v[k] = _clamp(v[k] + rate * h)
        else:
            v["sono"] = _clamp(v["sono"] - B.SLEEP_RECOVERY_PER_H * h)
            v["fome"] = _clamp(v["fome"] + B.NEED_RATES_PER_H["fome"] * 0.5 * h)

    def apply(self, delta: dict[str, float]) -> None:
        for k, d in delta.items():
            if k in self.values:
                self.values[k] = _clamp(self.values[k] + d)

    def top(self, n: int, threshold: float = 50) -> list[tuple[str, float]]:
        items = [(k, v) for k, v in self.values.items() if v >= threshold]
        items.sort(key=lambda kv: kv[1], reverse=True)
        return items[:n]

    def mean(self) -> float:
        return sum(self.values.values()) / len(self.values)

    def as_vector(self) -> np.ndarray:
        return np.array([self.values[k] for k in NEED_KEYS], dtype=np.float64) / 100.0

    def to_dict(self) -> dict:
        return {"values": dict(self.values)}

    @classmethod
    def from_dict(cls, d: dict) -> "Needs":
        return cls(d.get("values"))
