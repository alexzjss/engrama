import numpy as np
from engrama.mind.contracts import Blackboard, Observation
from engrama.modules.affect.pad import PadAffect, pad_label, baseline, default_traits


def make():
    return PadAffect({}, np.random.default_rng(0))


def test_pad_decays_to_baseline_dt_invariant():
    res = []
    for dt in (1.0, 60.0):
        m = make(); m.pad = np.array([0.8, -0.6, 0.5])
        bb = Blackboard()
        for _ in range(int(3600 / dt)):
            m.step(bb, dt)
        res.append(m.pad.copy())
    assert np.allclose(res[0], res[1], atol=1e-3)
    assert np.linalg.norm(res[0] - baseline(default_traits())) < np.linalg.norm([0.8, -0.6, 0.5])


def test_pad_pet_raises_pleasure():
    m = make(); bb = Blackboard(); p0 = m.pad[0]
    bb.events = (Observation(0.0, "pet"),)
    m.step(bb, 1.0)
    assert m.pad[0] > p0 + 0.1 and bb.read("affect.pad")[0] == m.pad[0]


def test_pad_high_drives_lower_pleasure():
    a, b = make(), make()
    bb = Blackboard(); bb.write("drives", np.ones(6))
    for _ in range(600):
        a.step(bb, 1.0); b.step(Blackboard(), 1.0)
    assert a.pad[0] < b.pad[0]


def test_pad_label_octants_and_neutral():
    assert pad_label([0.05, 0.05, 0.05]) == "neutral"
    exp = {"+++": "exuberant", "++-": "excited", "+-+": "relaxed", "+--": "content",
           "-++": "angry", "-+-": "anxious", "--+": "bored", "---": "sad"}
    for k, v in exp.items():
        assert pad_label([0.5 if c == "+" else -0.5 for c in k]) == v
