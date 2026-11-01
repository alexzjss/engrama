import time
import pytest
import numpy as np
from engrama.mind.contracts import Blackboard, Module, Proposal
from engrama.mind.recipe import ModuleSpec
from engrama.mind.scheduler import Scheduler


class Counter(Module):
    reads = (); writes = ()
    def __init__(self, name="c", rate=1.0, budget=5.0):
        super().__init__({}, np.random.default_rng(0))
        self.name = name; self.rate_hz = rate; self.budget_ms = budget; self.dts = []
    def step(self, bb, dt): self.dts.append(dt)
    def propose(self, bb): return [Proposal("idle", 1.0, "x")]


class Crasher(Counter):
    def step(self, bb, dt): raise RuntimeError("boom")


class Sleeper(Counter):
    def step(self, bb, dt): time.sleep(0.01)


class PadWriter(Counter):
    def step(self, bb, dt): bb.write("affect.pad", [0.5, 0.5, 0.5])


def sched(*mods, shadow=()):
    specs = [ModuleSpec("t", m.name, {}, shadow=m.name in shadow) for m in mods]
    return Scheduler(list(mods), specs)


def test_rate_respected():
    m = Counter(rate=0.1); s = sched(m); bb = Blackboard()
    for _ in range(60):
        s.step(bb, 1.0)
    assert len(m.dts) == 6
    assert all(abs(d - 10.0) < 1e-9 for d in m.dts)


def test_rate_with_long_dt():
    m = Counter(rate=1.0); s = sched(m); bb = Blackboard()
    for _ in range(3):
        s.step(bb, 60.0)
    assert m.dts == [60.0] * 3


def test_crashing_module_disabled_others_continue():
    bad = Crasher(name="bad"); good = Counter(name="good"); s = sched(bad, good); bb = Blackboard()
    for _ in range(3):
        s.step(bb, 1.0)
    st = {x.name: x for x in s.status()}
    assert not st["bad"].enabled and "boom" in st["bad"].error
    assert st["good"].enabled and len(good.dts) == 3
    live, _ = s.proposals(bb)
    assert [p.source for p in live] == ["good"]


def test_overbudget_demoted():
    m = Sleeper(budget=1.0); s = sched(m); bb = Blackboard()
    for _ in range(5):
        s.step(bb, 1.0)
    assert s.status()[0].rate_factor == 0.5


def test_shadow_writes_namespaced():
    live = Counter(name="live"); sh = PadWriter(name="sh")
    s = sched(live, sh, shadow=("sh",)); bb = Blackboard()
    bb.write("affect.pad", [0.1, 0.1, 0.1])
    s.step(bb, 1.0)
    assert np.allclose(bb.read("affect.pad"), 0.1)
    assert np.allclose(bb.read("shadow/sh/affect.pad"), 0.5)
    _, shadow_props = s.proposals(bb)
    assert [p.source for p in shadow_props] == ["sh"]


class NoneProposer(Counter):
    def propose(self, bb): return None


class BadItem(Counter):
    def propose(self, bb): return ["garbage"]


class BadAction(Counter):
    def propose(self, bb): return [Proposal("fly", 1.0, "x")]


class NoReason(Counter):
    def propose(self, bb): return [Proposal("idle", 1.0, " ")]


@pytest.mark.parametrize("cls", [NoneProposer, BadItem, BadAction, NoReason])
def test_bad_proposals_disable_module_only(cls):
    bad = cls(name="bad"); good = Counter(name="good"); s = sched(bad, good); bb = Blackboard()
    live, _ = s.proposals(bb)
    assert [p.source for p in live] == ["good"]
    st = {x.name: x for x in s.status()}
    assert not st["bad"].enabled and st["bad"].error


@pytest.mark.parametrize("rate", [0, -1.0])
def test_bad_rate_rejected_at_construction(rate):
    with pytest.raises(ValueError, match="rate_hz"):
        sched(Counter(rate=rate))


def test_duplicate_and_mismatched_names_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        Scheduler([Counter(name="a"), Counter(name="a")], [ModuleSpec("t", "a", {}), ModuleSpec("t", "a", {})])
    with pytest.raises(ValueError, match="match"):
        Scheduler([Counter(name="a")], [ModuleSpec("t", "b", {})])


def test_rate_mutated_to_zero_after_construction_isolated():
    bad = Counter(name="bad"); good = Counter(name="good"); s = sched(bad, good); bb = Blackboard()
    bad.rate_hz = 0
    s.step(bb, 1.0)
    assert len(good.dts) == 1 and not s.status()[0].enabled


class EventCounter(Counter):
    def __init__(self, name="e", rate=1.0):
        super().__init__(name=name, rate=rate)
        self.seen = []
    def step(self, bb, dt):
        self.seen.append([o.t for o in bb.events]); self.dts.append(dt)


def _ev(t):
    from engrama.mind.contracts import Observation
    return (Observation(t, "pet"),)


def test_slow_module_receives_every_event_since_last_run():
    m = EventCounter(rate=0.25); s = sched(m); bb = Blackboard()
    for i in range(8):
        bb.events = _ev(float(i)) if i != 2 else ()
        s.step(bb, 1.0)
    assert m.seen == [[0.0, 1.0, 3.0], [4.0, 5.0, 6.0, 7.0]]


def test_fast_module_sees_each_tick_events_and_shadow_too():
    m = EventCounter(name="f"); sh = EventCounter(name="sh", rate=0.5)
    s = sched(m, sh, shadow=("sh",)); bb = Blackboard()
    for i in range(4):
        bb.events = _ev(float(i))
        s.step(bb, 1.0)
    assert m.seen == [[0.0], [1.0], [2.0], [3.0]] and sh.seen == [[0.0, 1.0], [2.0, 3.0]]


def test_event_buffer_survives_state_roundtrip():
    m = EventCounter(rate=0.25); s = sched(m); bb = Blackboard()
    for i in range(2):
        bb.events = _ev(float(i)); s.step(bb, 1.0)
    m2 = EventCounter(rate=0.25); s2 = sched(m2); s2.load_state_dict(s.state_dict())
    for i in range(2, 4):
        bb.events = _ev(float(i)); s2.step(bb, 1.0)
    assert m2.seen == [[0.0, 1.0, 2.0, 3.0]]


def test_budgets_measured_but_not_enforced_when_off():
    m = Sleeper(budget=1.0)
    s = Scheduler([m], [ModuleSpec("t", m.name, {})], enforce_budgets=False); bb = Blackboard()
    for _ in range(12):
        s.step(bb, 1.0)
    st = s.status()[0]
    assert st.rate_factor == 1.0 and st.last_ms > 1.0 and s.state_dict()["runs"][m.name] == 12


def test_demotion_has_floor_and_recovers():
    from engrama import balance as B
    m = Sleeper(budget=1.0); s = sched(m); bb = Blackboard()
    for _ in range(60):
        s.step(bb, 100.0)
    assert s.status()[0].rate_factor == B.MODULE_MIN_RATE_FACTOR
    m.step = lambda bb, dt: None                     # now well within budget
    for _ in range(4 * B.MODULE_RECOVERY_RUNS + 10):
        s.step(bb, 100.0)
    assert s.status()[0].rate_factor == 1.0
