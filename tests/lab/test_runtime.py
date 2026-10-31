import time
from pathlib import Path
import numpy as np
import pytest
from engrama.lab.explog import ExperienceLog, read_log
from engrama.lab.metrics import compute_metrics
from engrama.lab.runtime import Runtime, run_days
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind import registry
from engrama.mind.contracts import Module
from engrama.mind.recipe import ModuleSpec, Recipe, load_recipe

RECIPE = Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml"
DAY = 86400.0


def _user(seed=1, profile="attentive"):
    return SimUser(PROFILES[profile], np.random.default_rng([seed, 1]))


def _actions(rt, seconds, dt=60.0):
    out = []
    end = rt.kernel.t + seconds
    while rt.kernel.t < end - 1e-9:
        out.append(rt.tick(dt, rt.user.events(rt.kernel.t, dt, rt.creature())))
    return out


def test_tick_order_and_experience_alignment(tmp_path):
    log = ExperienceLog(tmp_path / "l.db", "r", "minimal-v1", 1)
    rt = Runtime(load_recipe(RECIPE), 1, log)
    rt.user = _user()
    chosen = _actions(rt, 3600.0)
    log.close()
    rows = list(read_log(tmp_path / "l.db"))
    assert len(rows) == len(chosen) - 1
    assert [r.action for r in rows] == chosen[:-1]
    assert rows[0].t == pytest.approx(8 * 3600.0 + 120.0) and rows[0].dt == 60.0
    assert all(set(r.rewards) >= {"need_relief", "ignored"} for r in rows)


def test_same_seed_same_log(tmp_path):
    for n in ("a", "b"):
        run_days(RECIPE, 1, "attentive", 3, 60.0, tmp_path / f"{n}.db")
    a, b = (list(read_log(tmp_path / f"{n}.db")) for n in ("a", "b"))
    assert [(r.t, r.action, r.prob, r.rewards) for r in a] == [(r.t, r.action, r.prob, r.rewards) for r in b]


def test_save_load_continue_identical(tmp_path):
    recipe = load_recipe(RECIPE)
    ref = Runtime(recipe, 2); ref.user = _user(2)
    full = _actions(ref, 3 * DAY)
    rt = Runtime(recipe, 2); rt.user = _user(2)
    first = _actions(rt, 2 * DAY)
    rt.save(tmp_path / "save")
    rt2 = Runtime.load(tmp_path / "save")
    assert rt2.user is not None
    assert first + _actions(rt2, DAY) == full
    assert rt2.kernel.state_dict()["needs"] == ref.kernel.state_dict()["needs"]


class Broken(Module):
    reads = (); writes = ()
    def step(self, bb, dt): raise RuntimeError("boom")
    def propose(self, bb): raise RuntimeError("boom")


def test_creature_never_stalls_with_broken_module():
    registry.register("test.broken", f"{__name__}:Broken")
    try:
        base = load_recipe(RECIPE)
        recipe = Recipe("broken", 1, (ModuleSpec("test.broken", "bad", {}),) + base.modules, base.arbiter)
        rt = Runtime(recipe, 1); rt.user = _user()
        acts = _actions(rt, DAY)
        assert all(a for a in acts) and len(set(acts)) > 2
        assert not [s for s in rt.scheduler.status() if s.name == "bad"][0].enabled
    finally:
        registry.REGISTRY.pop("test.broken", None)


def test_creature_acts_with_only_broken_module():
    registry.register("test.broken", f"{__name__}:Broken")
    try:
        rt = Runtime(Recipe("b", 1, (ModuleSpec("test.broken", "bad", {}),), {"temperature": 1.0, "trait_temperature": True}), 1)
        rt.user = _user()
        assert all(_actions(rt, 3600.0))
    finally:
        registry.REGISTRY.pop("test.broken", None)


def test_simuser_profiles_differ():
    rates = {p: run_days(RECIPE, 3, p, 1, 60.0, None)["answered_rate"] for p in ("attentive", "absent")}
    assert rates["attentive"] > rates["absent"]


@pytest.mark.slow
def test_30_days_under_2_minutes(tmp_path):
    t0 = time.perf_counter()
    m = run_days(RECIPE, 30, "attentive", 1, 60.0, tmp_path / "m1.db")
    assert time.perf_counter() - t0 < 120.0
    assert m["wellbeing"] > 0.5
    assert all(np.isfinite(m["pad_mean"])) and all(np.isfinite(m["pad_std"]))
    assert not any(np.isnan(r.channels["affect.pad"]).any()
                   for r in read_log(tmp_path / "m1.db") if "affect.pad" in r.channels)


class NanModule(Module):
    reads = (); writes = ()
    def propose(self, bb):
        from engrama.mind.contracts import Proposal
        return [Proposal("idle", float("nan"), "nan")]


def test_nan_proposal_never_crashes_tick():
    registry.register("test.nan", f"{__name__}:NanModule")
    try:
        base = load_recipe(RECIPE)
        recipe = Recipe("nan", 1, (ModuleSpec("test.nan", "nan", {}),) + base.modules, base.arbiter)
        rt = Runtime(recipe, 1); rt.user = _user()
        assert all(_actions(rt, 3600.0))
        assert not [s for s in rt.scheduler.status() if s.name == "nan"][0].enabled
    finally:
        registry.REGISTRY.pop("test.nan", None)


def test_forced_continuation_logs_prob_one_at_dt1():
    from engrama.kernel.sensors import Obs
    rt = Runtime(load_recipe(RECIPE), 1)
    rt.tick(1.0, [Obs(rt.kernel.t, "click") for _ in range(5)])
    for _ in range(30):
        rt.tick(1.0, [])
    assert rt.kernel.action not in (None, "hide") and rt._since_decision < 5.0   # continuation branch
    rt.tick(1.0, [Obs(rt.kernel.t, "fullscreen_on")])
    assert rt.kernel.world.fullscreen
    assert rt._last_action == "hide" and rt._pending["action"] == "hide" and rt._pending["prob"] == 1.0
