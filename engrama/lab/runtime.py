"""The simulation loop: kernel (body) + scheduler/arbiter (mind) + experience log."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import numpy as np
from engrama import balance as B
from engrama.kernel.kernel import Kernel
from engrama.kernel.sensors import Obs
from engrama.lab.explog import ExperienceLog, TickRow, read_log
from engrama.lab.metrics import compute_metrics
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind import registry
from engrama.mind.arbiter import SoftmaxArbiter
from engrama.mind.contracts import Blackboard, Experience, Observation, Proposal
from engrama.mind.recipe import ModuleSpec, Recipe, load_recipe
from engrama.mind.scheduler import Scheduler
from engrama.services.persistence import load_run, rng_from_state, rng_state, save_run


def _arr(d: dict) -> dict:
    return {k: np.asarray(v, dtype=np.float64) for k, v in d.items()}


def _lst(d: dict) -> dict:
    return {k: v.tolist() for k, v in d.items()}


def _props(ps: list[Proposal]) -> list[dict]:
    return [{"action": p.action, "score": p.score, "reason": p.reason, "source": p.source} for p in ps]


class Runtime:
    """Save/load persists the pending Experience (channels, action, prob, proposals), so a loaded
    runtime continues bit-identically to an uninterrupted one."""

    def __init__(self, recipe: Recipe, seed: int, log: ExperienceLog | None = None,
                 start_hour: float = 8.0) -> None:
        self.recipe, self.seed, self.start_hour, self.log = recipe, seed, start_hour, log
        # live modules, then the arbiter, then shadows: adding a shadow never shifts a live stream
        live_n = sum(not s.shadow for s in recipe.modules)
        rngs = np.random.default_rng(seed).spawn(len(recipe.modules) + 1)
        li = si = 0
        rng_of = []
        for sp in recipe.modules:
            if sp.shadow:
                rng_of.append(rngs[live_n + 1 + si]); si += 1
            else:
                rng_of.append(rngs[li]); li += 1
        mods = [registry.build(s, r) for s, r in zip(recipe.modules, rng_of)]
        self._scheduler = Scheduler(mods, list(recipe.modules))
        self._arbiter_rng = rngs[live_n]
        self._arbiter = SoftmaxArbiter({s.name: s.weight for s in recipe.modules if not s.shadow},
                                       float(recipe.arbiter["temperature"]),
                                       bool(recipe.arbiter["trait_temperature"]))
        self._kernel = Kernel(seed, start_hour * B.HOUR)
        self._bb = Blackboard()
        self.user: SimUser | None = None
        self._since_decision = 0.0
        self._pending: dict | None = None   # channels, action, prob, live, shadow
        self._last_action = ""

    bb = property(lambda self: self._bb)
    kernel = property(lambda self: self._kernel)
    scheduler = property(lambda self: self._scheduler)

    def tick(self, dt: float, events: list[Obs]) -> str:
        k, bb = self._kernel, self._bb
        k.ingest(events)
        evs, rewards = k.step(dt)
        for name, v in k.channels().items():
            bb.write(name, v)
        conv = tuple(Observation(e.t, e.kind, dict(e.data)) for e in evs)
        bb.events, bb.t, bb.available_actions = conv, k.t, k.available_actions()
        pend = self._pending
        if pend is not None:
            exp = Experience(bb.t, dt, conv, pend["channels"], pend["action"], pend["prob"], rewards,
                             bb.snapshot())
            self._scheduler.learn(exp)
            if self.log is not None:
                self.log.write(exp, pend["live"], pend["shadow"], pend.get("decided", True))
        self._scheduler.step(bb, dt)
        self._since_decision += dt
        channels = bb.snapshot()
        if pend is None or self._since_decision >= B.DECISION_PERIOD or k.action is None:
            self._since_decision = 0.0
            live, shadow = self._scheduler.proposals(bb)
            action, prob, _ = self._arbiter.choose(live, bb.available_actions, bb, self._arbiter_rng)
            running, forced = k.execute(action)
            self._pending = {"channels": channels, "action": running, "prob": 1.0 if forced else prob,
                             "live": live, "shadow": shadow, "decided": True}
        else:
            running, forced = k.execute(pend["action"])
            if forced or running != pend["action"]:
                self._pending = {**pend, "channels": channels, "action": running, "prob": 1.0,
                                  "decided": False}
            else:
                self._pending = {**pend, "channels": channels, "decided": False}
        self._last_action = running
        return running

    def creature(self) -> dict:
        k = self._kernel
        return {"action": self._last_action, "needs": k.needs.values, "stage": k.stage}

    def run(self, seconds: float, dt: float, user: SimUser | None = None) -> None:
        if user is not None:
            self.user = user
        end = self._kernel.t + seconds
        while self._kernel.t < end - 1e-9:
            step = min(dt, end - self._kernel.t)
            evs = self.user.events(self._kernel.t, step, self.creature()) if self.user else []
            self.tick(step, evs)

    def save(self, save_dir: Path) -> None:
        mods = self._scheduler.modules()
        pend = self._pending
        meta = {
            "seed": self.seed, "start_hour": self.start_hour, "recipe": asdict(self.recipe),
            "scheduler": self._scheduler.state_dict(),
            "arbiter_rng": rng_state(self._arbiter_rng),
            "module_rngs": {n: rng_state(m.rng) for n, m in mods.items()},
            "since_decision": self._since_decision, "last_action": self._last_action,
            "bb": {"channels": _lst(self._bb.snapshot()), "t": self._bb.t,
                   "available": list(self._bb.available_actions)},
            "pending": None if pend is None else {
                "channels": _lst(pend["channels"]), "action": pend["action"], "prob": pend["prob"],
                "live": _props(pend["live"]), "shadow": _props(pend["shadow"]),
                "decided": pend.get("decided", True)},
            "user": None if self.user is None else self.user.state_dict(),
        }
        save_run(Path(save_dir), self._kernel.state_dict(), {n: m.state_dict() for n, m in mods.items()}, meta)

    @classmethod
    def load(cls, save_dir: Path, log: ExperienceLog | None = None) -> "Runtime":
        kstate, mstates, meta = load_run(Path(save_dir))
        r = meta["recipe"]
        specs = tuple(ModuleSpec(m["type"], m["name"], m["params"], float(m["weight"]), bool(m["shadow"]))
                      for m in r["modules"])
        rt = cls(Recipe(r["name"], int(r["version"]), specs, r["arbiter"]),
                 int(meta["seed"]), log, float(meta["start_hour"]))
        rt._kernel = Kernel.from_state_dict(kstate)
        for n, m in rt._scheduler.modules().items():
            m.load_state_dict(mstates.get(n, {}))
            m.rng = rng_from_state(meta["module_rngs"][n])
        rt._scheduler.load_state_dict(meta["scheduler"])
        rt._arbiter_rng = rng_from_state(meta["arbiter_rng"])
        bb = meta["bb"]
        for name, v in bb["channels"].items():
            rt._bb.write(name, v)
        rt._bb.t, rt._bb.available_actions = float(bb["t"]), tuple(bb["available"])
        rt._since_decision, rt._last_action = float(meta["since_decision"]), meta["last_action"]
        p = meta["pending"]
        if p is not None:
            rt._pending = {"channels": _arr(p["channels"]), "action": p["action"], "prob": float(p["prob"]),
                           "live": [Proposal(**x) for x in p["live"]],
                           "shadow": [Proposal(**x) for x in p["shadow"]],
                           "decided": bool(p.get("decided", True))}
        if meta["user"] is not None:
            rt.user = SimUser.from_state_dict(meta["user"])
        return rt


class _Collector:
    """In-memory stand-in for ExperienceLog, so metrics need no file."""
    def __init__(self) -> None:
        self.rows: list[TickRow] = []
        self._last_sample = float("-inf")

    def write(self, exp: Experience, proposals: list[Proposal], shadow: list[Proposal],
              decided: bool = True) -> None:
        ch: dict = {}
        if exp.events or exp.t - self._last_sample >= B.EXPLOG_CHANNEL_SAMPLE_S:
            self._last_sample = exp.t
            ch = {n: np.asarray(v, dtype=np.float32) for n, v in exp.channels.items()}
        self.rows.append(TickRow(exp.t, exp.dt, exp.action, exp.action_prob, exp.rewards,
                                 [{"kind": o.kind} for o in exp.events], _props(proposals), _props(shadow), ch, decided))


def run_days(recipe_path: Path, days: float, profile: str, seed: int, dt: float,
             log_path: Path | None, save_dir: Path | None = None) -> dict:
    recipe = load_recipe(Path(recipe_path))
    log = (ExperienceLog(Path(log_path), f"{recipe.name}-{profile}-{seed}", recipe.name, seed)
           if log_path else _Collector())
    rt = Runtime(recipe, seed, log)
    user = SimUser(PROFILES[profile], np.random.default_rng([seed, 1]))
    rt.run(days * 24 * B.HOUR, dt, user)
    if save_dir is not None:
        rt.save(Path(save_dir))
    if log_path:
        log.close()
        return compute_metrics(read_log(Path(log_path)))
    return compute_metrics(log.rows)
