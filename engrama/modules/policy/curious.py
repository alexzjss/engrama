"""CuriousQPolicy: Q-learning plus an intrinsic bonus from the world model's prediction error.

The bonus of a transition is credited one tick late: world.error in e_{t+1}.channels is the error of e_t,
so e_t is held until e_{t+1} arrives. Credit experiences (dt <= 0) are applied at once, with no bonus.
"""
from __future__ import annotations
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Experience, Proposal, Blackboard, VizSpec, reward_combine
from engrama.modules.policy.qlearning import QLearningPolicy, state_index
from engrama.vocab import ACTIONS


class CuriousQPolicy(QLearningPolicy):
    reads = QLearningPolicy.reads + ("world.error",)

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.beta = float(self.params.get("beta", B.CUR_BETA))
        self.mode = str(self.params.get("bonus", "surprise"))
        if self.mode not in ("surprise", "progress"):
            raise ValueError(f"unknown bonus mode {self.mode!r}")
        self.error_channel = str(self.params.get("error_channel", "world.error"))
        self._init()

    def _init(self) -> None:
        self.held: tuple[int, int, int, float] | None = None
        self.baseline = 0.0
        self.fast = np.zeros(len(ACTIONS))
        self.slow = np.zeros(len(ACTIONS))
        self.sum_b = 0.0
        self.sum_r = 0.0
        self.n_b = 0
        self._last_b = 0.0
        self._hist: list[float] = []

    def _td(self, s: int, a: int, s2: int, r: float) -> None:
        self.Q[s, a] += self.alpha * (r + self.gamma * self.Q[s2].max() - self.Q[s, a])
        self.visits[s, a] += 1

    def _bonus(self, a0: int, err: float) -> float:
        if self.mode == "surprise":
            b = float(np.clip(err - self.baseline, 0.0, 1.0))
            self.baseline += (1.0 - B.CUR_BASELINE_EMA) * (err - self.baseline)
            return b
        self.fast[a0] += (1.0 - B.CUR_LP_FAST) * (err - self.fast[a0])
        self.slow[a0] += (1.0 - B.CUR_LP_SLOW) * (err - self.slow[a0])
        return float(np.clip(self.slow[a0] - self.fast[a0], 0.0, 1.0))

    def learn(self, exp: Experience) -> None:
        if exp.action not in ACTIONS:
            return
        s, a = state_index(exp.channels), ACTIONS.index(exp.action)
        s2 = state_index(exp.next_channels)
        r = reward_combine(exp.rewards)
        if exp.dt <= 0:   # ask-window credit: immediate, no bonus
            self._td(s, a, s2, r)
            return
        if self.held is not None:
            s0, a0, s20, r0 = self.held
            err = exp.channels.get(self.error_channel)
            b = self._bonus(a0, float(err[0])) if err is not None else 0.0
            self._td(s0, a0, s20, r0 + self.beta * b)
            self.sum_b += b
            self.sum_r += abs(r0)
            self.n_b += 1
            self._last_b = b
            self._hist.append(b)
            if len(self._hist) > 200:
                del self._hist[:-200]
        self.held = (s, a, s2, r)

    def propose(self, bb: Blackboard) -> list[Proposal]:
        props = super().propose(bb)
        reason = f"aprendi + curiosidade: {self._last_b:.2f}"
        return [Proposal(p.action, p.score, f"{reason}/{p.action}") for p in props]

    def lab_metrics(self) -> dict:
        tot = self.sum_r + self.beta * self.sum_b
        return {"bonus_mean": self.sum_b / self.n_b if self.n_b else 0.0,
                "bonus_share": self.beta * self.sum_b / tot if tot > 0 else 0.0}

    def state_dict(self) -> dict:
        d = super().state_dict()
        d.update({"version": B.M10_STATE_VERSION,
                  "held": None if self.held is None else [self.held[0], self.held[1], self.held[2], self.held[3]],
                  "baseline": self.baseline, "fast": self.fast.copy(), "slow": self.slow.copy(),
                  "sum_b": self.sum_b, "sum_r": self.sum_r, "n_b": self.n_b, "last_b": self._last_b,
                  "hist": list(self._hist)})
        return d

    def load_state_dict(self, d: dict) -> None:
        if not d:
            return
        v = int(d.get("version", B.M10_STATE_VERSION))
        if v > B.M10_STATE_VERSION:
            raise ValueError(f"policy.curious state version {v} is newer than {B.M10_STATE_VERSION}")
        super().load_state_dict(d)
        h = d.get("held")
        self.held = None if h is None else (int(h[0]), int(h[1]), int(h[2]), float(h[3]))
        self.baseline = float(d["baseline"])
        self.fast = np.array(d["fast"], dtype=np.float64).reshape(len(ACTIONS))
        self.slow = np.array(d["slow"], dtype=np.float64).reshape(len(ACTIONS))
        self.sum_b = float(d["sum_b"]); self.sum_r = float(d["sum_r"]); self.n_b = int(d["n_b"])
        self._last_b = float(d["last_b"])
        self._hist = [float(x) for x in d.get("hist", [])]

    def viz(self) -> list[VizSpec]:
        return super().viz() + [VizSpec("series", "bônus de curiosidade", {"bônus": list(self._hist)})]
