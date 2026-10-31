import pytest
from engrama.mind.contracts import Blackboard, reward_combine
from engrama.vocab import ACTIONS, EVENT_KINDS, FOOD_IDS


def test_blackboard_write_clips_and_copies():
    bb = Blackboard()
    bb.write("body.needs", [2.0, -1, 0.5, 0, 0, 0])
    out = bb.read("body.needs")
    assert out.tolist() == [1, 0, 0.5, 0, 0, 0]
    out[0] = 0.123
    assert bb.read("body.needs")[0] == 1.0


def test_blackboard_rejects_unknown_and_bad_dim():
    bb = Blackboard()
    with pytest.raises(KeyError):
        bb.write("nope", [0.0])
    with pytest.raises(ValueError):
        bb.write("body.needs", [0.0, 0.0, 0.0])


def test_shadow_namespace_allowed():
    bb = Blackboard()
    bb.write("shadow/x/affect.pad", [0, 0, 0])
    assert bb.has("shadow/x/affect.pad")
    with pytest.raises(ValueError):
        bb.write("shadow/x/affect.pad", [0, 0])
    with pytest.raises(KeyError):
        bb.write("shadow/x/nope", [0])


def test_read_get_has_snapshot():
    bb = Blackboard()
    with pytest.raises(KeyError):
        bb.read("affect.pad")
    assert bb.get("affect.pad") is None and bb.get("affect.pad", 7) == 7
    bb.write("affect.pad", [5, 0, -5])
    snap = bb.snapshot()
    snap["affect.pad"][0] = 0
    assert bb.read("affect.pad").tolist() == [1, 0, -1]


def test_reward_combine_default_weights():
    assert reward_combine({"need_relief": 1, "ignored": 1}) == pytest.approx(0.7)


def test_vocab_sizes():
    assert len(ACTIONS) == 8 and len(EVENT_KINDS) == 10 and len(FOOD_IDS) == 10
