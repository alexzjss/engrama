import time
from pathlib import Path
import numpy as np
import pytest
from engrama import balance as B
from engrama.kernel.branches import derive_seed
from engrama.lab.runtime import Runtime, run_days
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind.recipe import load_recipe
from engrama.vocab import INITIAL_TRAITS, TRAIT_KEYS

RECIPE = Path(__file__).resolve().parents[2] / "engrama" / "recipes" / "default-v1.toml"
DAY = 86400.0
BUDGET_RECIPE = "minimal-v1.toml"   # the default recipe (SNN) needs ~3.5 s per sim-day here


def _user(seed=1, profile="attentive"):
    return SimUser(PROFILES[profile], np.random.default_rng([seed, 1]))


def _q_module(rt):
    return next(m for m in rt.scheduler.modules().values() if "Q" in m.state_dict())


def _trait_module(rt):
    return next(m for m in rt.scheduler.modules().values() if "traits" in m.writes)


def _force_death(rt, cause="neglect"):
    rt.kernel.dead, rt.kernel.death_cause = True, cause


def test_rebirth_new_seed_and_mind():
    rt = Runtime(load_recipe(RECIPE), 7)
    rt.run(1.5 * DAY, 60.0, _user(7))
    assert np.any(_q_module(rt).state_dict()["Q"] != 0)
    vec = [0.9] * len(TRAIT_KEYS)
    rt.kernel.observe_traits(vec)
    _force_death(rt)
    t_before = rt.kernel.t
    summary = rt.rebirth()
    assert summary["generation"] == 1 and summary["seed"] == 7 and summary["cause"] == "neglect"
    assert summary["days"] > 1.0 and summary["final_traits"] == pytest.approx(vec)
    assert rt.seed == derive_seed(7, 2) != 7
    k = rt.kernel
    assert k.generation == 2 and not k.dead and k.stage == "egg" and k.t == t_before and k.seed == rt.seed
    assert np.all(_q_module(rt).state_dict()["Q"] == 0)
    traits = _trait_module(rt).state_dict()["traits"]
    for key in TRAIT_KEYS:
        want = INITIAL_TRAITS[key] + B.TRAIT_INHERIT * (90.0 - INITIAL_TRAITS[key])
        assert traits[key] == pytest.approx(want)
    assert rt.user is not None and rt._pending is None


def test_rebirth_save_load_bit_identical(tmp_path):
    recipe = load_recipe(RECIPE)

    def make():
        rt = Runtime(recipe, 5)
        rt.run(0.5 * DAY, 60.0, _user(5, "gamer"))
        _force_death(rt)
        rt.tick(60.0, [])
        rt.lives.append(rt.rebirth())
        return rt

    def acts(rt, seconds):
        out, end = [], rt.kernel.t + seconds
        while rt.kernel.t < end - 1e-9:
            out.append(rt.tick(60.0, rt.user.events(rt.kernel.t, 60.0, rt.creature())))
        return out

    ref = make()
    full = acts(ref, 6 * 3600.0)
    rt = make()
    first = acts(rt, 3 * 3600.0)
    rt.save(tmp_path / "save")
    rt2 = Runtime.load(tmp_path / "save")
    assert rt2.seed == rt.seed and rt2.kernel.generation == 2 and len(rt2.lives) == 1
    assert first + acts(rt2, 3 * 3600.0) == full
    assert rt2.kernel.state_dict() == ref.kernel.state_dict()


def test_dead_runtime_does_not_learn():
    rt = Runtime(load_recipe(RECIPE), 3)
    rt.run(0.5 * DAY, 60.0, _user(3))
    q0 = _q_module(rt).state_dict()["Q"].copy()
    _force_death(rt, "old_age")
    rt.tick(60.0, [])
    mem = [m.state_dict() for m in rt.scheduler.modules().values() if "Q" in m.state_dict()]
    t0 = rt.kernel.t
    for _ in range(120):
        assert rt.tick(60.0, rt.user.events(rt.kernel.t, 60.0, rt.creature())) == "idle"
    assert rt.kernel.t == pytest.approx(t0 + 7200.0) and rt.kernel.dead
    assert np.array_equal(_q_module(rt).state_dict()["Q"], q0) and len(mem) == 1


def test_run_rebirths_and_records_lives():
    rt = Runtime(load_recipe(RECIPE), 2)
    rt.user = _user(2)
    rt.run(600.0, 60.0)
    _force_death(rt)
    rt.run(600.0, 60.0)
    assert len(rt.lives) == 1 and rt.kernel.generation == 2 and not rt.kernel.dead
    rt3 = Runtime(load_recipe(RECIPE), 2)
    rt3.run(600.0, 60.0, _user(2))
    _force_death(rt3)
    rt3.run(600.0, 60.0, rebirth=False)
    assert rt3.lives == [] and rt3.kernel.dead


def _lives(profile, seed, days):
    rt = Runtime(load_recipe(RECIPE), seed)
    rt.run(days * DAY, 60.0, _user(seed, profile))
    return rt


NEGLECT_BRANCHES = {"arisco", "sombrio", "rebelde", "sombra"}


@pytest.mark.slow
def test_neglectful_dies_before_final():
    for seed in (1, 2):
        rt = _lives("neglectful", seed, 30)
        assert rt.lives, seed
        first = rt.lives[0]
        assert first["cause"] == "neglect" and first["final_day"] is None
        assert first["days"] < 30


@pytest.mark.slow
def test_attentive_reaches_final_and_dies_old():
    rt = _lives("attentive", 1, 110)
    first = rt.lives[0]
    assert first["cause"] == "old_age"
    # the stage minimums sum to 74.5 days, so "final" cannot come before that
    assert 74.4 <= first["final_day"] <= 90
    assert 105 <= first["days"] <= 125


@pytest.mark.slow
def test_profiles_branch_differently():
    att = _lives("attentive", 1, 40)
    neg = _lives("neglectful", 1, 40)
    lin_a = att.kernel.lineage
    assert lin_a and not NEGLECT_BRANCHES & set(lin_a)
    lins_n = [tuple(l["lineage"]) for l in neg.lives] + [neg.kernel.lineage]
    assert any(NEGLECT_BRANCHES & set(l) for l in lins_n)
    assert all(l != lin_a for l in lins_n)


@pytest.mark.slow
def test_200_days_under_8_min():
    t0 = time.time()
    m = run_days(RECIPE.with_name(BUDGET_RECIPE), 200, "attentive", 1, 60.0, None)
    assert time.time() - t0 < 480
    assert m["days_simulated"] == pytest.approx(200, rel=1e-3)
    assert m["lives"]["generations_finished"] >= 1
