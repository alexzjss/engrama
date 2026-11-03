import math
import numpy as np
import pytest
from engrama import balance as B
from engrama.mind.contracts import Blackboard, Experience, Observation
from engrama.modules.policy.curious import CuriousQPolicy
from engrama.modules.policy.qlearning import QLearningPolicy, state_index
from engrama.modules.world.model import WorldModel
from engrama.vocab import ACTIONS, NEED_KEYS
from tests.modules import contract_kit as K

RNG = lambda: np.random.default_rng(0)


def chans(hour=3, active=1, pad=(0.5, 0.5, 0.0), err=None):
    a = 2 * math.pi * hour / 24
    ch = {"world.hour": np.array([math.sin(a), math.cos(a)]), "world.user_active": np.array([float(active)]),
          "affect.pad": np.array(pad), "body.asleep": np.array([0.0]), "drives": np.full(len(NEED_KEYS), 0.3),
          "body.needs": np.full(len(NEED_KEYS), 0.5)}
    if err is not None:
        ch["world.error"] = np.array([err])
    return ch


def exp(ch, action, rewards=None, nxt=None, dt=60.0, events=()):
    return Experience(0.0, dt, tuple(Observation(0.0, k) for k in events), ch, action, 1.0, rewards or {},
                      nxt if nxt is not None else ch)


def test_beta_zero_is_q_learning_lagged_by_one():
    rng = np.random.default_rng(5)
    chs = [chans(hour=int(rng.integers(0, 24)), active=int(rng.integers(0, 2)),
                 pad=tuple(rng.uniform(-1, 1, 3)), err=float(rng.random())) for _ in range(41)]
    es = [exp(chs[i], ACTIONS[int(rng.integers(0, 8))], {"petting": float(rng.random()), "need_pain": -0.1 * i % 1},
              nxt=chs[i + 1]) for i in range(40)]
    cur = CuriousQPolicy({"beta": 0.0}, RNG())
    ql = QLearningPolicy({}, RNG())
    for e in es:
        cur.learn(e)
    for e in es[:-1]:
        ql.learn(e)
    assert np.array_equal(cur.Q, ql.Q) and np.array_equal(cur.visits, ql.visits)


def pipeline(cur, wm, steps, seed=0, hot="explore"):
    rng = np.random.default_rng(seed)
    bb = Blackboard()
    ch = chans()
    bb.write("world.error", [0.0])
    prev = None
    for _ in range(steps):
        act = ACTIONS[int(rng.integers(0, len(ACTIONS)))]
        evs = tuple(k for k in ("click", "pet", "message", "food", "answered") if rng.random() < 0.5) \
            if act == hot else ()
        e = exp(dict(ch, **{"world.error": bb.read("world.error")}), act, {}, nxt=ch, events=evs)
        wm.learn(e)
        cur.learn(e)
        wm.step(bb, 60.0)
    return cur


def test_bonus_credited_to_transition_action():
    cur = CuriousQPolicy({"beta": 1.0}, RNG())
    pipeline(cur, WorldModel({}, RNG()), 400)
    s = state_index(chans())
    x = ACTIONS.index("explore")
    assert cur.Q[s, x] > max(cur.Q[s, i] for i in range(len(ACTIONS)) if i != x)


def test_credit_experience_applied_immediately_without_bonus():
    cur = CuriousQPolicy({"beta": 1.0}, RNG())
    ch = chans(err=1.0)
    cur.learn(exp(ch, "ask_attention", {"user_response": 1.0}, dt=0.0))
    ql = QLearningPolicy({}, RNG())
    ql.learn(exp(ch, "ask_attention", {"user_response": 1.0}, dt=0.0))
    assert np.array_equal(cur.Q, ql.Q) and cur.held is None and cur.n_b == 0
    cur.learn(exp(ch, "idle"))
    held = cur.held
    cur.learn(exp(ch, "ask_attention", {"ignored": 1.0}, dt=0.0))
    assert cur.held == held and cur.n_b == 0


def test_progress_bonus_returns_to_zero_when_error_flat():
    cur = CuriousQPolicy({"bonus": "progress"}, RNG())
    for i in range(100):
        cur.learn(exp(chans(err=1.0 if i < 10 else 0.0), "idle"))
    assert cur._last_b > 0.0 or max(cur._hist) > 0.0
    for _ in range(3000):
        cur.learn(exp(chans(err=0.2), "idle"))
    assert cur._last_b < 1e-3


def test_no_world_channel_means_no_bonus():
    cur = CuriousQPolicy({"beta": 1.0}, RNG())
    ql = QLearningPolicy({}, RNG())
    es = [exp(chans(), "idle", {"petting": 0.5}) for _ in range(5)]
    for e in es:
        cur.learn(e)
    for e in es[:-1]:
        ql.learn(e)
    assert cur.sum_b == 0.0 and np.array_equal(cur.Q, ql.Q)


def test_held_transition_survives_save_load(tmp_path):
    cur = CuriousQPolicy({"beta": 0.5}, RNG())
    es = [exp(chans(err=0.1 * (i % 7)), ACTIONS[i % 8], {"petting": 0.2}) for i in range(20)]
    for e in es[:10]:
        cur.learn(e)
    assert cur.held is not None
    K.assert_state_roundtrip(cur, tmp_path)
    cur2 = CuriousQPolicy({"beta": 0.5}, RNG())
    cur2.load_state_dict(cur.state_dict())
    for e in es[10:]:
        cur.learn(e)
        cur2.learn(e)
    assert np.array_equal(cur.Q, cur2.Q) and cur.held == cur2.held


def test_bad_mode_rejected_and_future_version_fails():
    with pytest.raises(ValueError):
        CuriousQPolicy({"bonus": "x"}, RNG())
    with pytest.raises(ValueError):
        CuriousQPolicy({}, RNG()).load_state_dict({"version": B.M10_STATE_VERSION + 1})


NAMES = ("curious-v1", "curious-lp-v1")


@pytest.mark.parametrize("name", NAMES)
def test_recipe_runs_clean(name):
    K.run_clean(K.recipe(name), 3.0)


@pytest.mark.slow
@pytest.mark.parametrize("name", NAMES)
def test_recipe_runs_clean_neglectful(name):
    K.run_clean(K.recipe(name), 5.0, profile="neglectful")


@pytest.mark.parametrize("name", NAMES)
def test_recipe_save_load_identical(name, tmp_path):
    K.assert_save_load_identical(K.recipe(name), tmp_path, 3600.0, 3600.0)


@pytest.mark.parametrize("name", NAMES)
def test_recipe_state_roundtrip_and_budget(name, tmp_path, monkeypatch):
    rt = K.run_clean(K.recipe(name), 0.5)
    for mod in ("policy.curious", "world.model"):
        K.assert_state_roundtrip(rt.scheduler.modules()[mod], tmp_path / mod)
        assert K.mean_ms(rt, mod) <= B.EXP_BUDGET_MS
    K.assert_no_global_rng(monkeypatch, K.recipe(name))
