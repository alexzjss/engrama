from engrama.kernel.genome import Genome


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
