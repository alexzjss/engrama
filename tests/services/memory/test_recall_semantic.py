"""Hybrid recall (M9 T3): a fake memory with a scripted `similar`, plus the FakeEmbedder for vectors."""
import json

import numpy as np

from engrama.services.memory import SEM_MIN_SIM
from engrama.services.memory.recall import RecallContext, recall
from tests.services.fake_embedder import FakeEmbedder
from tests.services.memory.golden_recall import CASES, FIXTURE, build_store, snapshot

FE = FakeEmbedder()
OP = {"cachorro": dict(topic="cachorro", lean=0.9, experience=0.9, stance=0.9, confidence=0.9,
                       phrase=None, phrase_lang=None)}


class SemMem:
    """Same surface as the T2 memory: similar(), retrieve(sims), retrieve_ancestral(sims)."""

    def __init__(self, facts=(), topics=(), ops=None, episodes=(), ancestral=(), sim=None, boom=False):
        self._f, self._t, self._o = list(facts), list(topics), ops or {}
        self._e, self._a = list(episodes), list(ancestral)   # (id, summary)
        self.sim = sim or {}                                  # kind -> [(ref, cos)]
        self.boom = boom
        self.seen = []

    def fact_rows(self):
        return [dict(key=k, value=v, confidence=0.5, source="chat", t=0.0) for k, v in self._f]

    def similar(self, qvec, kind, k, min_sim):
        if self.boom:
            raise RuntimeError("index broken")
        self.seen.append((kind, k, min_sim))
        return [(r, s) for r, s in self.sim.get(kind, []) if s >= min_sim][:k]

    def retrieve(self, words, k=5, sims=None):
        if sims is None:
            return [s for _, s in self._e if any(w in s for w in words)][:k]
        order = sorted(self._e, key=lambda e: -sims.get(e[0], 0.0))
        return [s for i, s in order if sims.get(i, 0.0) >= SEM_MIN_SIM][:k] or [
            s for _, s in self._e if any(w in s for w in words)][:k]

    def retrieve_ancestral(self, words, k=1, sims=None):
        if sims:
            return [s for i, s in sorted(self._a, key=lambda e: -sims.get(e[0], 0.0))
                    if sims.get(i, 0.0) >= SEM_MIN_SIM][:k]
        return [s for _, s in self._a if any(w in s for w in words)][:k]

    def current_topics(self, n=3):
        return self._t[:n]

    def past_topics(self, n=3):
        return []

    def opinion(self, topic):
        return self._o.get(topic)


def q(text):
    return FE.query(text)


def test_qvec_none_identical_to_m4(tmp_path):
    store = build_store(tmp_path / "memory.sqlite")
    try:
        assert snapshot(store) == json.loads(FIXTURE.read_text(encoding="utf-8"))
        for text, stage, lang in CASES:
            assert recall(store, text, stage, lang, qvec=None) == recall(store, text, stage, lang)
    finally:
        store.close()


def test_memory_without_similar_is_m4(tmp_path):
    store = build_store(tmp_path / "memory.sqlite")
    try:
        class NoSim:
            def __getattr__(self, name):
                if name == "similar":
                    raise AttributeError(name)
                return getattr(store, name)
        for text, stage, lang in CASES:
            assert recall(NoSim(), text, stage, lang, qvec=q(text)) == recall(store, text, stage, lang)
    finally:
        store.close()


def test_fact_found_by_meaning():
    m = SemMem(facts=[("cor", "azul"), ("animal_de_estimacao", "cachorro biscoito")],
               sim={"fact": [("animal_de_estimacao", 0.9)]})
    msg = "meu bichinho está doente"
    assert recall(m, msg, "adult", "pt").facts == ["cor: azul", "animal_de_estimacao: cachorro biscoito"]
    ctx = recall(m, msg, "adult", "pt", qvec=q(msg))
    assert ctx.facts == ["animal_de_estimacao: cachorro biscoito"]


def test_fact_word_hit_beats_weak_meaning():
    m = SemMem(facts=[("cor", "azul"), ("jogo_favorito", "hollow knight"), ("musica", "rock")],
               sim={"fact": [("musica", 0.62)]})
    ctx = recall(m, "qual seu jogo preferido?", "adult", "pt", qvec=q("jogo"))
    assert ctx.facts[0] == "jogo_favorito: hollow knight"
    assert ctx.facts[1] == "musica: rock"


