from engrama.balance import HOUR
from engrama.kernel.lifecycle import Health, StageMachine
from engrama.vocab import STAGES


def test_egg_hatches_after_300s():
    sm = StageMachine()
    assert sm.update(299.0, 0.0) is None
    assert sm.stage == "egg"
    assert sm.update(2.0, 0.0) == "baby"
    assert sm.stage == "baby"
    assert sm.stage_age == 0.0


def test_hatch_now():
    sm = StageMachine()
    sm.hatch_now()
    assert sm.stage == "baby"


def test_poor_care_delays_then_forces():
    sm = StageMachine(stage="baby")
    for _ in range(36):
        sm.update(HOUR, 95.0)
    assert sm.stage == "baby"
    for _ in range(18):
        sm.update(HOUR, 95.0)
    assert sm.stage == "child"


def test_final_is_terminal():
    sm = StageMachine(stage="final")
    assert sm.update(10**9, 0.0) is None
    assert sm.stage == "final"


def test_stage_roundtrip():
    sm = StageMachine(stage="child", age=5.0, stage_age=2.0, care_quality=0.7)
    assert StageMachine.from_dict(sm.to_dict()) == sm
    assert STAGES == ("egg", "baby", "child", "adult", "perfect", "final")


def test_stage_index():
    assert StageMachine().stage_index == 0
    assert StageMachine(stage="adult").stage_index == STAGES.index("adult")


def test_health_stub_never_sick_and_roundtrips():
    h = Health()
    h.update(10**6, 100.0)
    assert h.sick is False
    assert Health.from_dict(h.to_dict()) == h
