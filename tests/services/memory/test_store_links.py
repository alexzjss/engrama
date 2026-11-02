from engrama.services.memory.store import MemoryStore


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def make(tmp_path):
    return MemoryStore(tmp_path / "memory.sqlite", now_fn=Clock())


def test_set_phrase_does_not_create_opinion(tmp_path):
    s = make(tmp_path)
    s.set_opinion_phrase("jogo", "adora jogos", "pt")
    assert s.opinion("jogo") is None and s.opinion_rows() == []
    s.update_opinion("jogo", lambda t: 0.6, 0.0)
    s.set_opinion_phrase("jogo", "adora jogos", "pt")
    op = s.opinion("jogo")
    assert op["phrase"] == "adora jogos" and op["phrase_lang"] == "pt" and op["lean"] == 0.6
    s.close()


def test_link_episode_adds_links_once(tmp_path):
    s = make(tmp_path)
    eid = s.add_episode("chat", "conversa: oi")
    s.link_episode(eid, topics=["Jogos"], facts=["nome"])
    s.link_episode(eid, topics=["jogo"])
    s.link_episode(9999, topics=["x"])
    rows = s._db.execute("SELECT kind, ref FROM episode_links WHERE episode_id=? ORDER BY kind", (eid,)).fetchall()
    assert rows == [("fact", "nome"), ("topic", "jogo")]
    s.close()