def test_episode_by_meaning_two_max():
    eps = [(1, "falou do trabalho"), (2, "o bichinho dela ficou doente"), (3, "viu a chuva"),
           (4, "o cachorro dormiu")]
    m = SemMem(episodes=eps, sim={"episode": [("2", 0.9), ("4", 0.8), ("3", 0.55)]})
    ctx = recall(m, "meu dog", "adult", "pt", qvec=q("meu dog"))
    assert ctx.episodes == ["o bichinho dela ficou doente", "o cachorro dormiu"]
    assert ("episode", 20, SEM_MIN_SIM) in m.seen


def test_ancestral_by_meaning():
    m = SemMem(ancestral=[(7, "sonhei com um cachorro"), (8, "sonhei com chuva")],
               sim={"ancestral": [("7", 0.8)]})
    assert recall(m, "bichinho", "child", "pt", qvec=q("bichinho")).ancestral == ["sonhei com um cachorro"]
    assert ("ancestral", 3, SEM_MIN_SIM) in m.seen


def test_opinion_by_nearest_topic():
    m = SemMem(ops=OP, sim={"topic": [("pizza", 0.9), ("cachorro", 0.8)]})
    ctx = recall(m, "meu bichinho", "adult", "pt", qvec=q("meu bichinho"))
    assert ctx.opinion is not None and "cachorro" in ctx.opinion
    assert recall(m, "meu bichinho", "adult", "pt").opinion is None


def test_opinion_word_match_wins_over_meaning():
    ops = dict(OP, jogo=dict(OP["cachorro"], topic="jogo", stance=-0.8))
    m = SemMem(ops=ops, sim={"topic": [("cachorro", 0.9)]})
    ctx = recall(m, "falar de jogo", "adult", "pt", qvec=q("falar de jogo"))
    assert "jogo" in ctx.opinion


def test_unrelated_message_adds_nothing():
    m = SemMem(facts=[("cor", "azul"), ("jogo_favorito", "x")], topics=["musica"], ops=OP,
               episodes=[(1, "viu algo")], ancestral=[(2, "sonho")])
    for msg in ("a chuva de sabado", "oi", "jogo"):
        assert recall(m, msg, "adult", "pt", qvec=q(msg)) == recall(m, msg, "adult", "pt")


def test_semantic_failure_falls_back_to_m4():
    m = SemMem(facts=[("cor", "azul"), ("jogo_favorito", "x")], topics=["musica"], ops=OP,
               episodes=[(1, "viu o jogo")], boom=True)
    ctx = recall(m, "jogo", "adult", "pt", qvec=q("jogo"))
    assert ctx == recall(m, "jogo", "adult", "pt")
    assert ctx.facts == ["jogo_favorito: x"] and ctx.current == ["musica"]


def test_stage_gating_unchanged_with_qvec():
    m = SemMem(facts=[("cor", "azul")], topics=["musica"], ops=OP, episodes=[(1, "viu algo")],
               sim={"topic": [("cachorro", 0.9)], "fact": [("cor", 0.9)]})
    v = q("bichinho")
    assert recall(m, "bichinho", "egg", "pt", qvec=v) == RecallContext()
    assert recall(m, "bichinho", "baby", "pt", qvec=v).opinion is None
    assert recall(m, "bichinho", "child", "pt", qvec=v).opinion is None
    assert recall(m, "bichinho", "adult", "pt", qvec=v).opinion is not None


def test_no_digits_with_qvec():
    m = SemMem(facts=[("idade", "30 anos"), ("cor", "azul")], episodes=[(1, "viu 3 gatos")],
               ancestral=[(2, "sonho 12")], sim={"fact": [("idade", 0.9)], "episode": [("1", 0.9)],
                                               "ancestral": [("2", 0.9)]})
    ctx = recall(m, "bichinho", "adult", "pt", qvec=q("bichinho"))
    import re
    for s in ctx.facts + ctx.episodes + ctx.ancestral:
        assert not re.search(r"\d", s)
    assert ctx.facts[0] == "idade: anos" and ctx.episodes == ["viu gatos"]


def test_qvec_is_ndarray_unused_by_words_path():
    m = SemMem(facts=[("cor", "azul")])
    assert isinstance(q("x"), np.ndarray)
    assert recall(m, "oi", "adult", "pt", qvec=None).facts == ["cor: azul"]
