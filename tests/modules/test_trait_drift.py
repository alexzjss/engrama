import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Blackboard, Experience
from engrama.modules.traits.drift import TraitDrift
from engrama.vocab import INITIAL_TRAITS, TRAIT_KEYS


def exp(t, rewards, action="idle"):
    return Experience(t, 1.0, (), {}, action, 1.0, rewards, {})


def mk():
    return TraitDrift({}, np.random.default_rng(0))


def test_initial_traits_written():
    bb = Blackboard()
    mk().step(bb, 1.0)
    assert np.allclose(bb.read("traits"), [INITIAL_TRAITS[k] / 100 for k in TRAIT_KEYS])


def test_trait_drift_daily_cap():
    td = mk()
    for i in range(100):
        td.learn(exp(i, {"user_response": 1.0}))
    assert td.traits["sociabilidade"] == INITIAL_TRAITS["sociabilidade"] + 2.0
    td.learn(exp(86400 + 1, {"user_response": 1.0}))
    assert td.traits["sociabilidade"] == INITIAL_TRAITS["sociabilidade"] + 2.0 + 0.5 * B.TRAIT_NUDGE_SCALE


def test_trait_drift_ignored_raises_independence():
    td = mk()
    td.learn(exp(0, {"ignored": 1.0}))
    assert np.isclose(td.traits["independencia"], INITIAL_TRAITS["independencia"] + 0.3 * B.TRAIT_NUDGE_SCALE)
    assert np.isclose(td.traits["sociabilidade"], INITIAL_TRAITS["sociabilidade"] - 0.2 * B.TRAIT_NUDGE_SCALE)


def test_trait_drift_conditional_nudges():
    td = mk()
    td.learn(exp(0, {"novelty": 1.0}, "idle"))
    td.learn(exp(0, {"need_relief": 1.0}, "sleep"))
    assert td.traits["curiosidade"] == INITIAL_TRAITS["curiosidade"]
    assert td.traits["criatividade"] == INITIAL_TRAITS["criatividade"]
    td.learn(exp(0, {"novelty": 1.0}, "explore"))
    td.learn(exp(0, {"need_relief": 1.0}, "play_alone"))
    td.learn(exp(0, {"petting": 1.0}))
    assert np.isclose(td.traits["curiosidade"], 50 + 0.3 * B.TRAIT_NUDGE_SCALE)
    assert np.isclose(td.traits["criatividade"], 50 + 0.1 * B.TRAIT_NUDGE_SCALE)
    assert np.isclose(td.traits["paciencia"], 70 + 0.05 * B.TRAIT_NUDGE_SCALE)


def test_state_roundtrips():
    td = mk()
    for i in range(10):
        td.learn(exp(i, {"user_response": 1.0}))
    td2 = mk()
    td2.load_state_dict(td.state_dict())
    assert td2.traits == td.traits and td2.used == td.used and td2.day == td.day
