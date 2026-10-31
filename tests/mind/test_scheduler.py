import time
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
