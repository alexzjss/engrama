"""FoodPrefs: per-creature food likings shaped by novelty-seeking and comfort."""
from __future__ import annotations
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Module, Blackboard, VizSpec
from engrama.mind.helpers import read_traits
from engrama.vocab import FOOD_IDS


class FoodPrefs(Module):
    reads = ("traits",)
    writes = ("prefs.food",)
    rate_hz = 1.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.liking = np.clip(rng.normal(0.0, B.FOOD_LIKING_INIT_SD, len(FOOD_IDS)), -1, 1)
        self.counts = np.zeros(len(FOOD_IDS), dtype=np.int64)

    def step(self, bb: Blackboard, dt: float) -> None:
        for ev in bb.events:
            if ev.kind != "food" or ev.data.get("food") not in FOOD_IDS:
                continue
            i = FOOD_IDS.index(ev.data["food"])
            tr = read_traits(bb)
            if self.counts[i] < B.FOOD_NOVELTY_COUNT:
                d = B.FOOD_NOVELTY_GAIN * (tr["curiosidade"] - 0.5)
            else:
                d = B.FOOD_COMFORT_GAIN * (tr["paciencia"] - 0.5)
            self.liking[i] = np.clip(self.liking[i] + d + self.rng.normal(0.0, B.FOOD_NOISE_SD), -1, 1)
            self.counts[i] += 1
        bb.write("prefs.food", self.liking)

    def state_dict(self) -> dict:
        return {"liking": self.liking.copy(), "counts": self.counts.copy()}

    def load_state_dict(self, d: dict) -> None:
        self.liking = np.array(d["liking"], dtype=np.float64).reshape(len(FOOD_IDS))
        self.counts = np.array(d["counts"], dtype=np.int64).reshape(len(FOOD_IDS))

    def viz(self) -> list[VizSpec]:
        return [VizSpec("bars", "Gosto por comida", dict(zip(FOOD_IDS, self.liking.tolist())))]
