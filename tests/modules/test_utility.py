import numpy as np
from engrama.mind.contracts import Blackboard
from engrama.modules.policy.utility import UtilityPolicy
from engrama.vocab import ACTIONS, NEED_KEYS, TRAIT_KEYS


def mk(drives=None, traits=None, actions=ACTIONS):
    bb = Blackboard(); bb.available_actions = tuple(actions)
    bb.write("drives", drives if drives is not None else np.zeros(6))
    if traits is not None:
        bb.write("traits", traits)
    return UtilityPolicy({}, np.random.default_rng(0)).propose(bb)


def score(props, a):
    return next(p.score for p in props if p.action == a)


def test_utility_sleepy_prefers_sleep():
    d = np.zeros(6); d[NEED_KEYS.index("sono")] = 1.0
    props = mk(d)
    others = [p.score for p in props if p.action not in ("sleep", "hide")]
    assert score(props, "sleep") > max(others)


def test_utility_only_available_actions():
    props = mk(actions=("idle", "sleep"))
    assert {p.action for p in props} == {"idle", "sleep"}


def test_utility_reasons_nonempty():
    props = mk(np.full(6, 0.5))
    assert len(props) == len(ACTIONS) and all(p.reason for p in props)


def test_traits_change_utility():
    d = np.zeros(6); d[NEED_KEYS.index("carinho")] = 1.0
    def tr(s): return [s if k == "sociabilidade" else 0.5 for k in TRAIT_KEYS]
    assert score(mk(d, tr(0.9)), "ask_attention") > score(mk(d, tr(0.1)), "ask_attention")
