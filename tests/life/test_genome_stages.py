from engrama.core.balance import HOUR
from engrama.life.genome import Genome
from engrama.life.stages import STAGES, StageMachine


def test_genome_deterministic():
    assert Genome.from_seed(42) == Genome.from_seed(42)
    assert Genome.from_seed(42) != Genome.from_seed(43)


def test_genome_ranges():
    for seed in range(200):
        g = Genome.from_seed(seed)
        assert 0 <= g.body <= 5
        assert 0 <= g.eyes <= 3
        assert 0 <= g.ears <= 4
        assert 0 <= g.tail <= 3
        assert 0 <= g.pattern <= 3
        assert 180 <= g.voice_pitch <= 520
        assert g.branch == "base"
        assert len(g.palette) == 4
        for color in g.palette:
            assert len(color) == 3 and all(0 <= c <= 255 for c in color)


def test_genome_roundtrip():
    g = Genome.from_seed(7)
    assert Genome.from_dict(g.to_dict()) == g


def test_inherit_keeps_main_color():
    parent = Genome.from_seed(1)
    child = Genome.inherit(parent, 99)
    assert child.palette[1] == parent.palette[1]
    assert child.seed == 99
    same = sum(getattr(child, f) == getattr(parent, f) for f in ("body", "ears", "tail"))
    assert same >= 1
    assert Genome.inherit(parent, 99) == child


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
