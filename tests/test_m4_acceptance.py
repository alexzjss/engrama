"""M4 acceptance (spec section 8): the creature remembers, tells current from past subjects, holds opinions of
its own, reflects without loading the LLM, takes rare initiative, forgets for good, stays bounded and migrates."""
import json
import random
import re
import sqlite3
from pathlib import Path

import pytest

from engrama.app.host import Host, _memory_provider
from engrama.clock import SimClock
from engrama.config import Config
from engrama.services.language.initiative import InitiativePolicy
from engrama.services.language.persona import PersonaState
from engrama.services.language.service import FACTS_PROMPT, LanguageService
from engrama.services.memory import MAX_EPISODES, MAX_FACTS, MAX_TOPICS
from engrama.services.memory.opinions import innate_lean
from engrama.services.memory.store import MemoryStore, WorkingMemory

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "recipes" / "minimal-v1.toml"
DAY = 86400.0
FACTS_HEADS = (FACTS_PROMPT["pt"][:30], FACTS_PROMPT["en"][:30])
REFLECT_HEADS = ("Você é a memória", "You are Engrama's memory")


class FakeTime:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


class ScriptedClient:
    """Chat answers 'oi'; fact extraction and reflection prompts get fixed JSON. Counts warm/chat calls."""

    def __init__(self, facts=None, reflection=None):
        self.facts = facts or {"facts": [], "topics": [], "valence": 0.0}
        self.reflection = reflection or {"summary": "falamos de jogos", "topic": "jogo"}
        self.warms = self.unloads = 0
        self.chats: list[list[dict]] = []

    def warm(self, model):
        self.warms += 1

    def unload(self, model):
        self.unloads += 1

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        head = messages[0]["content"]
        if head.startswith(FACTS_HEADS):
            return json.dumps(self.facts)
        if head.startswith(REFLECT_HEADS):
            return json.dumps(self.reflection)
        # varied lines: the M13 repeat guard rejects the same reply as one of the last three
        return ["oi, e ai", "tudo bem?", "fala ai", "opa, beleza?", "que legal"][len(self.chats) % 5]

    def tags(self):
        return {"qwen3:1.7b"}

    def pull(self, name, on_progress):
        on_progress(100, "ok")


class FakeServer:
    def available(self):
        return True

    def running(self):
        return True

    def start(self):
        return True


def make_lang(tmp, ft, client, stage="child", idle=lambda: True, name="mem.sqlite"):
    mem = MemoryStore(tmp / name, now_fn=ft)
    work = WorkingMemory()
    lang = LanguageService(client, FakeServer(), Config(data_dir=tmp), mem, work,
                           get_state=lambda: PersonaState(stage=stage), food_name=lambda i, l: i,
                           idle=idle, now_fn=ft, sync=True)
    return lang, mem, work


def drain(lang):
    out = []
    while not lang.replies.empty():
        out.append(lang.replies.get())
    return out


def system_for(client, user_text):
    return next(m[0]["content"] for m in client.chats if m[-1]["content"] == user_text)


# 1 -------------------------------------------------------------------------------------------------------
def test_remembers_fact_days_later(tmp_path):
    ft = FakeTime()
    client = ScriptedClient(facts={"facts": [["jogo_favorito", "hollow knight", 0.9]],
                                   "topics": [["jogo", 0.5]], "valence": 0.5})
    lang, mem, _ = make_lang(tmp_path, ft, client)
    lang.request("meu jogo favorito é hollow knight")
    lang.pump()
    assert ("jogo_favorito", "hollow knight") in mem.facts()
    ft.tick(4 * DAY)
    lang.request("quer falar de jogo?")
    lang.pump()
    prompt = system_for(client, "quer falar de jogo?")
    assert "hollow knight" in prompt and not re.search(r"\d", prompt)
    mem.close()


# 2 -------------------------------------------------------------------------------------------------------
def test_current_vs_past_topics(tmp_path):
    ft = FakeTime()
    mem = MemoryStore(tmp_path / "m.sqlite", now_fn=ft)
    for _ in range(3):                        # week 1: a hot subject
        mem.bump_topic("xadrez", 0.6)
        ft.tick(DAY)
    ft.tick(14 * DAY)                         # then silence until week 3
    for _ in range(2):
        mem.bump_topic("futebol", 0.5)
        ft.tick(3600)
    assert "xadrez" in mem.past_topics(5) and "xadrez" not in mem.current_topics(5)
    assert "futebol" in mem.current_topics(5) and "futebol" not in mem.past_topics(5)
    mem.close()


