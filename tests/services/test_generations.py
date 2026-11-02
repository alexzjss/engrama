from engrama.services.generations import (
    GenerationRecord, append_generation, delete_generation_archive, load_generations)


def rec(n):
    return GenerationRecord(n=n, lineage=("brincalhao", "companheiro"), seed=42 + n, born_wall=1.0,
                            died_wall=2.0, days=100.5, cause="old_age", ancestral=("um sonho",))


def test_generations_roundtrip_and_corrupt(tmp_path):
    p = tmp_path / "data" / "generations.json"
    assert load_generations(p) == []
    append_generation(p, rec(1))
    append_generation(p, rec(2))
    assert load_generations(p) == [rec(1), rec(2)]
    assert not list(p.parent.glob("*.tmp"))
    p.write_text("{not json", encoding="utf-8")
    assert load_generations(p) == []
    append_generation(p, rec(3))
    assert load_generations(p) == [rec(3)]


def test_delete_archive_keeps_record(tmp_path):
    p = tmp_path / "generations.json"
    append_generation(p, rec(1))
    d = tmp_path / "generations" / "1"
    d.mkdir(parents=True)
    (d / "memory.sqlite").write_bytes(b"x")
    delete_generation_archive(tmp_path, 1)
    assert not d.exists()
    delete_generation_archive(tmp_path, 1)   # idempotent
    assert load_generations(p) == [rec(1)]
