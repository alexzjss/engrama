import math
import numpy as np
import pytest
from engrama.lab.metrics import compute_metrics
from engrama.lab.explog import TickRow


def row(t, action, dt=10.0, rewards=None, shadow=None, needs=None, pad=None, surprise=None):
    ch = {}
    if needs is not None:
        ch["body.needs"] = np.array(needs)
    if pad is not None:
        ch["affect.pad"] = np.array(pad)
    if surprise is not None:
        ch["temporal.surprise"] = np.array([surprise])
    return TickRow(t, dt, action, 1.0, rewards or {}, [], [], shadow or [], ch)


def test_metrics_entropy_and_rates():
    rows = [row(10, "idle"), row(20, "idle"), row(30, "ask_attention", rewards={"user_response": 1.0}),
            row(40, "idle"), row(50, "ask_attention"), row(60, "idle", rewards={"ignored": 1.0})]
    m = compute_metrics(rows)
    assert m["ticks"] == 6 and m["ask_count"] == 2
    assert m["answered_rate"] == 0.5 and m["ignored_rate"] == 0.5
    assert m["action_share"] == {"idle": pytest.approx(4 / 6), "ask_attention": pytest.approx(2 / 6)}
    assert m["behavior_entropy"] == pytest.approx(-(2 / 3 * math.log2(2 / 3) + 1 / 3 * math.log2(1 / 3)))
    assert m["days_simulated"] == pytest.approx(60 / 86400)


def test_entropy_is_time_weighted():
    m = compute_metrics([row(1, "idle", dt=90.0), row(2, "wander", dt=10.0)])
    assert m["action_share"]["idle"] == pytest.approx(0.9)


def test_wellbeing_weighted_by_time_between_samples():
    ok, bad = [0.1] * 6, [0.95, 0, 0, 0, 0, 0]
    rows = [row(0, "idle", needs=ok), row(100, "idle", needs=bad), row(400, "idle", needs=ok),
            row(500, "idle", needs=ok)]
    assert compute_metrics(rows)["wellbeing"] == pytest.approx(1 - 300 / 500)


def test_pad_surprise_and_shadow_agreement():
    sh = lambda a, b: [{"source": "q", "action": a, "score": 1.0}, {"source": "q", "action": b, "score": 0.2}]
    rows = [row(1, "idle", pad=[0.2, 0, 0], surprise=0.4, shadow=sh("idle", "wander")),
            row(2, "wander", pad=[0.4, 0, 0], surprise=0.2, shadow=sh("idle", "wander"))]
    m = compute_metrics(rows)
    assert m["pad_mean"][0] == pytest.approx(0.3) and m["pad_std"][0] == pytest.approx(0.1)
    assert m["surprise_mean"] == pytest.approx(0.3)
    assert m["shadow_agreement"] == {"q": 0.5}


def test_empty_rows():
    m = compute_metrics([])
    assert m["ticks"] == 0 and m["wellbeing"] == 1.0