# 3 -------------------------------------------------------------------------------------------------------
def test_opinions_can_oppose_user_and_each_other(tmp_path):
    topic = "jogo"
    pos = next(s for s in range(500) if innate_lean(s, topic) > 0.5)
    neg = next(s for s in range(500) if innate_lean(s, topic) < -0.5)

    def history(seed, name):
        mem = MemoryStore(tmp_path / name, now_fn=FakeTime())
        for _ in range(8):                    # same user history: loves the subject
            mem.bump_topic(topic, 0.4)
            mem.update_opinion(topic, lambda t, s=seed: innate_lean(s, t), 0.6)
        op, aff = mem.opinion(topic), dict(mem.top_topics(5))[topic]
        mem.close()
        return op["stance"], aff

    s_pos, aff_pos = history(pos, "a.sqlite")
    s_neg, aff_neg = history(neg, "b.sqlite")
    assert s_pos > 0 > s_neg                  # same history, opposite positions
    assert aff_neg > 0.8 and s_neg < 0        # the user adores it, the creature does not


# 4 -------------------------------------------------------------------------------------------------------
def test_reflection_never_loads_llm(tmp_path):
    ft = FakeTime()
    client = ScriptedClient()
    lang, mem, work = make_lang(tmp_path, ft, client, name="off.sqlite")
    work.add("user", "oi"), work.add("assistant", "oi")
    lang._reflect_due, lang._last_llm_reply = True, ft.t       # a finished conversation, LLM offline
    for _ in range(60):                                         # 1 h of ticks
        ft.tick(60)
        lang.tick(ft.t)
        lang.pump()
    assert client.warms == 0 and client.chats == []
    assert mem.recent_reflections(3) == []
    mem.close()
    # ready and idle: a finished conversation yields a reflection episode
    client2 = ScriptedClient()
    lang2, mem2, _ = make_lang(tmp_path, ft, client2, name="on.sqlite")
    lang2.request("oi, gosto de jogo")
    lang2.pump()
    assert lang2.status == "ready"
    ft.tick(130)
    lang2.tick(ft.t)
    lang2.pump()
    assert mem2.recent_reflections(1) == ["falamos de jogos"]
    mem2.close()


# 5 -------------------------------------------------------------------------------------------------------
def _initiative_run(tmp, stage, fullscreen=False, hours=10, seed=11):
    ft = FakeTime()
    host = Host(Config(data_dir=tmp), tmp, MINIMAL, seed=7, clock=SimClock(1.0, now_fn=ft),
                ram_free_mb_fn=lambda: 8000.0)
    host.runtime.kernel.lifecycle.stage = stage          # forced, as the host tests do
    client = ScriptedClient()
    lang, mem, _ = make_lang(tmp, ft, client, stage=stage, idle=lambda: not host.snapshot().resting)
    mem.bump_topic("jogo", 0.6)
    lang.warm()
    policy = InitiativePolicy(mem, ft, rng=random.Random(seed))
    if fullscreen:
        host.post("fullscreen_on")
    fired = 0
    for _ in range(hours * 60):
        ft.tick(60)
        host.post("user_active")
        host.pump(1)
        snap = host.snapshot()
        assert snap.stage == stage
        res = policy.update(ft.t, stage=snap.stage, user_active=True, llm_ready=lang.status == "ready",
                            resting=snap.resting, fullscreen=snap.rest_reason == "fullscreen",
                            action=snap.action)
        if res:
            lang.spontaneous(res[0], res[1])
        lang.pump()
        fired += len(drain(lang))
    host.stop()
    mem.close()
    return fired


def test_initiative_real_host(tmp_path):
    n = _initiative_run(tmp_path / "adult", "adult")
    assert 1 <= n <= 10
    assert _initiative_run(tmp_path / "baby", "baby") == 0
    assert _initiative_run(tmp_path / "full", "adult", fullscreen=True) == 0


