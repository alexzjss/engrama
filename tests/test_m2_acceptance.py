"""M2 acceptance: the default mind is stable, perceives novelty, differs from minimal, and individuates."""
import time
from pathlib import Path
import numpy as np
import pytest
from engrama import balance as B
from engrama.lab.explog import ExperienceLog, read_log
from engrama.lab.metrics import compute_metrics
from engrama.lab.runtime import Runtime, _Collector, run_days
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind.recipe import load_recipe
from engrama.vocab import FOOD_IDS, TRAIT_KEYS, INITIAL_TRAITS

RECIPES = Path(__file__).resolve().parents[1] / "recipes"
DEFAULT, MINIMAL = RECIPES / "default-v1.toml", RECIPES / "minimal-v1.toml"
DAY = 24 * B.HOUR


def _runtime(recipe: Path, profile: str, seed: int, log=None) -> Runtime:
    rt = Runtime(load_recipe(recipe), seed, log)
    rt.user = SimUser(PROFILES[profile], np.random.default_rng([seed, 1]))
    return rt


def _mod(rt: Runtime, name: str):
    return rt.scheduler.modules()[name]


@pytest.mark.slow
def test_default_recipe_30_days_stable():
    col = _Collector()
    rt = _runtime(DEFAULT, "attentive", 1, col)
    drift = _mod(rt, "traits.drift")
    t0 = time.perf_counter()
    for _ in range(30):
        before = dict(drift.traits)
        rt.run(DAY, 60.0)
        for k in TRAIT_KEYS:   # per-day cap (a day boundary can split a run, so allow two days' worth)
            assert abs(drift.traits[k] - before[k]) <= 2 * B.TRAIT_MAX_DRIFT_PER_DAY + 1e-6
    elapsed = time.perf_counter() - t0
    assert elapsed < 180
    assert all(s.enabled for s in rt.scheduler.status()), [(s.name, s.error) for s in rt.scheduler.status()]
    m = compute_metrics(col.rows)
    assert m["wellbeing"] > 0.5
    moved = [abs(drift.traits[k] - INITIAL_TRAITS[k]) for k in TRAIT_KEYS]
    assert max(moved) > 0
    assert all(d <= B.TRAIT_MAX_DRIFT_PER_DAY * 31 for d in moved)


def test_snn_measures_novelty_in_replay(tmp_path):
    db = tmp_path / "gamer.db"
    run_days(DEFAULT, 7, "gamer", 1, 60.0, db)
    rows = list(read_log(db))
    window = 24 * B.HOUR
    history: dict[str, list[float]] = {}
    rare, common = [], []
    for r in rows:
        kinds = {e["kind"] for e in r.events}
        if kinds and "temporal.surprise" in r.channels:
            counts = {}
            for k in kinds:
                counts[k] = sum(1 for t in history.get(k, ()) if r.t - window <= t < r.t)
            s = float(r.channels["temporal.surprise"][0])
            if any(c < 2 for c in counts.values()):
                rare.append(s)
            elif all(c >= 5 for c in counts.values()):
                common.append(s)
        for k in kinds:
            history.setdefault(k, []).append(r.t)
    assert len(rare) >= 3 and len(common) >= 3, (len(rare), len(common))
    assert np.mean(rare) > np.mean(common), (np.mean(rare), np.mean(common), len(rare), len(common))


@pytest.mark.slow
def test_recipes_differ_on_metric():
    a = run_days(MINIMAL, 10, "attentive", 1, 60.0, None)
    b = run_days(DEFAULT, 10, "attentive", 1, 60.0, None)
    d_ent = abs(b["behavior_entropy"] - a["behavior_entropy"])
    d_ans = abs(b["answered_rate"] - a["answered_rate"])
    assert max(d_ent, d_ans) > 0.01, (a["behavior_entropy"], b["behavior_entropy"], a["answered_rate"], b["answered_rate"])


@pytest.mark.slow
def test_creatures_diverge():
    out = []
    for seed in (1, 2):
        rt = _runtime(DEFAULT, "attentive", seed)
        rt.run(10 * DAY, 60.0)
        d = _mod(rt, "traits.drift").traits
        out.append((int(np.argmax(_mod(rt, "prefs.food").liking)), np.array([d[k] for k in TRAIT_KEYS])))
    l1 = float(np.abs(out[0][1] - out[1][1]).sum())
    assert out[0][0] != out[1][0] or l1 > 1.0, (out[0][0], out[1][0], l1)
