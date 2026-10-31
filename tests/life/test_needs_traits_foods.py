import random

import pytest

from engrama.core import balance as B
from engrama.life.foods import FOODS, Tastes
from engrama.life.needs import NEED_KEYS, Needs
from engrama.life.traits import Traits


def test_needs_decay_one_hour():
    n = Needs()
    n.decay(B.HOUR, awake=True, interacting=False)
    assert n.values["fome"] == pytest.approx(14.3)
    assert n.values["tedio"] == pytest.approx(66.7)
    assert n.values["sono"] == pytest.approx(6.25)


def test_needs_interacting_freezes_tedio_carinho():
    n = Needs()
    n.decay(B.HOUR, awake=True, interacting=True)
    assert n.values["tedio"] == 0 and n.values["carinho"] == 0
    assert n.values["fome"] > 0


def test_needs_sleep_recovers():
    n = Needs({"sono": 80, "fome": 10})
    n.decay(B.HOUR, awake=False, interacting=False)
    assert n.values["sono"] == pytest.approx(80 - B.SLEEP_RECOVERY_PER_H)
    assert n.values["fome"] == pytest.approx(10 + 14.3 / 2)


def test_needs_clamped_under_spam():
    n = Needs({"fome": 50, "carinho": 50})
    for _ in range(200):
        n.apply({"fome": -40, "carinho": -30})
    assert all(0 <= v <= 100 for v in n.values.values())
    for _ in range(200):
        n.apply({"fome": 40})
    assert n.values["fome"] == 100


def test_needs_top_mean_roundtrip():
    n = Needs({"fome": 90, "tedio": 60, "sono": 10})
    assert n.top(2) == [("fome", 90), ("tedio", 60)]
    assert n.top(5, threshold=95) == []
    assert n.mean() == pytest.approx(160 / len(NEED_KEYS))
    m = Needs.from_dict(n.to_dict())
    assert m.values == n.values and m.empolgacao == n.empolgacao


def test_trait_drift_daily_cap():
    t = Traits()
    for _ in range(10):
        t.drift("curiosidade", 1, day_index=0)
    assert t.values["curiosidade"] == pytest.approx(52)
    for _ in range(10):
        t.drift("curiosidade", 1, day_index=1)
    assert t.values["curiosidade"] == pytest.approx(54)
    for _ in range(10):
        t.drift("curiosidade", -1, day_index=1)
    assert t.values["curiosidade"] == pytest.approx(54)
    for _ in range(10):
        t.drift("curiosidade", -1, day_index=2)
    assert t.values["curiosidade"] == pytest.approx(52)
    assert Traits.from_dict(t.to_dict()).values == t.values


def test_trait_adjectives_pt_en():
    t = Traits()
    assert any("paciente" in a for a in t.adjectives("pt"))
    assert "patient" in t.adjectives("en")
    t.values["curiosidade"] = 10
    assert t.adjectives("pt")[0] == "pouco curiosa"
    assert len(t.adjectives("pt")) <= 2
    t.values.update({k: 50 for k in t.values})
    assert t.adjectives("pt") == []


def test_tastes_deterministic_per_seed():
    a, b, c = Tastes(7, Traits()), Tastes(7, Traits()), Tastes(8, Traits())
    assert a.scores == b.scores
    assert a.scores != c.scores
    assert all(-1 <= s <= 1 for s in a.scores.values())
    assert Tastes.from_dict(a.to_dict(), Traits()).scores == a.scores


def test_disliked_food_refused_sometimes():
    refused = 0
    for i in range(100):
        t = Tastes(1, Traits())
        t.scores["bug"] = -0.9
        ok, delta = t.eat("bug", random.Random(i))
        if not ok:
            refused += 1
            assert delta == {}
        else:
            assert delta["fome"] == pytest.approx(FOODS["bug"].effects["fome"] / 2)
    assert 40 <= refused <= 80


def test_liked_food_bonus():
    t = Tastes(1, Traits())
    t.scores["carne"] = 0.9
    ok, delta = t.eat("carne", random.Random(0))
    assert ok and delta["fome"] == -40 and delta["carinho"] == -13 and delta["tedio"] == -5


def test_foods_min_stage():
    assert len(FOODS) == 10
    assert FOODS["ram"].min_stage == "child" and FOODS["ram"].digital
    assert FOODS["ram"].effects == {"fome": -15, "sono": -10}
    assert all(f.min_stage == "baby" for f in FOODS.values() if f.digital and f.id != "ram")
    assert all(f.min_stage for f in FOODS.values())
