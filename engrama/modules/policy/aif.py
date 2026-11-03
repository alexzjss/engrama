"""ActiveInferencePolicy: minimal, honest active inference (M10).

Observed contexts (the 32 Q-learning states), one-step horizon, the seven reward signals as binary outcome
factors with Beta counts per (context, action, factor). Preferences are priors over outcomes:
ln p~_k(o=1) = C_k - logaddexp(C_k, 0), ln p~_k(o=0) = -logaddexp(C_k, 0), with C_k = scale * REWARD_WEIGHTS[k].
G(a) = sum_k -E_q[ln p~_k(o)] - eta * (parameter information gain); the proposal score is -G(a).
With observed states, risk + ambiguity reduce to the cross-entropy with the preferences, and the epistemic term
uses the pymdp approximation 0.5 * (1/alpha_o - 1/alpha_0). It behaves like a Bayesian bandit with an
information bonus. No RNG is used.
"""
from __future__ import annotations
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import (ASK_ACTION, ASK_WINDOW_KEYS, Blackboard, Experience, Module, Proposal,
                                    VizSpec)
from engrama.mind.helpers import read_traits
from engrama.modules.policy.qlearning import N_STATES, state_index
from engrama.vocab import ACTIONS, REWARD_KEYS

FACTORS = REWARD_KEYS
_NF = len(FACTORS)
_EPS = 1e-12          # guards 1/0 and log(0); counts never fall below the prior in normal use
_ASK_IDX = tuple(FACTORS.index(k) for k in ASK_WINDOW_KEYS)
_W = np.array([B.REWARD_WEIGHTS[k] for k in FACTORS], dtype=np.float64)
_UR = FACTORS.index("user_response")


def outcome_vector(rewards: dict[str, float]) -> np.ndarray:
    return np.array([rewards.get(k, 0.0) > 0 for k in FACTORS], dtype=bool)


def log_pref(traits: dict[str, float], scale: float = B.AIF_PREF_SCALE) -> np.ndarray:
    """(7, 2) log preferences, each row normalised (exp sums to 1); stable via logaddexp."""
    c = scale * _W
    c[_UR] *= 1.0 + B.AIF_SOCIAL_GAIN * (float(traits.get("sociabilidade", 0.5)) - 0.5)
    lse = np.logaddexp(c, 0.0)
    return np.stack([-lse, c - lse], axis=-1)


def efe(counts: np.ndarray, lnp: np.ndarray, eta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """counts (A, 7, 2) of one context -> (G, pragmatic, novelty), each (A,)."""
    c = np.maximum(np.asarray(counts, dtype=np.float64), _EPS)
    c0 = c.sum(-1, keepdims=True)
    q = c / c0
    pragmatic = -(q * lnp).sum(axis=(-1, -2))
    novelty = (q * 0.5 * (1.0 / c - 1.0 / c0)).sum(axis=(-1, -2))
    return pragmatic - eta * novelty, pragmatic, novelty


class ActiveInferencePolicy(Module):
    reads = ("world.hour", "world.user_active", "affect.pad", "traits")
    writes = ()
    rate_hz = 1.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.pref_scale = float(self.params.get("pref_scale", B.AIF_PREF_SCALE))
        self.novelty_weight = float(self.params.get("novelty_weight", B.AIF_NOVELTY_WEIGHT))
        self.half_life_days = float(self.params.get("half_life_days", B.AIF_COUNT_HALF_LIFE_DAYS))
        self.counts = np.full((N_STATES, len(ACTIONS), _NF, 2), B.AIF_PRIOR, dtype=np.float64)
        # decisions, sum eta*novelty, sum |pragmatic|, sum G spread, sum pragmatic (means over actions)
        self.stats = np.zeros(5, dtype=np.float64)
        self._last: tuple[list[str], np.ndarray, np.ndarray, np.ndarray] | None = None

    def learn(self, exp: Experience) -> None:
        if exp.action not in ACTIONS:
            return
        s, a = state_index(exp.channels), ACTIONS.index(exp.action)
        if exp.dt > 0:
            f = 0.5 ** (exp.dt / (self.half_life_days * 86400.0))
            self.counts = B.AIF_PRIOR + (self.counts - B.AIF_PRIOR) * f
        o = outcome_vector(exp.rewards)
        if exp.dt <= 0:
            for k in _ASK_IDX:
                if o[k]:
                    self.counts[s, a, k, 1] += 1.0
            return
        for k in range(_NF):
            if exp.action == ASK_ACTION and k in _ASK_IDX and not o[k]:
                continue
            self.counts[s, a, k, int(o[k])] += 1.0

    def propose(self, bb: Blackboard) -> list[Proposal]:
        s = state_index(bb.snapshot())
        lnp = log_pref(read_traits(bb), self.pref_scale)
        G, prag, nov = efe(self.counts[s], lnp, self.novelty_weight)
        acts = [a for a in bb.available_actions if a in ACTIONS]
        idx = [ACTIONS.index(a) for a in acts]
        if idx:
            g, p, n = G[idx], prag[idx], self.novelty_weight * nov[idx]
            self.stats += (1.0, float(n.mean()), float(np.abs(p).mean()), float(g.max() - g.min()),
                           float(p.mean()))
            self._last = (acts, -g, p, nov[idx])
        out = []
        for a, i in zip(acts, idx):
            q = self.counts[s, i] / self.counts[s, i].sum(-1, keepdims=True)
            if self.novelty_weight * nov[i] > abs(prag[i]):
                reason = f"curiosa sobre {a}"
            else:
                k = int(np.argmax(q[:, 1] * np.abs(_W)))
                reason = f"prefere {FACTORS[k]}"
            out.append(Proposal(a, float(-G[i]), reason))
        return out

    def lab_metrics(self) -> dict:
        n = max(self.stats[0], 1.0)
        tot = self.stats[1] + self.stats[2]
        return {"novelty_share": float(self.stats[1] / tot) if tot > 0 else 0.0,
                "g_spread_mean": float(self.stats[3] / n), "pragmatic_mean": float(self.stats[4] / n)}

    def state_dict(self) -> dict:
        return {"version": B.M10_STATE_VERSION, "counts": self.counts.copy(), "stats": self.stats.copy()}

    def load_state_dict(self, d: dict) -> None:
        if int(d.get("version", B.M10_STATE_VERSION)) > B.M10_STATE_VERSION:
            raise ValueError(f"policy.aif: unsupported state version {d['version']}")
        if "counts" in d:
            self.counts = np.array(d["counts"], dtype=np.float64).reshape(N_STATES, len(ACTIONS), _NF, 2)
        if "stats" in d:
            self.stats = np.array(d["stats"], dtype=np.float64).reshape(5)

    def viz(self) -> list[VizSpec]:
        if self._last is None:
            return [VizSpec("bars", "-G por ação", {}), VizSpec("table", "pragmático / novidade", [])]
        acts, score, prag, nov = self._last
        return [VizSpec("bars", "-G por ação", {a: float(x) for a, x in zip(acts, score)}),
                VizSpec("table", "pragmático / novidade",
                        [[a, float(p), float(n)] for a, p, n in zip(acts, prag, nov)])]
