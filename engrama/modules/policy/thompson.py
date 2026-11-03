"""ThompsonPolicy: Q-learning bayesiano simplificado (M10).

A média mu[s, a] é atualizada por TD, como no QLearningPolicy (mesma conta). A incerteza é
sd[s, a] = sqrt(max(floor², td_var) / (1 + n[s, a])), com n as visitas que esquecem com meia-vida
e td_var a variância móvel do erro de TD. A proposta é mu + sd * z, com uma normal por ação de
ACTIONS a cada decisão, para o consumo do RNG não depender das ações disponíveis.
"""
from __future__ import annotations
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Module, Blackboard, Proposal, Experience, VizSpec, reward_combine
from engrama.modules.policy.qlearning import N_STATES, context, state_index
from engrama.vocab import ACTIONS

DAY_S = 86400.0


class ThompsonPolicy(Module):
    reads = ("world.hour", "world.user_active", "affect.pad")
    writes = ()
    rate_hz = 1.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.alpha = float(self.params.get("alpha", B.QL_ALPHA))
        self.gamma = float(self.params.get("gamma", B.QL_GAMMA))
        self.sigma0 = float(self.params.get("sigma0", B.TS_SIGMA0))
        self.half_life_days = float(self.params.get("half_life_days", B.TS_N_HALF_LIFE_DAYS))
        self.mu = np.zeros((N_STATES, len(ACTIONS)))
        self.n = np.zeros((N_STATES, len(ACTIONS)))
        self.td_var = self.sigma0 ** 2
        self.decisions = 0
        self.explores = 0

    def sd(self) -> np.ndarray:
        return np.sqrt(np.maximum(B.TS_NOISE_FLOOR ** 2, self.td_var) / (1.0 + self.n))

    def learn(self, exp: Experience) -> None:
        if exp.action not in ACTIONS:
            return
        s, a = state_index(exp.channels), ACTIONS.index(exp.action)
        s2 = state_index(exp.next_channels)
        r = reward_combine(exp.rewards)
        td = r + self.gamma * self.mu[s2].max() - self.mu[s, a]
        self.mu[s, a] += self.alpha * td
        if exp.dt > 0:
            self.n *= 0.5 ** (exp.dt / (self.half_life_days * DAY_S))
        self.n[s, a] += 1.0
        self.td_var += (1.0 - B.TS_TD_VAR_EMA) * (td * td - self.td_var)

    def propose(self, bb: Blackboard) -> list[Proposal]:
        ch = bb.snapshot()
        s = state_index(ch)
        b, act, _ = context(ch)
        z = self.rng.standard_normal(len(ACTIONS))   # sempre len(ACTIONS) normais, por decisão
        sd = self.sd()
        out: list[Proposal] = []
        for a in bb.available_actions:
            if a not in ACTIONS:
                continue
            i = ACTIONS.index(a)
            out.append(Proposal(a, float(self.mu[s, i] + sd[s, i] * z[i]), f"amostrei: {b}/{act}"))
        if out:
            self.decisions += 1
            idx = [ACTIONS.index(p.action) for p in out]
            sampled = max(range(len(out)), key=lambda k: out[k].score)
            greedy = max(range(len(idx)), key=lambda k: self.mu[s, idx[k]])
            if sampled != greedy:
                self.explores += 1
        return out

    def lab_metrics(self) -> dict:
        rate = self.explores / self.decisions if self.decisions else 0.0
        return {"sd_mean": float(self.sd().mean()), "explore_rate": float(rate)}

    def state_dict(self) -> dict:
        return {"version": B.M10_STATE_VERSION, "mu": self.mu.copy(), "n": self.n.copy(),
                "td_var": float(self.td_var), "decisions": int(self.decisions), "explores": int(self.explores)}

    def load_state_dict(self, d: dict) -> None:
        if not d:
            return
        v = int(d.get("version", B.M10_STATE_VERSION))
        if v > B.M10_STATE_VERSION:
            raise ValueError(f"thompson: versão {v} mais nova que {B.M10_STATE_VERSION}")
        self.mu = np.array(d["mu"], dtype=np.float64).reshape(N_STATES, len(ACTIONS))
        self.n = np.array(d["n"], dtype=np.float64).reshape(N_STATES, len(ACTIONS))
        self.td_var = float(d["td_var"])
        self.decisions = int(d["decisions"])
        self.explores = int(d["explores"])

    def viz(self) -> list[VizSpec]:
        return [VizSpec("heatmap", "μ Thompson (estado x ação)", self.mu.tolist()),
                VizSpec("heatmap", "sd Thompson (estado x ação)", self.sd().tolist())]
