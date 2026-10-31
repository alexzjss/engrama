import numpy as np
import pytest

from engrama import balance as B
from engrama.kernel.needs import Needs
from engrama.vocab import NEED_KEYS


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
    assert m.values == n.values
    assert not hasattr(n, "empolgacao")


def test_needs_vector_order():
    n = Needs({"fome": 100, "apoio": 50, "sono": 25})
    v = n.as_vector()
    assert v.shape == (len(NEED_KEYS),)
    assert np.allclose(v, [1.0, 0.25, 0.0, 0.0, 0.0, 0.5])
