"""TemporalCTRNN: continuous-time RNN with a spread of time constants and the same predictive readout as the SNN."""
from __future__ import annotations
from collections import deque
import numpy as np
import engrama.balance as B
from engrama.mind.contracts import Module, Blackboard, VizSpec
from engrama.vocab import EVENT_KINDS

_NK = len(EVENT_KINDS)
_N_IN = _NK + 5                        # events, hour-phase halves, user_active
_SERIES_LEN = 300


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class TemporalCTRNN(Module):
    reads = ("world.hour", "world.user_active")
    writes = ("temporal.surprise", "temporal.familiarity", "temporal.expectation")
    rate_hz = 1.0
    budget_ms = B.CTRNN_BUDGET_MS

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.readout_hidden = bool(params.get("readout_hidden", True))   # False: ablation, bias-only readout
        n = int(params.get("n_hidden", B.CTRNN_HIDDEN))
        tau_min = float(params.get("tau_min", B.CTRNN_TAU_MIN_BINS))
        tau_max = float(params.get("tau_max", B.CTRNN_TAU_MAX_BINS))
        rho = float(params.get("spectral_radius", B.CTRNN_SPECTRAL_RADIUS))
        self.n = n
        self.tau = np.geomspace(tau_min, tau_max, n)
        self.U = rng.normal(0.0, B.CTRNN_W_IN / np.sqrt(_N_IN), (n, _N_IN))
        mask = rng.random((n, n)) < B.CTRNN_P_REC
        np.fill_diagonal(mask, False)
        W = rng.normal(0.0, 1.0, (n, n)) * mask
        r = float(np.max(np.abs(np.linalg.eigvals(W)))) if n else 0.0
        self.W = W * (rho / r) if r > 1e-12 else W
        self.b = rng.normal(0.0, 0.1, n)
        self.h = np.zeros(n)
        self.w_pred = np.zeros((_NK, n))
        self.bias = np.zeros(_NK)
        self.feat = np.zeros(n)
        self.fmean = np.zeros(n)
        self.pred = np.full(_NK, 0.5)
        self.surprise_ema = 0.0
        self.surprise_long = 0.5
        self.raw_surprise = 0.0
        self._series: deque = deque(maxlen=_SERIES_LEN)
        self._bin_start: float | None = None
        self._pending: list[tuple[float, str]] = []

    # --- encoding (same as the SNN) ---
    def _encode(self, kinds, bb: Blackboard) -> np.ndarray:
        x = np.zeros(_N_IN)
        for kind in kinds:
            x[EVENT_KINDS.index(kind)] = 1.0
        h = bb.get("world.hour")
        s, c = (float(h[0]), float(h[1])) if h is not None else (0.0, 0.0)
        x[_NK:_NK + 4] = (max(s, 0.0), max(-s, 0.0), max(c, 0.0), max(-c, 0.0))
        ua = bb.get("world.user_active")
        x[_NK + 4] = float(ua[0]) if ua is not None else 0.0
        return x

    # --- module api ---
    def step(self, bb: Blackboard, dt: float) -> None:
        now, bin_s = float(bb.t), B.SNN_BIN_S
        if self._bin_start is None:
            self._bin_start = now - dt
        self._pending.extend((float(ev.t), ev.kind) for ev in bb.events if ev.kind in EVENT_KINDS)
        earliest = now - B.SNN_MAX_BINS_PER_STEP * bin_s
        if self._bin_start < earliest:
            self._bin_start = earliest
        while now - self._bin_start >= bin_s - 1e-9:
            end = self._bin_start + bin_s
            kinds = {k for t, k in self._pending if t < end - 1e-6}
            self._pending = [(t, k) for t, k in self._pending if t >= end - 1e-6]
            self._advance(self._encode(kinds, bb), end)
            self._bin_start = end
        bb.write("temporal.surprise", [self.surprise_ema])
        bb.write("temporal.familiarity", [1.0 - self.surprise_long])
        bb.write("temporal.expectation", self.pred)

    def _advance(self, x: np.ndarray, t_end: float) -> None:
        err = x[:_NK] - self.pred
        raw = float(np.mean(np.abs(err)))
        f = self.feat
        g = B.SNN_PRED_LR / (1.0 + float(f @ f))
        self.w_pred += g * np.outer(err, f)
        self.bias += B.SNN_BIAS_LR * err
        self.raw_surprise = raw
        self.surprise_ema += (1.0 - B.SNN_SURPRISE_EMA) * (raw - self.surprise_ema)
        self.surprise_long += (raw - self.surprise_long) / B.SNN_FAMILIARITY_BINS

        S = B.CTRNN_SUBSTEPS
        drive = self.U @ x + self.b
        k = (1.0 / S) / self.tau
        h = self.h
        for _ in range(S):
            h = h + k * (-h + self.W @ np.tanh(h) + drive)
        self.h = h
        trace = np.tanh(h)
        self.fmean += B.SNN_FMEAN_RATE * (trace - self.fmean)
        self.feat = trace - self.fmean if self.readout_hidden else np.zeros(self.n)
        self.pred = _sigmoid(self.w_pred @ self.feat + self.bias)
        self._series.append((t_end, self.surprise_ema, 1.0 - self.surprise_long))

    def learn(self, exp) -> None:
        return None

    def state_dict(self) -> dict:
        return {"version": B.M10_STATE_VERSION,
                "h": self.h.copy(), "tau": self.tau.copy(), "W": self.W.copy(), "U": self.U.copy(),
                "b": self.b.copy(), "w_pred": self.w_pred.copy(), "bias": self.bias.copy(),
                "feat": self.feat.copy(), "fmean": self.fmean.copy(), "pred": self.pred.copy(),
                "surprise_ema": self.surprise_ema, "surprise_long": self.surprise_long,
                "raw_surprise": self.raw_surprise,
                "bin_start": self._bin_start, "pending": [[t, k] for t, k in self._pending],
                "series": np.array(self._series, dtype=np.float64).reshape(-1, 3)}

    def load_state_dict(self, d: dict) -> None:
        if not d:
            return
        if int(d.get("version", 0)) > B.M10_STATE_VERSION:
            raise ValueError(f"temporal.ctrnn state version {d['version']} is newer than {B.M10_STATE_VERSION}")
        for k in ("h", "tau", "W", "U", "b", "w_pred", "bias", "feat", "fmean", "pred"):
            setattr(self, k, np.array(d[k], dtype=np.float64))
        self.n = len(self.h)
        self.surprise_ema = float(d["surprise_ema"]); self.surprise_long = float(d["surprise_long"])
        self.raw_surprise = float(d.get("raw_surprise", 0.0))
        bs = d.get("bin_start")
        self._bin_start = None if bs is None else float(bs)
        self._pending = [(float(t), str(k)) for t, k in d.get("pending", [])]
        self._series = deque((tuple(r) for r in np.asarray(d.get("series", np.zeros((0, 3))))), maxlen=_SERIES_LEN)

    def _tau_bands(self) -> np.ndarray:
        a = np.abs(np.tanh(self.h))
        return np.array([float(np.mean(c)) if len(c) else 0.0 for c in np.array_split(a, 4)])

    def viz(self) -> list[VizSpec]:
        return [VizSpec("series", "surprise / familiarity",
                        {"names": ["surprise", "familiarity"], "rows": list(self._series)}),
                VizSpec("bars", "atividade por escala de tempo", self._tau_bands()),
                VizSpec("heatmap", "readout weights", self.w_pred.copy())]

    def lab_metrics(self) -> dict:
        return {"ctrnn_h_abs_mean": float(np.mean(np.abs(self.h))) if self.n else 0.0,
                "ctrnn_surprise_mean": float(self.surprise_ema)}
