import json

from engrama.config import Config
from engrama.services.language.client import LLMOffline
from engrama.services.language.persona import PersonaState
from engrama.services.language.service import LanguageService
from engrama.services.memory import CONVERSATION_GAP_S
from engrama.services.memory.store import MemoryStore, WorkingMemory


class Server:
    def available(self):
        return True

    def running(self):
        return True

    def start(self):
        return True


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Client:
    """Routes by system prompt: facts / reflection / opinion / chat."""

    def __init__(self, chat="oi amigo", facts="{}", reflect="{}", opinion="adora jogos de verdade", warm_exc=None):
        self.chat_reply, self.facts, self.reflect, self.opinion = chat, facts, reflect, opinion
        self.warm_exc = warm_exc
        self.calls = []

    def warm(self, model):
        if self.warm_exc:
            raise self.warm_exc

    def unload(self, model):
        pass

    def tags(self):
        return set()

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        sysm = messages[0]["content"]
        self.calls.append(messages)
        if sysm.startswith(("Extraia", "From the user's")):
            return self.facts
        if "memória do Engrama" in sysm or "Engrama's memory" in sysm:
            return self.reflect
        if sysm.startswith(("Escreva em uma linha", "Write in one short line")):
            return self.opinion
        return self.chat_reply


def make(tmp_path, client, stage="adult", idle=lambda: True, lean=None):
    clock = Clock()
    mem = MemoryStore(tmp_path / "m.sqlite", now_fn=clock)
    svc = LanguageService(client, Server(), Config(data_dir=tmp_path), mem, WorkingMemory(),
                          lambda: PersonaState(stage=stage), lambda i, l: i, idle=idle, now_fn=clock,
                          sync=True, lean_fn=lean)
    return svc, mem, clock


def ready(svc):
    svc.warm()
    assert svc.status == "ready"


def reflection_calls(client):
    return [c for c in client.calls if "memória do Engrama" in c[0]["content"]]


def test_chat_prompt_contains_recalled_fact(tmp_path):
    client = Client()
    svc, mem, _ = make(tmp_path, client)
    mem.upsert_fact("cor_favorita", "azul", 0.9, "chat")
    ready(svc)
    svc.request("qual a minha cor favorita?")
    svc.pump()
    chat = next(m for m in client.calls if m[-1]["content"].startswith("qual a minha"))
    assert "azul" in chat[0]["content"]


def test_extract_links_topics_and_updates_opinion(tmp_path):
    client = Client(facts=json.dumps({"facts": [], "topics": [["Jogos", 0.5]], "valence": 0.5}))
    svc, mem, _ = make(tmp_path, client, lean=lambda t: 0.4)
    ready(svc)
    svc.request("eu adoro jogos")
    svc.pump()
    op = mem.opinion("jogo")
    assert op is not None and op["lean"] == 0.4
    ep = mem._db.execute("SELECT id FROM episodes WHERE kind='chat'").fetchone()[0]
    assert ("topic", "jogo") in mem._db.execute(
        "SELECT kind, ref FROM episode_links WHERE episode_id=?", (ep,)).fetchall()


def test_chat_episode_links_known_topics(tmp_path):
    client = Client()
    svc, mem, _ = make(tmp_path, client)
    mem.bump_topic("Jogos", 0.5)
    ready(svc)
    svc.request("vamos falar de games")
    svc.pump()
    ep = mem._db.execute("SELECT id FROM episodes WHERE kind='chat'").fetchone()[0]
    assert mem._db.execute("SELECT ref FROM episode_links WHERE episode_id=? AND kind='topic'",
                           (ep,)).fetchall() == [("jogo",)]


def test_deleted_fact_not_recreated_by_queued_extract(tmp_path):
    state = {"idle": False}
    client = Client(facts=json.dumps({"facts": [["nome", "Ana", 0.9]], "topics": [], "valence": 0}))
    svc, mem, clock = make(tmp_path, client, idle=lambda: state["idle"])
    ready(svc)
    svc.request("meu nome é Ana")
    svc.pump()                      # chat runs; the extraction waits for idle
    clock.t += 5
    mem.delete_fact("nome")
    clock.t += 5
    state["idle"] = True
    svc.pump()
    assert mem.facts() == []


def test_newer_mention_unblocks_fact(tmp_path):
    client = Client(facts=json.dumps({"facts": [["nome", "Ana", 0.9]], "topics": [], "valence": 0}))
    svc, mem, clock = make(tmp_path, client)
    mem.upsert_fact("nome", "Ana", 0.5, "chat")
    mem.delete_fact("nome")
    clock.t += 10
    ready(svc)
    svc.request("meu nome é Ana")
    svc.pump()
    assert mem.facts() == [("nome", "Ana")]


