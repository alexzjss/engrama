import time
import numpy as np
from engrama import balance as B
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


def sched(*mods, **kw):
    return Scheduler(list(mods), [ModuleSpec("t", m.name, {}) for m in mods], **kw)


def test_rest_slows_all_modules_and_restores():
    a, b = Counter("a", 1.0), Counter("b", 2.0)
    s = sched(a, b); bb = Blackboard()
    s.set_rest(True)
    assert all(st.rate_factor == B.MODULE_MIN_RATE_FACTOR for st in s.status())
    for _ in range(16):
        s.step(bb, 1.0)
    assert len(a.dts) == 2          # 1 Hz / 8 -> every 8 s
    s.set_rest(True)                # idempotent: must not overwrite the saved factors
    s.set_rest(False)
    assert all(st.rate_factor == 1.0 for st in s.status())
    n = len(a.dts)
    s.step(bb, 1.0); s.step(bb, 1.0)
    assert len(a.dts) == n + 2


def test_rest_restores_previous_demotion():
    a = Counter("a")
    s = sched(a)
    s._st["a"].rate_factor = 0.5
    s.set_rest(True); s.set_rest(False)
    assert s.status()[0].rate_factor == 0.5


def test_rest_is_saved():
    a = Counter("a")
    s = sched(a)
    s.set_rest(True)
    d = s.state_dict()
    assert d["rest"] is True
    s2 = sched(Counter("a"))
    s2.load_state_dict(d)
    assert s2.resting and s2.status()[0].rate_factor == B.MODULE_MIN_RATE_FACTOR
    s2.set_rest(False)
    assert s2.status()[0].rate_factor == 1.0


def test_old_state_dict_without_rest_loads():
    s = sched(Counter("a"))
    d = s.state_dict(); d.pop("rest"); d.pop("rest_saved")
    sched(Counter("a")).load_state_dict(d)


def test_budget_recovery_does_not_undo_rest():
    class Slow(Counter):
        def step(self, bb, dt): time.sleep(0.003)
    m = Slow(budget=100.0); s = sched(m, enforce_budgets=True); bb = Blackboard()
    s.set_rest(True)
    for _ in range(B.MODULE_RECOVERY_RUNS * 9 + 10):
        s.step(bb, 1.0)
    assert s.status()[0].rate_factor == B.MODULE_MIN_RATE_FACTOR
