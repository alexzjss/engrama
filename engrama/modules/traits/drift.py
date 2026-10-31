"""TraitDrift: slow, daily-capped personality drift driven by experience."""
from __future__ import annotations
import math
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Module, Blackboard, Experience, VizSpec
from engrama.vocab import TRAIT_KEYS, INITIAL_TRAITS


class TraitDrift(Module):
    reads = ()
    writes = ("traits",)
    rate_hz = 1.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.traits = {k: float(INITIAL_TRAITS[k]) for k in TRAIT_KEYS}   # trait points 0..100
        self.day = 0
        self.used = {k: 0.0 for k in TRAIT_KEYS}

    @staticmethod
    def _nudges(exp: Experience) -> list[tuple[str, float]]:
        r, out = exp.rewards, []
        if r.get("user_response", 0.0) > 0:
            out.append(("sociabilidade", 0.5))
        if r.get("ignored", 0.0) > 0:
            out += [("independencia", 0.3), ("sociabilidade", -0.2)]
        if r.get("novelty", 0.0) > 0 and exp.action in ("explore", "show_something"):
            out.append(("curiosidade", 0.3))
        if r.get("need_relief", 0.0) > 0 and exp.action == "play_alone":
            out.append(("criatividade", 0.1))
        if r.get("petting", 0.0) > 0:
            out.append(("paciencia", 0.05))
        return out

    def learn(self, exp: Experience) -> None:
        day = int(math.floor(exp.t / 86400.0))
        if day != self.day:
            self.day = day
            self.used = {k: 0.0 for k in TRAIT_KEYS}
        for k, d in self._nudges(exp):
            room = max(B.TRAIT_MAX_DRIFT_PER_DAY - self.used[k], 0.0)
            new = min(100.0, max(0.0, self.traits[k] + math.copysign(min(abs(d), room), d)))
            self.used[k] += abs(new - self.traits[k])
            self.traits[k] = new

    def step(self, bb: Blackboard, dt: float) -> None:
        bb.write("traits", [self.traits[k] / 100.0 for k in TRAIT_KEYS])

    def state_dict(self) -> dict:
        return {"traits": dict(self.traits), "day": self.day, "used": dict(self.used)}

    def load_state_dict(self, d: dict) -> None:
        self.traits = {k: float(d["traits"][k]) for k in TRAIT_KEYS}
        self.day = int(d["day"])
        self.used = {k: float(d["used"][k]) for k in TRAIT_KEYS}

    def viz(self) -> list[VizSpec]:
        return [VizSpec("bars", "Traços", dict(self.traits))]
