import math
import numpy as np
from engrama import balance as B
from engrama.lab.runtime import Runtime
from engrama.mind.contracts import Experience, Observation
from engrama.modules.world.model import WorldModel, features, targets, N_IN, N_OUT
from engrama.vocab import ACTIONS, NEED_KEYS
from tests.modules import contract_kit as K


def chans(needs=None):
    a = 2 * math.pi * 10 / 24
    ch = {"world.hour": np.array([math.sin(a), math.cos(a)]), "world.user_active": np.array([1.0]),
          "body.asleep": np.array([0.0]), "affect.pad": np.array([0.2, -0.1, 0.0]),
          "drives": np.full(len(NEED_KEYS), 0.3)}
    ch["body.needs"] = np.full(len(NEED_KEYS), 0.5) if needs is None else np.asarray(needs, dtype=float)
    return ch


def exp(action="idle", events=(), dt=60.0, n0=None, n1=None):
    return Experience(0.0, dt, tuple(Observation(0.0, k) for k in events), chans(n0), action, 1.0, {}, chans(n1))


def test_features_targets_shapes_and_missing_channels():
    x = features({}, "play_alone")
    assert x.shape == (N_IN,) and x[13] == 1.0 and x[14 + ACTIONS.index("play_alone")] == 1.0 and x.sum() == 2.0
    assert features(chans(), "idle").shape == (N_IN,)
    y = targets(exp(events=("pet",)))
    assert y.shape == (N_OUT,) and y[1] == 1.0
    assert np.all(targets(Experience(0.0, 60.0, (), {}, "idle", 1.0, {}, {})) == 0)


def test_targets_need_rate_dt_invariant():
    d = 0.01
    a = targets(exp(dt=60.0, n0=np.full(6, 0.5), n1=np.full(6, 0.5 + d)))
    b = targets(exp(dt=1.0, n0=np.full(6, 0.5), n1=np.full(6, 0.5 + d / 60.0)))
    assert np.allclose(a, b) and a[-1] > 0


def test_error_drops_in_stationary_world():
    wm = WorldModel({}, np.random.default_rng(0))
    errs = []
    for i in range(800):
        act = ACTIONS[i % len(ACTIONS)]
        wm.learn(exp(act, events=("pet",) if act == "play_alone" else ()))
        errs.append(wm.last_error)
    assert np.mean(errs[-200:]) < 0.5 * np.mean(errs[:200])


def test_ignores_credit_experiences():
    wm = WorldModel({}, np.random.default_rng(0))
    wm.learn(exp(events=("pet",), dt=0.0))
    wm.learn(Experience(0.0, 60.0, (), chans(), "bogus", 1.0, {}, chans()))
    assert wm.n == 0 and wm.last_error == 0.0 and not wm.W.any()


def test_world_error_written_after_learn():
    rt = Runtime(K.recipe("curious-v1"), 1)
    from engrama.lab.simuser import PROFILES, SimUser
    rt.user = SimUser(PROFILES["attentive"], np.random.default_rng([1, 1]))
    wm = rt.scheduler.modules()["world.model"]
    for _ in range(30):
        K.actions(rt, 60.0)
        assert rt.bb.read("world.error")[0] == wm.last_error
    assert wm.n > 0


def test_world_model_no_rng(monkeypatch):
    K.assert_no_global_rng(monkeypatch, K.recipe("curious-v1"))
    wm = WorldModel({}, np.random.default_rng(0))
    st = wm.rng.bit_generator.state
    wm.learn(exp(events=("pet",)))
    assert wm.rng.bit_generator.state == st
