"""The deterministic body: needs, life stage, world and primitive rewards."""
import math

import numpy as np

from engrama import balance as B
from engrama.kernel.actions import ACTION_SPECS, WAKE_SONO, available
from engrama.kernel.fallback import fallback_action
from engrama.kernel.foods import FOODS
from engrama.kernel.genome import Genome
from engrama.kernel.lifecycle import Health, StageMachine
from engrama.kernel.needs import Needs
from engrama.kernel.rewards import RewardTracker
from engrama.kernel.sensors import Obs, WorldState
from engrama.vocab import NEED_KEYS, STAGES

_WAKERS = ("click", "pet", "message", "food")
CARESS_RELIEF = 8.0


class Kernel:
    def __init__(self, seed: int, now: float = 0.0) -> None:
        self.seed = seed
        self._t = float(now)
        self.genome = Genome.from_seed(seed)
        self.rng = np.random.default_rng(seed)
        self.needs = Needs()
        self.lifecycle = StageMachine()
        self.health = Health()
        self.world = WorldState()
        self.tracker = RewardTracker()
        self._queue: list[Obs] = []
        self._action: str | None = None
        self._action_start = 0.0
        self._egg_clicks = 0
        self._interact_until = -math.inf

    @property
    def t(self) -> float:
        return self._t

    @property
    def stage(self) -> str:
        return self.lifecycle.stage

    @property
    def asleep(self) -> bool:
        return self._action == "sleep"

    def ingest(self, events: list[Obs]) -> None:
        self._queue.extend(events)

    def available_actions(self) -> tuple[str, ...]:
        rested = self.needs.values["sono"] < WAKE_SONO
        return available(self.stage, self.asleep and not rested, self.world.fullscreen)

    def step(self, dt: float) -> tuple[list[Obs], dict[str, float]]:
        events, self._queue = self._queue, []
        t0 = self._t
        self._t += dt
        before = self.needs.as_vector()
        for e in events:
            if self.world.apply(e):
                self.tracker.on_novel()
            if e.kind in _WAKERS:
                self._interact_until = max(self._interact_until, e.t + B.INTERACT_WINDOW_S)
                if self.asleep:
                    self._action = None
            self._apply_event(e)
        awake = not self.asleep
        hot = min(dt, max(0.0, self._interact_until - t0))
        if hot:
            self.needs.decay(hot, awake, True)
        if dt - hot > 0:
            self.needs.decay(dt - hot, awake, False)
        if self._action is not None:
            spec = ACTION_SPECS[self._action]
            if spec.effects_per_h:
                run = dt
                if spec.duration_s:
                    run = min(dt, max(0.0, self._action_start + spec.duration_s - t0))
                self.needs.apply({k: v * run / B.HOUR for k, v in spec.effects_per_h.items()})
            if self.asleep:
                if self.needs.values["sono"] < WAKE_SONO:
                    self._action = None
            elif spec.duration_s and self._t - self._action_start >= spec.duration_s:
                self._action = None
        self.lifecycle.update(dt, self.needs.mean())
        self.health.update(dt, self.needs.mean())
        after = self.needs.as_vector()
        self.tracker.on_events(events, self._t)
        self.tracker.on_needs(before, after, dt)
        return events, self.tracker.collect(self._t)

    def _apply_event(self, e: Obs) -> None:
        if e.kind in ("click", "pet"):
            self.needs.apply({"carinho": -CARESS_RELIEF})
        if e.kind == "click" and self.stage == "egg":
            self._egg_clicks += 1
            if self._egg_clicks >= B.EGG_HATCH_CLICKS:
                self.lifecycle.hatch_now()
        elif e.kind == "food" and self.stage != "egg":
            food = FOODS.get(str(e.data.get("food", "")))
            if food and STAGES.index(self.stage) >= STAGES.index(food.min_stage):
                self.needs.apply(food.effects)

    def channels(self) -> dict[str, np.ndarray]:
        ang = 2.0 * math.pi * ((self._t / B.HOUR) % 24.0) / 24.0
        return {
            "body.needs": self.needs.as_vector(),
            "body.stage": np.array([float(self.lifecycle.stage_index)]),
            "body.asleep": np.array([1.0 if self.asleep else 0.0]),
            "world.hour": np.array([math.sin(ang), math.cos(ang)]),
            "world.user_active": np.array([1.0 if self.world.user_active else 0.0]),
            "world.fullscreen": np.array([1.0 if self.world.fullscreen else 0.0]),
        }

    def execute(self, proposed: str | None) -> tuple[str, bool]:
        avail = self.available_actions()
        pressed = self.world.fullscreen and self.stage != "egg"
        if self._action is not None and self._action not in avail:
            self._action = None
        if self._action is not None:
            return self._action, pressed or self._action != proposed
        if proposed in avail:
            action, forced = proposed, pressed
        else:
            action, forced = fallback_action(self.needs.values, avail), True
        self._action, self._action_start = action, self._t
        self.tracker.on_action_started(action, self._t)
        return action, forced

    def offline_catchup(self, seconds: float) -> None:
        h = seconds / B.HOUR
        for k in NEED_KEYS:
            cur = self.needs.values[k]
            self.needs.values[k] = max(cur, min(cur + B.NEED_RATES_PER_H[k] * h, B.OFFLINE_NEED_CAP))
        self._t += seconds
        self.lifecycle.update(seconds, self.needs.mean())
        self._action = None
        self._queue = []
        self.tracker = RewardTracker()

    def state_dict(self) -> dict:
        return {
            "seed": self.seed, "t": self._t, "genome": self.genome.to_dict(),
            "rng": self.rng.bit_generator.state,
            "needs": self.needs.to_dict(), "lifecycle": self.lifecycle.to_dict(),
            "health": self.health.to_dict(), "world": self.world.to_dict(),
            "tracker": self.tracker.to_dict(),
            "queue": [{"t": e.t, "kind": e.kind, "data": dict(e.data)} for e in self._queue],
            "action": self._action, "action_start": self._action_start,
            "egg_clicks": self._egg_clicks,
            "interact_until": None if self._interact_until == -math.inf else self._interact_until,
        }

    @classmethod
    def from_state_dict(cls, d: dict) -> "Kernel":
        k = cls(int(d["seed"]), float(d["t"]))
        k.genome = Genome.from_dict(d["genome"])
        k.rng.bit_generator.state = d["rng"]
        k.needs = Needs.from_dict(d["needs"])
        k.lifecycle = StageMachine.from_dict(d["lifecycle"])
        k.health = Health.from_dict(d["health"])
        k.world = WorldState.from_dict(d["world"])
        k.tracker = RewardTracker.from_dict(d["tracker"])
        k._queue = [Obs(float(e["t"]), e["kind"], dict(e["data"])) for e in d["queue"]]
        k._action = d["action"]
        k._action_start = float(d["action_start"])
        k._egg_clicks = int(d["egg_clicks"])
        iu = d.get("interact_until")
        k._interact_until = -math.inf if iu is None else float(iu)
        return k
