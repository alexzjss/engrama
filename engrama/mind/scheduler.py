"""Runs modules at their own rates with fault isolation and time budgets."""
from __future__ import annotations
import math
import time
from dataclasses import dataclass
from engrama import balance as B
from engrama.mind.contracts import Blackboard, Experience, Module, Observation, Proposal
from engrama.mind.recipe import ModuleSpec
from engrama.vocab import ACTIONS

@dataclass
class ModuleStatus:
    name: str
    enabled: bool = True
    rate_factor: float = 1.0
    strikes: int = 0
    good_runs: int = 0
    last_ms: float = 0.0
    mean_ms: float = 0.0
    error: str = ""
    shadow: bool = False

class ShadowBlackboard:
    """View of a Blackboard: writes go to shadow/<module>/<channel>; reads prefer that copy."""
    def __init__(self, bb: Blackboard, module: str, events=None) -> None:
        self._bb = bb; self._m = module
        if events is not None:
            self.events = events

    def _s(self, name: str) -> str:
        return f"shadow/{self._m}/{name}"

    def write(self, name: str, value) -> None:
        self._bb.write(self._s(name), value)

    def read(self, name: str):
        s = self._s(name)
        return self._bb.read(s if self._bb.has(s) else name)

    def get(self, name: str, default=None):
        s = self._s(name)
        return self._bb.get(s, self._bb.get(name, default))

    def has(self, name: str) -> bool:
        return self._bb.has(self._s(name)) or self._bb.has(name)

    def snapshot(self):
        return self._bb.snapshot()

    def __getattr__(self, item):
        return getattr(self._bb, item)

class _EventView:
    """Live-module view of a Blackboard whose `events` are everything since the module's last run."""
    def __init__(self, bb: Blackboard, events) -> None:
        self._bb = bb
        self.events = events

    def __getattr__(self, item):
        return getattr(self._bb, item)


