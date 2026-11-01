import math
import numpy as np
from engrama.mind.contracts import Blackboard, Experience
from engrama.modules.policy.qlearning import QLearningPolicy, state_index
from engrama.vocab import ACTIONS


def chans(hour, active, pad):
    a = 2 * math.pi * hour / 24
    return {"world.hour": np.array([math.sin(a), math.cos(a)]),
            "world.user_active": np.array([float(active)]), "affect.pad": np.array(pad, dtype=float)}


X = chans(3, 1, (0.5, 0.5, 0))
Y = chans(15, 0, (-0.5, -0.5, 0))


def exp(ch, action, rewards, nxt=None, dt=1.0):
    return Experience(0.0, dt, (), ch, action, 1.0, rewards, nxt if nxt is not None else ch)


def propose(q, ch):
    bb = Blackboard()
    for k, v in ch.items():
        bb.write(k, v)
    return {p.action: p for p in q.propose(bb)}


def test_state_index_bijection():
    seen = set()
    for h in (3, 9, 15, 21):
        for act in (0, 1):
            for p in (1, -1):
                for ar in (1, -1):
                    seen.add(state_index(chans(h, act, (p, ar, 0))))
    assert seen == set(range(32))


def test_q_learns_rewarded_action_in_context():
    q = QLearningPolicy({}, np.random.default_rng(0))
    for i in range(200):
        a = "ask_attention" if i % 2 == 0 else ACTIONS[i % 3 + 1]
        q.learn(exp(X, a, {"user_response": 1.0} if a == "ask_attention" else {}))
    props = propose(q, X)
    assert max(props, key=lambda a: props[a].score) == "ask_attention"
    assert all(p.score == 0.0 for p in propose(q, Y).values())
    assert props["idle"].reason == "aprendi: 0/1"


def test_q_dt_independent_reward_scale():
    def run(dt):
        q = QLearningPolicy({}, np.random.default_rng(0))
        q.learn(exp(X, "idle", {"user_response": 1.0}, dt=dt))
        return q.Q.copy()
    assert np.array_equal(run(1.0), run(60.0))


def test_q_only_available_actions():
    q = QLearningPolicy({}, np.random.default_rng(0))
    bb = Blackboard()
    bb.available_actions = ("idle", "sleep")
    assert {p.action for p in q.propose(bb)} == {"idle", "sleep"}


def test_state_roundtrips():
    q = QLearningPolicy({}, np.random.default_rng(0))
    q.learn(exp(X, "idle", {"user_response": 1.0}))
    q2 = QLearningPolicy({}, np.random.default_rng(1))
    q2.load_state_dict(q.state_dict())
    assert np.array_equal(q.Q, q2.Q) and np.array_equal(q.visits, q2.visits)
