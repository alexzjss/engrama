"""The deterministic body: needs, life stage, world and primitive rewards."""
import dataclasses
import math
from collections.abc import Sequence

import numpy as np

from engrama import balance as B
from engrama.kernel.branches import BranchContext, pick_branch
from engrama.kernel.actions import ACTION_SPECS, WAKE_SONO, available
from engrama.kernel.fallback import fallback_action
from engrama.kernel.foods import FOODS
from engrama.kernel.genome import Genome
from engrama.kernel.lifecycle import Health, StageMachine
from engrama.kernel.needs import Needs
from engrama.kernel.rewards import RewardTracker
from engrama.kernel.sensors import Obs, WorldState
from engrama.vocab import (BRANCH_STAGES, INITIAL_TRAITS, INTEREST_GROUPS, INTEREST_KEYS, MEDICINE_ID,
                           NEED_KEYS, STAGES, TRAIT_KEYS)

_WAKERS = ("click", "pet", "message", "food")
CARESS_RELIEF = 8.0
CALM_AFTER_MESSAGE_S = 5 * 60.0     # old-age death waits this long after the last message
_SICK_BLOCKED = ("play_alone", "explore", "show_something")


class Kernel:
    def __init__(self, seed: int, now: float = 0.0, generation: int = 1) -> None:
        self.seed = seed
        self.generation = generation
        self.lineage: tuple[str, ...] = ()
        self.dead = False
        self.death_cause = ""
        self.interest_s: dict[str, float] = {}
        self._traits: tuple[float, ...] = tuple(INITIAL_TRAITS[k] / 100.0 for k in TRAIT_KEYS)
        self._last_message_t = -math.inf
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
        self._interact_from = math.inf
        self._interact_until = -math.inf

    @property
    def t(self) -> float:
        return self._t

    @property
    def stage(self) -> str:
        return self.lifecycle.stage

    @property
    def egg_clicks(self) -> int:
        return self._egg_clicks

    @property
    def action(self) -> str | None:
        return self._action

    @property
    def asleep(self) -> bool:
        return self._action == "sleep"

    def ingest(self, events: list[Obs]) -> None:
        self._queue.extend(events)

    def observe_traits(self, vec: Sequence[float]) -> None:
        """Latest trait vector (TRAIT_KEYS order, 0..1) from the mind; used only for branching."""
        if len(vec) == len(TRAIT_KEYS):
            self._traits = tuple(float(x) for x in vec)

    def interests(self) -> dict[str, float]:
        """Shares of accumulated interest time per INTEREST_KEYS (all 0 when none yet)."""
        total = sum(self.interest_s.values())
        return {k: (self.interest_s.get(k, 0.0) / total if total > 0 else 0.0) for k in INTEREST_KEYS}

    def available_actions(self) -> tuple[str, ...]:
        if self.dead:
            return ()
        rested = self.needs.values["sono"] < WAKE_SONO
        acts = available(self.stage, self.asleep and not rested, self.world.fullscreen)
        lc = self.tracker.last_close
        if lc is not None and self._t - lc < B.ASK_MIN_INTERVAL:
            acts = tuple(a for a in acts if a != "ask_attention")
        if self.health.sick:
            acts = tuple(a for a in acts if a not in _SICK_BLOCKED)
        return acts

    def step(self, dt: float) -> tuple[list[Obs], dict[str, float]]:
        events, self._queue = self._queue, []
        t0 = self._t
        self._t += dt
        if self.dead:
            for e in events:
                self.world.apply(e)
            return events, self.tracker.collect(self._t)
        prev_stage = self.stage
        before = self.needs.as_vector()
        for e in events:
            if self.world.apply(e):
                self.tracker.on_novel()
            if e.kind in _WAKERS:
                self._mark_interaction(e.t)
                if self.asleep:
                    self._action = None
            self._apply_event(e)
        grp = INTEREST_GROUPS.get(self.world.last_app)
        if grp:
            self.interest_s[grp] = self.interest_s.get(grp, 0.0) + dt
        awake = not self.asleep
        hot = max(0.0, min(t0 + dt, self._interact_until) - max(t0, self._interact_from))
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
        self._on_stage_change(prev_stage)
        if self.stage != "egg":
            if self.health.update(dt, self.needs.mean(), self.rng):
                self._die("neglect")
            elif self._old_enough_to_die() and self._calm():
                self._die("old_age")
        after = self.needs.as_vector()
        self.tracker.on_events(events, self._t)
        self.tracker.on_needs(before, after, dt)
        return events, self.tracker.collect(self._t)

    def _calm(self) -> bool:
        return (not self.asleep and not self.world.fullscreen
                and self._t - self._last_message_t >= CALM_AFTER_MESSAGE_S)

    def _old_enough_to_die(self) -> bool:
        return self.lifecycle.old and self.lifecycle.old_online_s >= B.OLD_AGE_WARN_S

    def _die(self, cause: str) -> None:
        self.dead, self.death_cause, self._action = True, cause, None

    def _on_stage_change(self, prev: str) -> None:
        if self.stage == prev or self.stage not in BRANCH_STAGES:
            return
        lc = self.lifecycle
        ctx = BranchContext(self.stage, lc.care_quality, lc.finished_care_mean, lc.life_care_mean,
                            self._traits, self.interests(), self.lineage)
        branch = pick_branch(ctx, self.seed)
        self.genome = dataclasses.replace(self.genome, branch=branch)
        self.lineage = self.lineage + (branch,)

    def _mark_interaction(self, t: float) -> None:
        end = t + B.INTERACT_WINDOW_S
        if t <= self._interact_until:
            self._interact_from = min(self._interact_from, t)
            self._interact_until = max(self._interact_until, end)
        else:
            self._interact_from, self._interact_until = t, end

    def _apply_event(self, e: Obs) -> None:
        if e.kind == "message":
            self._last_message_t = self._t
        if e.kind in ("click", "pet"):
            self.needs.apply({"carinho": -CARESS_RELIEF})
        if e.kind == "click" and self.stage == "egg":
            self._egg_clicks += 1
            if self._egg_clicks >= B.EGG_HATCH_CLICKS:
                self.lifecycle.hatch_now()
        elif e.kind == "food" and self.stage != "egg" and e.data.get("food") == MEDICINE_ID:
            self.health.give_medicine(self._t)
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
            "body.health": self.health_vector(),
            "world.hour": np.array([math.sin(ang), math.cos(ang)]),
            "world.user_active": np.array([1.0 if self.world.user_active else 0.0]),
            "world.fullscreen": np.array([1.0 if self.world.fullscreen else 0.0]),
        }

    def health_vector(self) -> np.ndarray:
        """[sick, severity, old]; exposed as the body.health channel."""
        return np.array([1.0 if self.health.sick else 0.0, self.health.severity,
                         1.0 if self.lifecycle.old else 0.0])

    def execute(self, proposed: str | None) -> tuple[str, bool]:
        if self.dead:
            return "idle", True
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
        if self.dead:
            self._t += seconds
            return
        h = seconds / B.HOUR
        for k in NEED_KEYS:
            cur = self.needs.values[k]
            self.needs.values[k] = max(cur, min(cur + B.NEED_RATES_PER_H[k] * h, B.OFFLINE_NEED_CAP))
        self._t += seconds
        prev_stage = self.stage
        self.lifecycle.update(seconds, self.needs.mean(), online=False)
        self._on_stage_change(prev_stage)
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
            "generation": self.generation, "lineage": list(self.lineage),
            "dead": self.dead, "death_cause": self.death_cause,
            "interest_s": dict(self.interest_s), "traits": list(self._traits),
            "last_message_t": None if self._last_message_t == -math.inf else self._last_message_t,
            "interact": None if self._interact_until == -math.inf
            else [self._interact_from, self._interact_until],
        }

    @classmethod
    def from_state_dict(cls, d: dict) -> "Kernel":
        k = cls(int(d["seed"]), float(d["t"]), int(d.get("generation", 1)))
        k.lineage = tuple(str(b) for b in d.get("lineage", ()))
        k.dead = bool(d.get("dead", False))
        k.death_cause = str(d.get("death_cause", ""))
        k.interest_s = {str(a): float(b) for a, b in d.get("interest_s", {}).items()}
        if d.get("traits") is not None:
            k.observe_traits(d["traits"])
        lm = d.get("last_message_t")
        k._last_message_t = -math.inf if lm is None else float(lm)
        k.genome = Genome.from_dict(d["genome"])
        k.rng.bit_generator.state = d["rng"]
        k.needs = Needs.from_dict(d["needs"])
        k.lifecycle = StageMachine.from_dict(d["lifecycle"])
        k.health = Health.from_dict(d.get("health", {}))
        k.world = WorldState.from_dict(d["world"])
        k.tracker = RewardTracker.from_dict(d["tracker"])
        k._queue = [Obs(float(e["t"]), e["kind"], dict(e["data"])) for e in d["queue"]]
        k._action = d["action"]
        k._action_start = float(d["action_start"])
        k._egg_clicks = int(d["egg_clicks"])
        if d.get("interact") is not None:
            k._interact_from, k._interact_until = (float(x) for x in d["interact"])
        return k