class Scheduler:
    """enforce_budgets: demote modules that run over budget (wall-clock based, so NOT deterministic).
    Off => budgets are only measured. Demotion has a floor (MODULE_MIN_RATE_FACTOR) and recovers after
    MODULE_RECOVERY_RUNS in-budget runs. A module running below the tick rate always receives every event
    since its last run, whatever its rate."""
    def __init__(self, modules: list[Module], specs: list[ModuleSpec], enforce_budgets: bool = True) -> None:
        self.enforce_budgets = enforce_budgets
        names = [m.name for m in modules]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate module names: {sorted(n for n in set(names) if names.count(n) > 1)}")
        if names != [s.name for s in specs]:
            raise ValueError(f"module names {names} do not match spec names {[s.name for s in specs]}")
        for m in modules:
            if not isinstance(m.rate_hz, (int, float)) or not m.rate_hz > 0:
                raise ValueError(f"module {m.name!r}: rate_hz must be > 0, got {m.rate_hz!r}")
        self._mods = {m.name: m for m in modules}
        self._order = names
        self._st = {s.name: ModuleStatus(s.name, shadow=s.shadow) for s in specs}
        self._acc = {n: 0.0 for n in self._order}
        self._runs = {n: 0 for n in self._order}
        self._evbuf: dict[str, list[Observation]] = {n: [] for n in self._order}
        self._evticks = {n: 0 for n in self._order}

    def _view(self, name: str, bb: Blackboard, events=None):
        if self._st[name].shadow:
            return ShadowBlackboard(bb, name, events)
        return bb if events is None else _EventView(bb, events)

    def _fail(self, name: str, e: Exception) -> None:
        st = self._st[name]; st.enabled = False; st.error = repr(e)

    def step(self, bb: Blackboard, dt: float) -> None:
        for n in self._order:
            st = self._st[n]
            if not st.enabled:
                continue
            m = self._mods[n]
            try:
                self._acc[n] += dt
                self._evbuf[n].extend(bb.events)
                self._evticks[n] += 1
                due = self._acc[n] >= 1.0 / (m.rate_hz * st.rate_factor) - 1e-9
            except Exception as e:
                self._fail(n, e)
                continue
            if not due:
                continue
            adt, self._acc[n] = self._acc[n], 0.0
            # run every tick => this tick's events as-is; otherwise everything since the last run
            events = tuple(self._evbuf[n]) if self._evticks[n] > 1 else None
            self._evbuf[n], self._evticks[n] = [], 0
            t0 = time.perf_counter()
            try:
                m.step(self._view(n, bb, events), adt)
            except Exception as e:
                self._fail(n, e)
                continue
            ms = (time.perf_counter() - t0) * 1000.0
            self._runs[n] += 1
            st.last_ms = ms
            st.mean_ms += (ms - st.mean_ms) / self._runs[n]
            if not self.enforce_budgets:
                continue
            if ms > m.budget_ms:
                st.good_runs = 0
                st.strikes += 1
                if st.strikes >= B.MODULE_OVERBUDGET_STRIKES:
                    st.rate_factor = max(st.rate_factor * 0.5, B.MODULE_MIN_RATE_FACTOR); st.strikes = 0
            else:
                st.strikes = 0
                if st.rate_factor < 1.0:
                    st.good_runs += 1
                    if st.good_runs >= B.MODULE_RECOVERY_RUNS:
                        st.rate_factor = min(1.0, st.rate_factor * 2.0); st.good_runs = 0

    def proposals(self, bb: Blackboard) -> tuple[list[Proposal], list[Proposal]]:
        live: list[Proposal] = []; shadow: list[Proposal] = []
        for n in self._order:
            st = self._st[n]
            if not st.enabled:
                continue
            try:
                props = []
                for p in self._mods[n].propose(self._view(n, bb)):
                    if not isinstance(p, Proposal):
                        raise TypeError(f"propose() returned non-Proposal {p!r}")
                    if not math.isfinite(p.score):
                        raise ValueError(f"non-finite score {p.score!r}")
                    if p.action not in ACTIONS:
                        raise ValueError(f"unknown action {p.action!r}")
                    if not isinstance(p.reason, str) or not p.reason.strip():
                        raise ValueError("proposal reason must be non-empty")
                    props.append(Proposal(p.action, float(p.score), p.reason, n))
            except Exception as e:
                self._fail(n, e)
                continue
            (shadow if st.shadow else live).extend(props)
        return live, shadow

    def learn(self, exp: Experience) -> None:
        for n in self._order:
            if not self._st[n].enabled:
                continue
            try:
                self._mods[n].learn(exp)
            except Exception as e:
                self._fail(n, e)

    def state_dict(self) -> dict:
        return {"acc": dict(self._acc), "runs": dict(self._runs),
                "evbuf": {n: [[o.t, o.kind, dict(o.data)] for o in b] for n, b in self._evbuf.items()},
                "evticks": dict(self._evticks),
                "status": {n: {"enabled": s.enabled, "rate_factor": s.rate_factor, "strikes": s.strikes,
                               "good_runs": s.good_runs, "error": s.error} for n, s in self._st.items()}}

    def load_state_dict(self, d: dict) -> None:
        for n in self._order:
            self._acc[n] = float(d["acc"][n]); self._runs[n] = int(d["runs"][n])
            st, o = self._st[n], d["status"][n]
            st.enabled, st.rate_factor = bool(o["enabled"]), float(o["rate_factor"])
            st.strikes, st.error = int(o["strikes"]), str(o["error"])
            st.good_runs = int(o.get("good_runs", 0))
            self._evbuf[n] = [Observation(float(t), k, dict(data)) for t, k, data in d.get("evbuf", {}).get(n, [])]
            self._evticks[n] = int(d.get("evticks", {}).get(n, 0))

    def status(self) -> list[ModuleStatus]:
        return [self._st[n] for n in self._order]

    def modules(self) -> dict[str, Module]:
        return dict(self._mods)
