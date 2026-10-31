"""QLearningPolicy: tabular Q over hour bucket x user_active x PAD quadrant."""
from __future__ import annotations
import math
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Module, Blackboard, Proposal, Experience, VizSpec, reward_combine
from engrama.vocab import ACTIONS

N_STATES = 32


def context(ch: dict[str, np.ndarray]) -> tuple[int, int, int]:
    """(hour_bucket 0..3, active 0/1, quadrant 0..3); missing channels count as 0."""
    h = ch.get("world.hour", np.zeros(2))
    hours = (math.atan2(float(h[0]), float(h[1])) / (2 * math.pi) * 24.0) % 24.0
    bucket = min(3, int(hours // 6))
    active = int(float(ch.get("world.user_active", np.zeros(1))[0]) >= 0.5)
    pad = ch.get("affect.pad", np.zeros(3))
    quad = (0 if float(pad[0]) >= 0 else 2) + (0 if float(pad[1]) >= 0 else 1)
    return bucket, active, quad


def state_index(ch: dict[str, np.ndarray]) -> int:
    """Bijection: hour_bucket*8 + active*4 + quadrant (quadrant = 2*(P<0) + (A<0))."""
    b, a, q = context(ch)
    return b * 8 + a * 4 + q


class QLearningPolicy(Module):
    reads = ("world.hour", "world.user_active", "affect.pad")
    writes = ()
    rate_hz = 1.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.alpha = float(self.params.get("alpha", B.QL_ALPHA))
        self.gamma = float(self.params.get("gamma", B.QL_GAMMA))
        self.Q = np.zeros((N_STATES, len(ACTIONS)))
        self.visits = np.zeros((N_STATES, len(ACTIONS)), dtype=np.int64)

    def learn(self, exp: Experience) -> None:
        if exp.action not in ACTIONS:
            return
        s, a = state_index(exp.channels), ACTIONS.index(exp.action)
        s2 = state_index(exp.next_channels)
        r = reward_combine(exp.rewards)
        self.Q[s, a] += self.alpha * (r + self.gamma * self.Q[s2].max() - self.Q[s, a])
        self.visits[s, a] += 1

    def propose(self, bb: Blackboard) -> list[Proposal]:
        ch = bb.snapshot()
        s = state_index(ch)
        b, act, _ = context(ch)
        reason = f"aprendi: {b}/{act}"
        return [Proposal(a, float(self.Q[s, ACTIONS.index(a)]), reason)
                for a in bb.available_actions if a in ACTIONS]

    def state_dict(self) -> dict:
        return {"Q": self.Q.copy(), "visits": self.visits.copy()}

    def load_state_dict(self, d: dict) -> None:
        self.Q = np.array(d["Q"], dtype=np.float64).reshape(N_STATES, len(ACTIONS))
        self.visits = np.array(d["visits"], dtype=np.int64).reshape(N_STATES, len(ACTIONS))

    def viz(self) -> list[VizSpec]:
        return [VizSpec("heatmap", "Q (estado x ação)", self.Q.tolist())]
