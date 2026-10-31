import numpy as np
from engrama.mind.contracts import Blackboard, Observation
from engrama.modules.prefs.food import FoodPrefs
from engrama.vocab import FOOD_IDS, TRAIT_KEYS


def tr(**kw):
    d = {k: 0.5 for k in TRAIT_KEYS}
    d.update(kw)
    return d


def feed(fp, n, traits=None, food="carne"):
    bb = Blackboard()
    for _ in range(n):
        bb = Blackboard()
        if traits is not None:
            bb.write("traits", [traits[k] for k in TRAIT_KEYS])
        bb.events = (Observation(0.0, "food", {"food": food}),)
        fp.step(bb, 1.0)
    return bb


def mean_liking(traits, n, preset_count, seeds=30):
    vals = []
    for s in range(seeds):
        fp = FoodPrefs({}, np.random.default_rng(s))
        fp.liking[:] = 0.0
        fp.counts[0] = preset_count
        feed(fp, n, traits)
        vals.append(fp.liking[0])
    return float(np.mean(vals))


def test_food_prefs_differ_by_seed():
    a = FoodPrefs({}, np.random.default_rng(1))
    b = FoodPrefs({}, np.random.default_rng(2))
    assert not np.array_equal(a.liking, b.liking)
    assert np.array_equal(a.liking, FoodPrefs({}, np.random.default_rng(1)).liking)


def test_food_prefs_writes_channel():
    bb = feed(FoodPrefs({}, np.random.default_rng(1)), 1)
    assert bb.read("prefs.food").shape == (len(FOOD_IDS),)


def test_food_prefs_novelty_vs_comfort():
    # novelty phase (fewer than 3 meals): curious likes it more, incurious less
    assert mean_liking(tr(curiosidade=1.0), 3, 0) > 0.05 > -0.05 > mean_liking(tr(curiosidade=0.0), 3, 0)
    # comfort phase (3+ meals): patient likes it more, impatient less
    assert mean_liking(tr(paciencia=1.0), 10, 3) > 0.1 > -0.1 > mean_liking(tr(paciencia=0.0), 10, 3)


def test_state_roundtrips():
    fp = FoodPrefs({}, np.random.default_rng(1))
    feed(fp, 4)
    fp2 = FoodPrefs({}, np.random.default_rng(9))
    fp2.load_state_dict(fp.state_dict())
    assert np.array_equal(fp.liking, fp2.liking) and np.array_equal(fp.counts, fp2.counts)
