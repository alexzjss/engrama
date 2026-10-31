import numpy as np
from engrama.lab.simuser import PROFILES, SimUser
from engrama.vocab import FOOD_IDS


def _u(name="attentive", seed=1):
    return SimUser(PROFILES[name], np.random.default_rng(seed))


def _creature(**kw):
    return {"action": "idle", "needs": {"fome": 0.0}, "stage": "child", **kw}


def test_profiles_present_and_ordered():
    assert set(PROFILES) == {"attentive", "absent", "night_owl", "gamer"}
    assert PROFILES["attentive"].answer_prob == 0.8 and PROFILES["absent"].answer_prob == 0.1


def test_active_edges_and_inactive_silence():
    u = _u()
    assert [e.kind for e in u.events(3 * 3600.0, 60.0, _creature())] == []  # 03:00, idle at start
    assert [e.kind for e in u.events(8 * 3600.0, 60.0, _creature())][0] == "user_active"
    assert [e.kind for e in u.events(22 * 3600.0, 60.0, _creature())] == ["user_idle"]
    assert u.events(23 * 3600.0, 60.0, _creature(needs={"fome": 100.0})) == []


def test_feeds_when_hungry_only_active_hours():
    u = _u()
    ev = u.events(10 * 3600.0, 60.0, _creature(needs={"fome": 90.0}))
    foods = [e for e in ev if e.kind == "food"]
    assert len(foods) == 1 and foods[0].data["food"] in FOOD_IDS
    assert not [e for e in _u(seed=2).events(10 * 3600.0, 60.0, _creature(needs={"fome": 10.0})) if e.kind == "food"]


def test_answers_ask_within_window():
    answered = 0
    for s in range(200):
        u = _u(seed=s)
        t = 10 * 3600.0
        u.events(t, 60.0, _creature())
        got = []
        for i in range(3):
            got += [e for e in u.events(t + 60.0 * i, 60.0, _creature(action="ask_attention")) if e.kind == "answered"]
        answered += bool(got)
        assert all(0 <= e.t - t <= 120.0 for e in got)
    assert 0.6 < answered / 200 < 0.95


def test_egg_gets_clicks():
    u = _u()
    clicks = sum(e.kind == "click" for i in range(120)
                 for e in u.events(10 * 3600.0 + 60.0 * i, 60.0, _creature(stage="egg")))
    assert clicks >= 5


def test_state_roundtrip():
    a, b = _u(seed=5), None
    for i in range(50):
        a.events(10 * 3600.0 + 60.0 * i, 60.0, _creature(action="ask_attention"))
    b = SimUser.from_state_dict(a.state_dict())
    ev = lambda u: [(e.t, e.kind, e.data) for i in range(50, 100)
                    for e in u.events(10 * 3600.0 + 60.0 * i, 60.0, _creature())]
    assert ev(a) == ev(b)
