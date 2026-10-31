from engrama.memory.store import MemoryStore, WorkingMemory

DAY = 86400.0


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def make(tmp_path):
    clock = Clock()
    return MemoryStore(tmp_path / "mem.db", now_fn=clock), clock


def test_add_and_recent(tmp_path):
    s, clock = make(tmp_path)
    ids = []
    for i in range(3):
        clock.t += 1
        ids.append(s.add_episode("feed", f"ep{i}"))
    assert ids == sorted(ids) and len(set(ids)) == 3
    assert s.recent(2) == ["ep2", "ep1"]
    s.close()


def test_fact_upsert_confidence(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("nome", "Ana", 0.8, "chat")
    s.upsert_fact("nome", "Bia", 0.5, "chat")
    assert s.facts() == [("nome", "Ana")]
    s.upsert_fact("nome", "Cris", 0.8, "chat")
    assert s.facts() == [("nome", "Cris")]
    s.upsert_fact("nome", "Dani", 0.9, "chat")
    assert s.facts() == [("nome", "Dani")]
    s.close()


def test_retrieve_prefers_important_and_matching(tmp_path):
    s, _ = make(tmp_path)
    s.add_episode("chat", "comeu maca", importance=0.2)
    s.add_episode("chat", "falou de dinossauros", importance=0.5, topic="dino")
    s.add_episode("chat", "dia importante sem relacao", importance=0.7)
    res = s.retrieve(["dinossauros"], k=3)
    assert set(res) == {"comeu maca", "falou de dinossauros", "dia importante sem relacao"}
    assert s.retrieve(["dino"], k=1) == ["falou de dinossauros"]
    assert s.retrieve(["x"], k=1) == ["dia importante sem relacao"]
    s.close()


def test_forget_compacts_trivial_keeps_important(tmp_path):
    s, clock = make(tmp_path)
    now = clock.t
    clock.t = now - 4 * DAY
    for i in range(30):
        s.add_episode("feed", f"fed {i}", importance=0.2)
    s.add_episode("event", "grande dia", importance=0.8)
    s.upsert_fact("k", "v", 0.5, "x")
    clock.t = now
    removed = s.forget()
    assert removed == 30
    texts = s.recent(10)
    assert len(texts) == 2
    assert "grande dia" in texts
    compact = [t for t in texts if t != "grande dia"][0]
    assert compact.startswith("feed ×30 (")
    assert s.facts() == [("k", "v")]
    assert s.forget() == 0
    s.close()


def test_topics_clamped(tmp_path):
    s, _ = make(tmp_path)
    s.bump_topic("dino", 0.7)
    s.bump_topic("dino", 0.7)
    s.bump_topic("chuva", -2)
    s.bump_topic("lua", 0.3)
    assert s.top_topics(3) == [("dino", 1.0), ("lua", 0.3), ("chuva", -1.0)]
    assert s.top_topics(1) == [("dino", 1.0)]
    s.close()


def test_working_memory_maxlen():
    w = WorkingMemory(maxlen=3)
    for i in range(5):
        w.add("user", str(i))
    assert w.messages() == [{"role": "user", "content": s} for s in ("2", "3", "4")]
    w.clear()
    assert w.messages() == []
