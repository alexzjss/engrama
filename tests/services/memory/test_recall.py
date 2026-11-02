import re

from engrama.services.memory.recall import RecallContext, recall
from engrama.services.memory.store import MemoryStore


class FakeMem:
    def __init__(self, facts=(), topics=(), past=(), ops=None, episodes=()):
        self._f, self._t, self._p, self._o, self._e = list(facts), list(topics), list(past), ops or {}, list(episodes)

    def fact_rows(self):
        return [dict(key=k, value=v, confidence=0.5, source="chat", t=0.0) for k, v in self._f]

    def retrieve(self, words, k=5):
        return self._e[:k]

    def current_topics(self, n=3):
        return self._t[:n]

    def past_topics(self, n=3):
        return self._p[:n]

    def opinion(self, topic):
        return self._o.get(topic)


OP = {"jogo": dict(topic="jogo", lean=-0.8, experience=-0.8, stance=-0.8, confidence=0.9,
                   phrase=None, phrase_lang=None)}


def test_recall_finds_fact_by_word():
    m = FakeMem(facts=[("cor", "azul"), ("jogo_favorito", "hollow knight")])
    ctx = recall(m, "qual seu jogo preferido?", "adult", "pt")
    assert ctx.facts == ["jogo_favorito: hollow knight"]


def test_recall_fallback_most_confident_facts():
    m = FakeMem(facts=[("aaa", "um"), ("bbb", "dois"), ("ccc", "tres")])
    assert len(recall(m, "oi", "child", "pt").facts) == 2


def test_recall_stage_gating():
    m = FakeMem(facts=[("cor", "azul")], topics=["musica"], past=["futebol"], ops=OP, episodes=["viu algo"])
    assert recall(m, "jogo", "egg", "pt") == RecallContext([], [], [], [], None)
    b = recall(m, "jogo", "baby", "pt")
    assert b.opinion is None and b.past == []
    a = recall(m, "jogo", "adult", "pt")
    assert a.opinion is not None and "jogo" in a.opinion and a.past == []
    p = recall(m, "jogo", "perfect", "pt")
    assert p.past == ["futebol"] and p.current == ["musica"]


def test_recall_opinion_phrase_same_lang():
    ops = {"jogo": dict(OP["jogo"], phrase="jogo me irrita", phrase_lang="pt")}
    m = FakeMem(ops=ops)
    assert recall(m, "jogo", "adult", "pt").opinion == "jogo me irrita"
    assert recall(m, "jogo", "adult", "en").opinion == "hates jogo"


def test_recall_strips_digits():
    m = FakeMem(facts=[("idade", "23 anos")])
    ctx = recall(m, "qual minha idade", "adult", "pt")
    assert ctx.facts and not re.search(r"\d", " ".join(ctx.facts))


def test_recall_never_raises():
    class Boom:
        def __getattr__(self, n):
            def f(*a, **k):
                raise RuntimeError("x")
            return f
    assert recall(Boom(), "oi", "adult", "pt") == RecallContext([], [], [], [], None)


def test_recall_real_store(tmp_path):
    s = MemoryStore(tmp_path / "m.db")
    s.upsert_fact("jogo_favorito", "hollow knight", 0.8, "chat")
    s.bump_topic("jogo", 0.5)
    ctx = recall(s, "meu jogo", "adult", "pt")
    assert ctx.facts == ["jogo_favorito: hollow knight"]
    assert ctx.current == ["jogo"]
    s.close()
