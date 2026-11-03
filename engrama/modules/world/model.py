"""WorldModel: online forward model (context + action -> events and need rates); its error is the curiosity signal."""
from __future__ import annotations
import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Module, Blackboard, Experience, VizSpec
from engrama.vocab import ACTIONS, EVENT_KINDS, NEED_KEYS

CONTEXT = ("world.hour", "world.user_active", "body.asleep", "affect.pad", "drives")   # 2+1+1+3+6 = 13
_CTX_DIM = (2, 1, 1, 3, len(NEED_KEYS))
N_CTX = sum(_CTX_DIM)
N_IN = N_CTX + 1 + len(ACTIONS)
N_EV = len(EVENT_KINDS)
N_OUT = N_EV + len(NEED_KEYS)


def features(ch: dict[str, np.ndarray], action: str) -> np.ndarray:
    """Context channels (missing = zeros), bias 1, one-hot action."""
    x = np.zeros(N_IN)
    i = 0
    for name, d in zip(CONTEXT, _CTX_DIM):
        v = ch.get(name)
        if v is not None:
            x[i:i + d] = np.asarray(v, dtype=np.float64).reshape(-1)[:d]
        i += d
    x[N_CTX] = 1.0
    if action in ACTIONS:
        x[N_CTX + 1 + ACTIONS.index(action)] = 1.0
    return x


def targets(exp: Experience) -> np.ndarray:
    """Event kinds seen this tick (0/1) + clipped need change per hour."""
    y = np.zeros(N_OUT)
    for o in exp.events:
        if o.kind in EVENT_KINDS:
            y[EVENT_KINDS.index(o.kind)] = 1.0
    n0 = exp.channels.get("body.needs")
    n1 = exp.next_channels.get("body.needs")
    if n0 is not None and n1 is not None and exp.dt > 0:
        rate = (np.asarray(n1, dtype=np.float64).reshape(-1) - np.asarray(n0, dtype=np.float64).reshape(-1))
        y[N_EV:] = np.clip(rate / (exp.dt / B.HOUR), -1.0, 1.0)
    return y


class WorldModel(Module):
    reads = CONTEXT + ("body.needs",)
    writes = ("world.error",)
    rate_hz = 1.0

    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        super().__init__(params, rng)
        self.lr = float(self.params.get("lr", B.WM_LR))
        self._init()

    def _init(self) -> None:
        self.W = np.zeros((N_OUT, N_IN))
        self.last_error = 0.0
        self.err_ema = 0.0
        self.err_sum = 0.0
        self.n = 0
        self._hist: list[float] = []

    def predict(self, x: np.ndarray) -> np.ndarray:
        z = self.W @ x
        p = z.copy()
        p[:N_EV] = 1.0 / (1.0 + np.exp(-np.clip(z[:N_EV], -30.0, 30.0)))
        return p

    def learn(self, exp: Experience) -> None:
        if exp.dt <= 0 or exp.action not in ACTIONS:
            return
        x = features(exp.channels, exp.action)
        y = targets(exp)
        d = y - self.predict(x)
        err = float(np.clip(np.mean(d * d), 0.0, 1.0))
        self.W += self.lr * np.outer(d, x) / (1.0 + float(x @ x))
        self.last_error = err
        self.err_ema = B.WM_ERR_EMA * self.err_ema + (1.0 - B.WM_ERR_EMA) * err
        self.err_sum += err
        self.n += 1
        self._hist.append(err)
        if len(self._hist) > 200:
            del self._hist[:-200]

    def step(self, bb: Blackboard, dt: float) -> None:
        bb.write("world.error", [self.last_error])

    def lab_metrics(self) -> dict:
        return {"world_error_mean": self.err_sum / self.n if self.n else 0.0, "world_error_ema": self.err_ema}

    def state_dict(self) -> dict:
        return {"version": B.M10_STATE_VERSION, "W": self.W.copy(), "last_error": self.last_error,
                "err_ema": self.err_ema, "err_sum": self.err_sum, "n": self.n, "hist": list(self._hist)}

    def load_state_dict(self, d: dict) -> None:
        if not d:
            return
        v = int(d.get("version", B.M10_STATE_VERSION))
        if v > B.M10_STATE_VERSION:
            raise ValueError(f"world.model state version {v} is newer than {B.M10_STATE_VERSION}")
        self.W = np.array(d["W"], dtype=np.float64).reshape(N_OUT, N_IN)
        self.last_error = float(d["last_error"])
        self.err_ema = float(d["err_ema"])
        self.err_sum = float(d["err_sum"])
        self.n = int(d["n"])
        self._hist = [float(x) for x in d.get("hist", [])]

    def viz(self) -> list[VizSpec]:
        return [VizSpec("series", "erro do modelo de mundo", {"erro": list(self._hist), "média": [self.err_ema]})]