def test_deleted_topic_not_recreated(tmp_path):
    state = {"idle": False}
    client = Client(facts=json.dumps({"facts": [], "topics": [["jogos", 0.5]], "valence": 0.5}))
    svc, mem, clock = make(tmp_path, client, idle=lambda: state["idle"])
    ready(svc)
    svc.request("gosto de jogos")
    svc.pump()
    clock.t += 5
    mem.delete_topic("jogo")
    state["idle"] = True
    svc.pump()
    assert mem.topic_rows() == [] and mem.opinion("jogo") is None


def _talk(svc, clock):
    svc.request("vamos falar de jogos")
    svc.pump()
    return clock.t


def test_reflection_after_gap_only_when_ready(tmp_path):
    reflect = json.dumps({"summary": "falamos de jogos 3 vezes", "topic": "jogos"})
    client = Client(reflect=reflect, warm_exc=LLMOffline("down"))
    svc, mem, clock = make(tmp_path, client)
    svc.tick(clock.t + 200)
    svc.pump()
    assert client.calls == []
    client.warm_exc = None
    clock.t += 100
    ready(svc)
    t = _talk(svc, clock)
    svc.tick(t + CONVERSATION_GAP_S - 1)
    svc.pump()
    assert mem.recent_reflections(5) == []
    clock.t = t + CONVERSATION_GAP_S + 1
    svc.tick(clock.t)
    svc.tick(clock.t + 10)
    svc.pump()
    refl = mem.recent_reflections(5)
    assert len(refl) == 1 and not any(c.isdigit() for c in refl[0])
    svc.tick(clock.t + 500)
    svc.pump()
    assert len(mem.recent_reflections(5)) == 1 and len(reflection_calls(client)) == 1
    assert ("topic", "jogo") in mem._db.execute("SELECT kind, ref FROM episode_links").fetchall()


def test_reflection_bad_json_is_ignored(tmp_path):
    client = Client(reflect="isso não é json 42 😀")
    svc, mem, clock = make(tmp_path, client)
    ready(svc)
    t = _talk(svc, clock)
    svc.tick(t + CONVERSATION_GAP_S + 1)
    svc.pump()
    assert len(reflection_calls(client)) == 1 and mem.recent_reflections(5) == []
    client.reflect = '{"topic": "x"}'
    svc._reflect()
    assert mem.recent_reflections(5) == []


def test_opinion_phrase_written_in_lang(tmp_path):
    reflect = json.dumps({"summary": "falamos de jogos", "topic": "jogos"})
    client = Client(reflect=reflect, opinion="adora jogos 99 porque são divertidos",
                    facts=json.dumps({"facts": [], "topics": [["jogos", 0.5]], "valence": 0.9}))
    svc, mem, clock = make(tmp_path, client, lean=lambda t: 0.8)
    ready(svc)
    t = _talk(svc, clock)
    svc.tick(t + CONVERSATION_GAP_S + 1)
    svc.pump()
    op = mem.opinion("jogo")
    assert op["phrase_lang"] == "pt" and op["phrase"].startswith("adora jogos") and "9" not in op["phrase"]
    opinion_call = next(c for c in client.calls if c[0]["content"].startswith("Escreva em uma linha"))
    assert "adora" in opinion_call[0]["content"]


def test_reflection_without_opinion_does_not_invent_one(tmp_path):
    client = Client(reflect=json.dumps({"summary": "papo", "topic": "jogos"}))
    svc, mem, clock = make(tmp_path, client)
    ready(svc)
    t = _talk(svc, clock)
    svc.tick(t + CONVERSATION_GAP_S + 1)
    svc.pump()
    assert mem.opinion("jogo") is None


def test_spontaneous_reply_clean(tmp_path):
    client = Client(chat="Como posso ajudar? 3")
    svc, _, _ = make(tmp_path, client)
    ready(svc)
    svc.spontaneous("current", "jogos")
    svc.pump()
    assert svc.replies.empty()


def test_spontaneous_emits_llm_reply_with_topic(tmp_path):
    client = Client(chat="estava pensando em jogos 7")
    svc, _, _ = make(tmp_path, client)
    ready(svc)
    svc.spontaneous("current", "jogos")
    svc.pump()
    r = svc.replies.get_nowait()
    assert r.source == "llm" and r.text == "estava pensando em jogos"
    assert "jogos" in client.calls[-1][-1]["content"] and "jogos" in client.calls[-1][0]["content"]


def test_spontaneous_needs_ready(tmp_path):
    client = Client()
    svc, _, _ = make(tmp_path, client)
    svc.spontaneous("past", "jogos")
    svc.pump()
    assert svc.replies.empty() and client.calls == []


def test_spontaneous_silent_for_egg(tmp_path):
    svc, _, _ = make(tmp_path, Client(), stage="egg")
    ready(svc)
    svc.spontaneous("current", "jogos")
    svc.pump()
    assert svc.replies.empty()
