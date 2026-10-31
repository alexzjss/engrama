"""Shared mind contract: channels, blackboard, module base class, experience records."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
import numpy as np
from engrama import balance as B
from engrama.vocab import NEED_KEYS, TRAIT_KEYS, ACTIONS, EVENT_KINDS, REWARD_KEYS, FOOD_IDS

@dataclass(frozen=True)
class Channel:
    name: str
    dim: int
    lo: float = -1.0
    hi: float = 1.0
    doc: str = ""

CHANNELS: dict[str, Channel] = {c.name: c for c in (
    Channel("body.needs", len(NEED_KEYS), 0, 1, "needs/100, NEED_KEYS order"),
    Channel("body.stage", 1, 0, 5, "index into STAGES"),
    Channel("body.asleep", 1, 0, 1),
    Channel("world.hour", 2, -1, 1, "sin, cos of 2*pi*hour/24"),
    Channel("world.user_active", 1, 0, 1),
    Channel("world.fullscreen", 1, 0, 1),
    Channel("drives", len(NEED_KEYS), 0, 1, "urgency per need"),
    Channel("affect.pad", 3, -1, 1, "pleasure, arousal, dominance"),
    Channel("traits", len(TRAIT_KEYS), 0, 1, "traits/100, TRAIT_KEYS order"),
    Channel("temporal.surprise", 1, 0, 1),
    Channel("temporal.familiarity", 1, 0, 1),
    Channel("temporal.expectation", len(EVENT_KINDS), 0, 1, "P(event kind next bin)"),
    Channel("prefs.food", len(FOOD_IDS), -1, 1),
)}

@dataclass(frozen=True)
class Observation:
    t: float
    kind: str                 # one of EVENT_KINDS
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Proposal:
    action: str               # one of ACTIONS
    score: float              # module-local scale; arbiter weights it
    reason: str               # human-readable, required, non-empty
    source: str = ""          # filled by the scheduler with module name

@dataclass(frozen=True)
class Experience:
    t: float
    dt: float
    events: tuple[Observation, ...]          # observations of this tick
    channels: dict[str, np.ndarray]          # copies, BEFORE the decision
    action: str                              # action executed during [t-dt, t]
    action_prob: float                       # arbiter probability of that action (1.0 if forced)
    rewards: dict[str, float]                # REWARD_KEYS -> value observed at t
    next_channels: dict[str, np.ndarray]     # copies, AFTER kernel step at t

VizKind = Literal["raster", "heatmap", "series", "bars", "pad3d", "table"]

@dataclass(frozen=True)
class VizSpec:
    kind: VizKind
    title: str
    data: Any

class Blackboard:
    """Typed channel store + this tick's events. Single writer: the simulation thread."""
    def __init__(self) -> None:
        self._v: dict[str, np.ndarray] = {}
        self.events: tuple[Observation, ...] = ()
        self.t: float = 0.0
        self.available_actions: tuple[str, ...] = ACTIONS

    @staticmethod
    def _spec(name: str) -> Channel:
        base = name
        if name.startswith("shadow/"):
            parts = name.split("/", 2)
            if len(parts) != 3 or not parts[1]:
                raise KeyError(name)
            base = parts[2]
        if base not in CHANNELS:
            raise KeyError(name)
        return CHANNELS[base]

    def write(self, name: str, value) -> None:
        ch = self._spec(name)
        arr = np.array(value, dtype=np.float64).reshape(-1)
        if arr.shape != (ch.dim,):
            raise ValueError(f"{name}: expected dim {ch.dim}, got {arr.shape}")
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{name}: non-finite value")
        self._v[name] = np.clip(arr, ch.lo, ch.hi)

    def read(self, name: str) -> np.ndarray:
        return self._v[name].copy()

    def get(self, name: str, default=None):
        v = self._v.get(name)
        return default if v is None else v.copy()

    def has(self, name: str) -> bool:
        return name in self._v

    def snapshot(self) -> dict[str, np.ndarray]:
        return {k: v.copy() for k, v in self._v.items()}

class Module:
    name: str = ""                 # instance name, set by registry from recipe (default = type)
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    rate_hz: float = 1.0           # in SIM time; scheduler runs it at most once per tick
    budget_ms: float = B.MODULE_DEFAULT_BUDGET_MS
    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        self.params = dict(params); self.rng = rng
    def step(self, bb: Blackboard, dt: float) -> None: ...
    def propose(self, bb: Blackboard) -> list[Proposal]: return []
    def learn(self, exp: Experience) -> None: ...
    def state_dict(self) -> dict: return {}
    def load_state_dict(self, d: dict) -> None: ...
    def viz(self) -> list[VizSpec]: return []

def reward_combine(rewards: dict[str, float], weights: dict[str, float] | None = None) -> float:
    w = B.REWARD_WEIGHTS if weights is None else weights
    return float(sum(w.get(k, 0.0) * rewards.get(k, 0.0) for k in REWARD_KEYS))
