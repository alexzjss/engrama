"""policy.thompson: Q-learning bayesiano simplificado (M10, Tarefa 3)."""
from pathlib import Path

import numpy as np
import pytest

from engrama import balance as B
from engrama.mind.contracts import Blackboard, Experience
from engrama.modules.policy.qlearning import N_STATES, QLearningPolicy
from engrama.modules.policy.thompson import ThompsonPolicy
from engrama.vocab import ACTIONS
from tests.modules import contract_kit as K

DAY = 86400.0


def _exp(channels, action, reward=0.0, dt=60.0, next_channels=None):
    nxt = channels if next_channels is None else next_channels
    return Experience(t=0.0, dt=dt, events=(), channels=channels, action=action, action_prob=1.0,
                      rewards={"need_relief": reward}, next_channels=nxt)


def _ctx(rng):
    return {
        "world.hour": rng.uniform(-1, 1, size=2),
        "world.user_active": np.array([float(rng.integers(0, 2))]),
        "affect.pad": rng.uniform(-1, 1, size=3),
    }


def test_mu_matches_qlearning():
    rng = np.random.default_rng(3)
    th = ThompsonPolicy({}, np.random.default_rng(0))
    ql = QLearningPolicy({}, np.random.default_rng(0))
    for _ in range(300):
        ch, nxt = _ctx(rng), _ctx(rng)
        a = ACTIONS[int(rng.integers(len(ACTIONS)))]
        r = float(rng.uniform(-1, 1))
        e = Experience(t=0.0, dt=60.0, events=(), channels=ch, action=a, action_prob=1.0,
                       rewards={"need_relief": r}, next_channels=nxt)
        th.learn(e)
        ql.learn(e)
    assert np.array_equal(th.mu, ql.Q)


def test_sd_shrinks_with_visits_and_regrows_with_forgetting():
    m = ThompsonPolicy({}, np.random.default_rng(0))
    s, a = 0, ACTIONS.index("wander")
    sd0 = m.sd()[s, a]
    for _ in range(50):   # dt = 0: sem esquecimento, só contagem
        m.learn(_exp({}, "wander", dt=0.0))
    sd_visited = m.sd()[s, a]
    assert sd_visited < sd0
    assert m.n[s, a] == pytest.approx(50.0)
    # uma semana depois (exp.dt = 7 dias, meia-vida de 7 dias) as visitas caem à metade
    m.learn(_exp({}, "idle", dt=7 * DAY))
    assert m.n[s, a] == pytest.approx(25.0)
    assert m.sd()[s, a] > sd_visited


def test_two_armed_bandit_prefers_best():
    arm_a, arm_b = "idle", "wander"
    p = {arm_a: 0.7, arm_b: 0.3}
    m = ThompsonPolicy({"gamma": 0.0}, np.random.default_rng(1))
    bb = Blackboard()
    bb.available_actions = (arm_a, arm_b)
    env = np.random.default_rng(0)
    choices = []
    for _ in range(500):
        props = m.propose(bb)
        best = max(props, key=lambda q: q.score).action
        choices.append(best)
        r = 1.0 if env.random() < p[best] else 0.0
        m.learn(_exp({}, best, reward=r))
    assert choices[-200:].count(arm_a) / 200 > 0.9


def test_zero_sd_equals_mean():
    m = ThompsonPolicy({}, np.random.default_rng(0))
    m.mu = np.random.default_rng(4).normal(size=(N_STATES, len(ACTIONS)))
    m.n[:] = 1e12   # sd ~ 1e-7: a amostra é a média
    bb = Blackboard()
    props = m.propose(bb)
    assert props
    for p in props:
        assert abs(p.score - m.mu[0, ACTIONS.index(p.action)]) < 1e-6


def test_rng_draws_fixed_per_propose():
    def state_after(available):
        rng = np.random.default_rng(5)
        m = ThompsonPolicy({}, rng)
        bb = Blackboard()
        bb.available_actions = available
        m.propose(bb)
        return rng.bit_generator.state

    few = state_after(("idle", "wander"))
    many = state_after(ACTIONS)
    ref = np.random.default_rng(5)
    ref.standard_normal(len(ACTIONS))
    assert few == many == ref.bit_generator.state


def test_deterministic_given_rng_state():
    def run():
        rng_ctx = np.random.default_rng(9)
        m = ThompsonPolicy({}, np.random.default_rng(2))
        bb = Blackboard()
        out = []
        for _ in range(60):
            bb.available_actions = tuple(ACTIONS[:int(rng_ctx.integers(2, len(ACTIONS) + 1))])
            props = m.propose(bb)
            out.append([(p.action, p.score) for p in props])
            m.learn(_exp({}, props[0].action, reward=float(rng_ctx.uniform(-1, 1))))
        return out

    assert run() == run()


def test_state_roundtrip_versioned(tmp_path):
    m = ThompsonPolicy({}, np.random.default_rng(0))
    for _ in range(20):
        m.learn(_exp({}, "explore", reward=0.5))
    m.propose(Blackboard())
    K.assert_state_roundtrip(m, tmp_path)


def test_lab_metrics_and_viz():
    m = ThompsonPolicy({}, np.random.default_rng(0))
    m.propose(Blackboard())
    met = m.lab_metrics()
    assert set(met) == {"sd_mean", "explore_rate"}
    assert 0.0 <= met["explore_rate"] <= 1.0
    assert len(m.viz()) == 2


def test_recipe_is_default_with_thompson():
    rec = K.recipe("thompson-v1")
    types = [s.type for s in rec.modules]
    assert "policy.thompson" in types and "policy.qlearning" not in types
    base = [s.type for s in K.recipe("default-v1").modules if s.type != "policy.qlearning"]
    assert [t for t in types if t != "policy.thompson"] == base
    spec = [s for s in rec.modules if s.type == "policy.thompson"][0]
    assert spec.weight == pytest.approx(0.6)
    assert rec.name == "thompson-v1"


def test_thompson_runs_attentive_three_days():
    rt = K.run_clean(K.recipe("thompson-v1"), 3.0)
    assert rt.kernel.t > 0


@pytest.mark.slow
def test_thompson_runs_neglectful_five_days_with_rebirth():
    rt = K.run_clean(K.recipe("thompson-v1"), 5.0, profile="neglectful")
    assert rt.kernel.t > 0


def test_thompson_save_load_continue_identical(tmp_path):
    K.assert_save_load_identical(K.recipe("thompson-v1"), tmp_path, 0.5 * DAY, 0.25 * DAY)


def test_thompson_no_global_rng(monkeypatch):
    K.assert_no_global_rng(monkeypatch, K.recipe("thompson-v1"), seconds=3600.0)


@pytest.mark.perf
def test_thompson_mean_ms_within_budget():
    rt = K.run_clean(K.recipe("thompson-v1"), 0.5)
    assert K.mean_ms(rt, "policy.thompson") <= B.EXP_BUDGET_MS
