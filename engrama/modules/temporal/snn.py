"""TemporalSNN: spiking network with homeostasis and a predictive readout (surprise/familiarity)."""
from __future__ import annotations
from collections import deque
import numpy as np
import engrama.balance as B
from engrama.mind.contracts import Module, Blackboard, VizSpec
from engrama.vocab import EVENT_KINDS, STAGES

_NK = len(EVENT_KINDS)
_N_UNITS = _NK + 4 + 1                 # events, hour-phase halves, user_active
_N_IN = _N_UNITS * B.SNN_POP
_SERIES_LEN = 300
_THETA_MIN, _THETA_MAX = 0.2, 20.0


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _shift(a: np.ndarray) -> np.ndarray:
    """a delayed by one substep (row t holds a[t-1])."""
    return np.vstack([np.zeros((1, a.shape[1])), a[:-1]])


class TemporalSNN(Module):
    reads = ("body.stage", "world.hour", "world.user_active")
    writes = ("temporal.surprise", "temporal.familiarity", "temporal.expectation")
    rate_hz = 1.0
    budget_ms = 3.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.stage = int(params.get("stage", 0))
        n = int(params.get("n_hidden", B.SNN_HIDDEN_BY_STAGE[STAGES[self.stage]]))
        self.n = 0
        self.feat = np.zeros(0)
        self._alloc_empty()
        self._grow_to(n)
        self.bias = np.zeros(_NK)
        self.surprise_ema = 0.0
        self.surprise_long = 0.5
        self.raw_surprise = 0.0
        self.pred = np.full(_NK, 0.5)
        self.last_spikes = np.zeros((B.SNN_SUBSTEPS, n), dtype=bool)
        self._series: deque = deque(maxlen=_SERIES_LEN)

    # --- structure ---
    def _alloc_empty(self) -> None:
        self.w_in = np.zeros((0, _N_IN)); self.m_in = np.zeros((0, _N_IN), bool)
        self.w_ee = np.zeros((0, 0)); self.m_ee = np.zeros((0, 0), bool)
        self.w_ei = np.zeros((0, 0)); self.w_ie = np.zeros((0, 0))
        self.theta = np.zeros(0); self.w_pred = np.zeros((_NK, 0))

    def _grow_to(self, n_new: int) -> None:
        """Extend to n_new excitatory neurons keeping existing weights; new entries use 1/sqrt(fan_in)."""
        n0, ni0 = self.n, self.n // 4
        ni = n_new // 4
        rng = self.rng
        fan_in = max(1.0, B.SNN_P_IN * _N_IN)
        fan_ee = max(1.0, B.SNN_P_EE * n_new)
        m = rng.random((n_new, _N_IN)) < B.SNN_P_IN
        w = m * rng.uniform(0.5, 1.0, (n_new, _N_IN)) * (B.SNN_W_IN / np.sqrt(fan_in))
        m[:n0] = self.m_in; w[:n0] = self.w_in
        self.m_in, self.w_in = m, w
        m = rng.random((n_new, n_new)) < B.SNN_P_EE
        np.fill_diagonal(m, False)
        w = m * rng.uniform(0.5, 1.0, (n_new, n_new)) * (B.SNN_W_EE / np.sqrt(fan_ee))
        m[:n0, :n0] = self.m_ee; w[:n0, :n0] = self.w_ee
        self.m_ee, self.w_ee = m, w
        w = rng.uniform(0.5, 1.0, (ni, n_new)) * (B.SNN_W_EI / np.sqrt(n_new))
        w[:ni0, :n0] = self.w_ei
        self.w_ei = w
        w = rng.uniform(0.5, 1.0, (n_new, ni)) * (B.SNN_W_IE / np.sqrt(max(1, ni)))
        w[:n0, :ni0] = self.w_ie
        self.w_ie = w
        th = np.full(n_new, B.SNN_V_THRESH)
        if n0:
            th[:n0] = self.theta
            th[n0:] = float(np.mean(self.theta))
        self.theta = th
        wp = np.zeros((_NK, n_new)); wp[:, :n0] = self.w_pred
        self.w_pred = wp
        ft = np.zeros(n_new); ft[:n0] = self.feat
        self.feat = ft
        self.n = n_new
        self.v_e = np.zeros(n_new); self.v_i = np.zeros(ni)

    def grow(self, new_n: int) -> None:
        if new_n > self.n:
            self._grow_to(new_n)
            self.last_spikes = np.zeros((B.SNN_SUBSTEPS, self.n), dtype=bool)

    # --- encoding ---
    def _encode(self, bb: Blackboard) -> np.ndarray:
        x = np.zeros(_N_UNITS)
        for ev in bb.events:
            if ev.kind in EVENT_KINDS:
                x[EVENT_KINDS.index(ev.kind)] = 1.0
        h = bb.get("world.hour")
        s, c = (float(h[0]), float(h[1])) if h is not None else (0.0, 0.0)
        x[_NK:_NK + 4] = (max(s, 0.0), max(-s, 0.0), max(c, 0.0), max(-c, 0.0))
        ua = bb.get("world.user_active")
        x[_NK + 4] = float(ua[0]) if ua is not None else 0.0
        return x

    # --- dynamics ---
    def _run_bin(self, x: np.ndarray) -> np.ndarray:
        S, n = B.SNN_SUBSTEPS, self.n
        p = np.repeat(x, B.SNN_POP) * B.SNN_INPUT_HZ * 1e-3
        pre = (self.rng.random((S, _N_IN)) < p).astype(np.float64)
        drive_in = pre @ self.w_in.T            # (S, n) input current per substep
        spikes = np.zeros((S, n), dtype=bool)
        v_e, v_i = self.v_e, self.v_i
        refr = np.zeros(n, dtype=np.int64)
        e_prev = np.zeros(n); i_prev = np.zeros(len(v_i))
        d = B.SNN_LIF_DECAY
        for t in range(S):
            inp = drive_in[t] + self.w_ee @ e_prev - self.w_ie @ i_prev
            v_e = v_e * d + np.where(refr > 0, 0.0, inp)
            v_i = v_i * d + self.w_ei @ e_prev
            fire = v_e >= self.theta
            fire_i = v_i >= B.SNN_V_THRESH
            v_e[fire] = 0.0; v_i[fire_i] = 0.0
            refr = np.where(fire, B.SNN_REFRAC_MS, np.maximum(refr - 1, 0))
            spikes[t] = fire
            e_prev = fire.astype(np.float64); i_prev = fire_i.astype(np.float64)
        self.v_e, self.v_i = v_e, v_i
        self._stdp(pre, spikes.astype(np.float64))
        return spikes

    def _stdp(self, pre: np.ndarray, post: np.ndarray) -> None:
        """Pair-based STDP with traces, applied once per bin on Input->E and E->E."""
        dec = B.SNN_TRACE_DECAY
        pre_tr = np.zeros_like(pre); post_tr = np.zeros_like(post)
        a = np.zeros(pre.shape[1]); b = np.zeros(post.shape[1])
        for t in range(pre.shape[0]):        # traces as seen by spikes at t (before they count)
            pre_tr[t] = a; post_tr[t] = b
            a = a * dec + pre[t]; b = b * dec + post[t]
        ap, am, wmax = B.SNN_STDP_APLUS, B.SNN_STDP_AMINUS, B.SNN_WMAX
        dw = ap * (post.T @ pre_tr) - am * (post_tr.T @ pre)
        self.w_in = np.clip(self.w_in + dw * self.m_in, 0.0, wmax)
        dw = ap * (post.T @ _shift(post_tr)) - am * (post_tr.T @ _shift(post))
        self.w_ee = np.clip(self.w_ee + dw * self.m_ee, 0.0, wmax)

    # --- module api ---
    def step(self, bb: Blackboard, dt: float) -> None:
        st = bb.get("body.stage")
        if st is not None:
            idx = int(np.clip(round(float(st[0])), 0, len(STAGES) - 1))
            if idx != self.stage:
                self.stage = idx
                self.grow(B.SNN_HIDDEN_BY_STAGE[STAGES[idx]])
        x = self._encode(bb)
        ev = x[:_NK]
        err = ev - self.pred
        raw = float(np.mean(np.abs(err)))
        f = self.feat
        g = B.SNN_PRED_LR / (1.0 + float(f @ f))
        self.w_pred += g * np.outer(err, f)
        self.bias += g * err
        self.raw_surprise = raw
        self.surprise_ema += (1.0 - B.SNN_SURPRISE_EMA) * (raw - self.surprise_ema)
        self.surprise_long += (raw - self.surprise_long) / B.SNN_FAMILIARITY_BINS

        spikes = self._run_bin(x)
        self.last_spikes = spikes
        rate = spikes.sum(axis=0) * (1000.0 / B.SNN_SUBSTEPS)
        k = B.SNN_HOMEO_GAIN / B.SNN_HOMEO_TAU_BINS
        e = np.clip((rate - B.SNN_TARGET_HZ) / B.SNN_TARGET_HZ, -1.0, 4.0)
        self.theta = np.clip(self.theta + k * e, _THETA_MIN, _THETA_MAX)

        self.feat = B.SNN_READOUT_DECAY * self.feat + rate / B.SNN_TARGET_HZ
        self.pred = _sigmoid(self.w_pred @ self.feat + self.bias)
        fam = 1.0 - self.surprise_long
        bb.write("temporal.surprise", [self.surprise_ema])
        bb.write("temporal.familiarity", [fam])
        bb.write("temporal.expectation", self.pred)
        self._series.append((bb.t, self.surprise_ema, fam))

    def learn(self, exp) -> None:
        return None

    def state_dict(self) -> dict:
        return {"stage": self.stage, "n": self.n,
                "w_in": self.w_in.copy(), "m_in": self.m_in.copy(),
                "w_ee": self.w_ee.copy(), "m_ee": self.m_ee.copy(),
                "w_ei": self.w_ei.copy(), "w_ie": self.w_ie.copy(),
                "theta": self.theta.copy(), "v_e": self.v_e.copy(), "v_i": self.v_i.copy(),
                "w_pred": self.w_pred.copy(), "bias": self.bias.copy(),
                "feat": self.feat.copy(), "pred": self.pred.copy(),
                "surprise_ema": self.surprise_ema, "surprise_long": self.surprise_long}

    def load_state_dict(self, d: dict) -> None:
        self.stage = int(d["stage"]); self.n = int(d["n"])
        for k in ("w_in", "w_ee", "w_ei", "w_ie", "theta", "v_e", "v_i", "w_pred", "bias", "feat", "pred"):
            setattr(self, k, np.array(d[k], dtype=np.float64))
        self.m_in = np.array(d["m_in"], dtype=bool); self.m_ee = np.array(d["m_ee"], dtype=bool)
        self.surprise_ema = float(d["surprise_ema"]); self.surprise_long = float(d["surprise_long"])
        self.last_spikes = np.zeros((B.SNN_SUBSTEPS, self.n), dtype=bool)

    def viz(self) -> list[VizSpec]:
        return [VizSpec("raster", "E spikes (last bin)", self.last_spikes.copy()),
                VizSpec("heatmap", "Input->E weights", self.w_in.copy()),
                VizSpec("series", "surprise / familiarity",
                        {"names": ["surprise", "familiarity"], "rows": list(self._series)})]