# 6 -------------------------------------------------------------------------------------------------------
def test_delete_is_final(tmp_path):
    ft = FakeTime()
    client = ScriptedClient(facts={"facts": [["jogo_favorito", "hollow knight", 0.9]],
                                   "topics": [["jogo", 0.5]], "valence": 0.5})
    lang, mem, work = make_lang(tmp_path, ft, client)
    prov = _memory_provider(mem, work)
    lang.request("meu jogo favorito é hollow knight")
    lang.pump()
    assert ("jogo_favorito", "hollow knight") in prov.facts()
    assert any("hollow knight" in m["content"] for m in work.messages())
    ft.tick(10)
    prov.delete_fact("jogo_favorito")
    assert prov.facts() == []
    assert not any("hollow knight" in e for e in mem.recent(50))
    assert not any("hollow knight" in m["content"] for m in work.messages())
    # a late extraction of the old message (before the deletion) must not bring it back
    lang._extract("meu jogo favorito é hollow knight", "pt", t_msg=ft.t - 5)
    assert prov.facts() == []
    # nor does it show up in the next prompt
    ft.tick(10)
    client.facts = {"facts": [], "topics": [], "valence": 0.0}
    lang.request("e agora, jogo?")
    lang.pump()
    assert "hollow knight" not in system_for(client, "e agora, jogo?")
    # only a new mention by the user brings it back
    ft.tick(10)
    client.facts = {"facts": [["jogo_favorito", "hollow knight", 0.9]], "topics": [], "valence": 0.0}
    lang.request("já falei, hollow knight é o meu favorito")
    lang.pump()
    assert ("jogo_favorito", "hollow knight") in prov.facts()
    # topics and "forget everything"
    assert "jogo" in [n for n, _ in prov.topics()]
    prov.delete_topic("jogo")
    assert "jogo" not in [n for n, _ in prov.topics()]
    prov.forget_all()
    s = prov.summary()
    assert s["facts"] == 0 and s["topics"] == 0 and s["episodes"] == 0 and work.messages() == []
    mem.close()


# 7 -------------------------------------------------------------------------------------------------------
SYNTH = ["hoje joguei um jogo novo de aventura", "i watched a movie about space with my brother",
         "estou cansado do trabalho hoje", "my cat sleeps all day long", "quero aprender violao este ano",
         "the weather was rainy and cold today", "comi pizza com amigos ontem", "i am learning to cook pasta",
         "li um livro sobre historia antiga", "we went hiking near the river"]


def test_memory_bounded_30_days(tmp_path):
    ft = FakeTime()
    path = tmp_path / "memory.sqlite"
    mem = MemoryStore(path, now_fn=ft)
    for day in range(30):
        for i in range(20):
            text = f"{SYNTH[(day + i) % len(SYNTH)]} {day}-{i}"
            mem.add_episode("chat", f"conversa: {text}", 0.0, importance=0.2)
            mem.bump_topic(f"assunto{day}x{i}", 0.2)
            if i % 2 == 0:
                mem.upsert_fact(f"fato{day}x{i}", text, 0.6, "chat")
            ft.tick(600)
        ft.t += DAY - 20 * 600
        mem.forget()
    assert len(mem.recent(10 ** 6)) < 30 * 20          # old low-importance episodes were compacted
    assert len(mem.recent(10 ** 6)) <= MAX_EPISODES
    assert len(mem.fact_rows()) <= MAX_FACTS
    assert len(mem.topic_rows()) <= MAX_TOPICS
    mem.close()
    assert path.stat().st_size <= 5 * 1024 * 1024


# 8 -------------------------------------------------------------------------------------------------------
def test_m3_db_migrates(tmp_path):
    path = tmp_path / "memory.sqlite"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE episodes(id INTEGER PRIMARY KEY, t REAL, kind TEXT, summary TEXT,
                              valence REAL, importance REAL, topic TEXT NULL);
        CREATE TABLE facts(id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT, confidence REAL,
                           source TEXT, t REAL);
        CREATE TABLE topics(name TEXT PRIMARY KEY, affinity REAL, t REAL);
        CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
        INSERT INTO meta(k, v) VALUES('schema_version', '1');
        INSERT INTO episodes(t,kind,summary,valence,importance,topic) VALUES(1,'chat','conversa a',0,0.3,NULL);
        INSERT INTO episodes(t,kind,summary,valence,importance,topic) VALUES(2,'chat','conversa b',0,0.3,NULL);
        INSERT INTO facts(key,value,confidence,source,t) VALUES('nome','Ana',0.8,'chat',1);
        INSERT INTO topics(name,affinity,t) VALUES('musica',0.4,5);
    """)
    con.commit()
    con.close()
    mem = MemoryStore(path)
    assert len(mem.recent(10)) == 2
    assert mem.facts() == [("nome", "Ana")]
    assert mem.top_topics(5) == [("musica", 0.4)]
    assert mem.opinion_rows() == []
    mem.close()
