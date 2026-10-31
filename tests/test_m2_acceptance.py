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
    start = dict(drift.traits)
    per_day_max = 0.0
    day = drift.day
    while rt.kernel.t < 30 * DAY:
        rt.run(600.0, 60.0)
        if drift.day != day:           # a new day bucket opened: the previous one is closed
            day, start = drift.day, dict(drift.traits)
        for k in TRAIT_KEYS:           # drift inside the open day bucket never exceeds the cap
            moved = abs(drift.traits[k] - start[k])
            per_day_max = max(per_day_max, moved)
            assert drift.used[k] <= B.TRAIT_MAX_DRIFT_PER_DAY + 1e-9
            assert moved <= B.TRAIT_MAX_DRIFT_PER_DAY + 1e-9
    elapsed = time.perf_counter() - t0
    assert elapsed < 180
    assert all(s.enabled for s in rt.scheduler.status()), [(s.name, s.error) for s in rt.scheduler.status()]
    m = compute_metrics(col.rows)
    assert m["wellbeing"] > 0.5
    moved = [abs(drift.traits[k] - INITIAL_TRAITS[k]) for k in TRAIT_KEYS]
    assert max(moved) > 0


def _surprise_after_events(seed: int, days: float = 7.0):
    """Post-event surprise: read temporal.surprise AFTER the tick that processed the events."""
    rt = _runtime(DEFAULT, "gamer", seed)
    hist: dict[str, list[float]] = {}
    rare, common = [], []
    end = days * DAY
    while rt.kernel.t < end:
        rt.run(60.0, 60.0)
        kinds = {o.kind for o in rt.bb.events}
        if not kinds:
            continue
        t = rt.bb.t
        counts = {k: sum(1 for x in hist.get(k, ()) if t - DAY <= x < t) for k in kinds}
        s = float(rt.bb.read("temporal.surprise")[0])
        if any(c < 2 for c in counts.values()):
            rare.append(s)
        elif all(c >= 5 for c in counts.values()):
            common.append(s)
        for k in kinds:
            hist.setdefault(k, []).append(t)
    return rare, common


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snn_measures_novelty_in_replay(seed):
    rare, common = _surprise_after_events(seed)
    assert len(rare) >= 30 and len(common) >= 30, (len(rare), len(common))
    ratio = np.mean(rare) / np.mean(common)
    print("NOVELTY", seed, len(rare), len(common), np.mean(rare), np.mean(common), ratio)
    assert ratio >= 1.1, (ratio, len(rare), len(common))


@pytest.mark.slow
def test_recipes_differ_on_metric():
    a = run_days(MINIMAL, 10, "attentive", 1, 60.0, None)
    b = run_days(DEFAULT, 10, "attentive", 1, 60.0, None)
    d_ent = abs(b["behavior_entropy"] - a["behavior_entropy"])
    d_ans = abs(b["answered_rate"] - a["answered_rate"])
    assert max(d_ent, d_ans) > 0.01, (a["behavior_entropy"], b["behavior_entropy"], a["answered_rate"], b["answered_rate"])


def _final(profile: str, seed: int, days: int = 10):
    rt = _runtime(DEFAULT, profile, seed)
    rt.run(days * DAY, 60.0)
    tr = _mod(rt, "traits.drift").traits
    return int(np.argmax(_mod(rt, "prefs.food").liking)), np.array([tr[k] for k in TRAIT_KEYS])


@pytest.mark.slow
@pytest.mark.parametrize("pair", [(1, 2), (3, 4)])
def test_creatures_diverge(pair):
    (fa, ta), (fb, tb) = _final("attentive", pair[0]), _final("attentive", pair[1])
    l1 = float(np.abs(ta - tb).sum())
    assert fa != fb or l1 > 1.0, (fa, fb, l1)


@pytest.mark.slow
def test_profiles_shape_different_personalities():
    _, ta = _final("attentive", 1)
    _, tb = _final("absent", 1)
    assert float(np.abs(ta - tb).sum()) > 10.0, (ta, tb)


class _RoutineUser:
    """Scripted periodic user: the same schedule every day, no randomness."""
    _WINDOWS = ((9, 12, "message", 3), (14, 16, "pet", 4))   # (from h, to h, kind, every n ticks)

    def __init__(self, dt: float) -> None:
        self.dt = dt
        self._active = False

    def events(self, t, dt, creature):
        from engrama.kernel.sensors import Obs
        out = []
        h = (t / B.HOUR) % 24.0
        active = 8 <= h < 22
        if active != self._active:
            self._active = active
            out.append(Obs(t, "user_active" if active else "user_idle"))
        k = int(round(t / self.dt))
        for a, b, kind, n in self._WINDOWS:
            if a <= h < b and k % n == 0:
                out.append(Obs(t, kind, {"valence": 0.5} if kind == "message" else {}))
        return out

    def state_dict(self):
        return {}


def _brier(readout_hidden: bool, seed: int = 1, days: int = 4, dt: float = 60.0) -> float:
    import dataclasses
    from engrama.vocab import EVENT_KINDS
    rec = load_recipe(DEFAULT)
    mods = tuple(dataclasses.replace(s, params={**s.params, "readout_hidden": readout_hidden})
                 if s.type == "temporal.snn" else s for s in rec.modules)
    rt = Runtime(dataclasses.replace(rec, modules=mods), seed)
    rt.user = _RoutineUser(dt)
    prev, errs = None, []
    while rt.kernel.t < days * DAY:
        rt.run(dt, dt)
        kinds = {o.kind for o in rt.bb.events}
        if prev is not None and rt.kernel.t > days * DAY / 2:
            y = np.array([1.0 if k in kinds else 0.0 for k in EVENT_KINDS])
            errs.append(float(np.mean((prev - y) ** 2)))
        prev = np.asarray(rt.bb.read("temporal.expectation"), dtype=float).copy()
    return float(np.mean(errs))


@pytest.mark.slow
def test_snn_beats_ablation_on_routine_prediction():
    full, abl = _brier(True), _brier(False)
    print("BRIER", full, abl)
    assert full < abl, (full, abl)
