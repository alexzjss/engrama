import numpy as np
from engrama.mind.arbiter import SoftmaxArbiter
from engrama.mind.contracts import Blackboard, Proposal


def props():
    return [Proposal("idle", 1.0, "r", "a"), Proposal("wander", 2.0, "r", "a"), Proposal("sleep", 0.5, "r", "b")]


def test_arbiter_deterministic_with_seed():
    arb = SoftmaxArbiter({"a": 1.0, "b": 1.0}); bb = Blackboard()
    r1 = [arb.choose(props(), ("idle", "wander", "sleep"), bb, np.random.default_rng(3)) for _ in range(1)]
    r2 = [arb.choose(props(), ("idle", "wander", "sleep"), bb, np.random.default_rng(3)) for _ in range(1)]
    assert r1 == r2


def test_arbiter_respects_available_and_weights():
    arb = SoftmaxArbiter({"a": 1.0, "b": 100.0}, trait_temperature=False); bb = Blackboard()
    a, p, d = arb.choose(props(), ("idle", "wander", "sleep"), bb, np.random.default_rng(0))
    assert a == "sleep" and p > 0.99 and abs(sum(d.values()) - 1.0) < 1e-9
    a, p, d = arb.choose(props(), ("idle", "wander"), bb, np.random.default_rng(0))
    assert set(d) == {"idle", "wander"} and a in d


def test_arbiter_empty_returns_none():
    arb = SoftmaxArbiter({}); bb = Blackboard()
    assert arb.choose([], ("idle",), bb, np.random.default_rng(0)) == (None, 1.0, {})
    assert arb.choose(props(), ("hide",), bb, np.random.default_rng(0)) == (None, 1.0, {})
