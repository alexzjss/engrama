"""Softmax arbiter over weighted module proposals."""
from __future__ import annotations
import numpy as np
from engrama.mind.contracts import Blackboard, Proposal
from engrama.vocab import TRAIT_KEYS

class SoftmaxArbiter:
    def __init__(self, weights: dict[str, float], temperature: float = 1.0, trait_temperature: bool = True) -> None:
        self.weights = dict(weights); self.temperature = temperature; self.trait_temperature = trait_temperature

    def _temp(self, bb: Blackboard) -> float:
        t = self.temperature
        if self.trait_temperature and bb.has("traits"):
            t *= 0.5 + float(bb.read("traits")[TRAIT_KEYS.index("curiosidade")])
        return max(t, 1e-6)

    def choose(self, proposals: list[Proposal], available: tuple[str, ...], bb: Blackboard,
               rng: np.random.Generator) -> tuple[str | None, float, dict[str, float]]:
        scores: dict[str, float] = {}
        for p in proposals:
            if p.action in available:
                scores[p.action] = scores.get(p.action, 0.0) + self.weights.get(p.source, 1.0) * p.score
        if not scores:
            return None, 1.0, {}
        acts = [a for a in available if a in scores]
        z = np.array([scores[a] for a in acts]) / self._temp(bb)
        e = np.exp(z - z.max())
        probs = e / e.sum()
        i = int(rng.choice(len(acts), p=probs))
        pd = {a: float(p) for a, p in zip(acts, probs)}
        return acts[i], pd[acts[i]], pd
