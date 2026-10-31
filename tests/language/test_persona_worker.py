import random
import re
import time

from engrama.core.bus import EventBus
from engrama.core.config import Config
from engrama.i18n import _table
from engrama.language.client import LLMOffline
from engrama.language.lang import detect_lang
from engrama.language.persona import babble, build_messages, clean_reply
from engrama.language.worker import LanguageWorker

STATE = {"stage": "baby", "needs_top": ["fome", "sono"], "traits": {"curiosidade": 90, "sociabilidade": 40,
         "paciencia": 70, "independencia": 30, "criatividade": 50}, "favorites": ["fruta"], "disliked": ["peixe"],
         "topics": ["jogos 2"], "memories": ["falou do dia 12 de maio", "comeu 3 vezes", "brincou"],
         "valence": 0.5, "arousal": 0.4}


def test_detect_lang():
    for s in ("to triste hoje", "vc gosta de jogos?", "oi"):
        assert detect_lang(s, "en") == "pt"
    for s in ("hey are you hungry", "what's up"):
        assert detect_lang(s, "pt") == "en"
    assert detect_lang("ok", "en") == "en" and detect_lang("ok") == "pt"


def test_system_prompt_has_no_digits():
    for lang in ("pt", "en"):
        sys = build_messages(STATE, [], "oi", lang)[0]["content"]
        assert sys and not re.search(r"\d", sys)
        assert "Engrama" in sys


def test_prompt_stage_styles_differ():
    by = {s: build_messages({**STATE, "stage": s}, [], "oi", "en") for s in ("baby", "child", "adult")}
    assert len({m[0]["content"] for m in by.values()}) == 3
    assert len({m[2]["content"] for m in by.values()}) == 3  # few-shot answers differ
    assert by["baby"][-1] == {"role": "user", "content": "oi"}


def test_clean_reply_rejects_digits_and_assistant():
    assert clean_reply("fome 20 carinho 30", 6) is None
    assert clean_reply("How can I help you today?", 12) is None
    assert clean_reply("posso ajudar em algo?", 12) is None
    assert clean_reply('<think>x</think>"pii! oi oi 😀 vamos brincar agora mesmo"', 4) == "pii! oi oi vamos"


def test_babble_keys_localized():
    rng = random.Random(1)
    for lang in ("pt", "en"):
        for k in ("bleh", "missed_you", "brain_loading"):
            assert babble("", "baby", lang, rng, key=k) == _table(lang)[f"babble.{k}"]
    assert babble("oi", "egg", "en", rng).startswith("...")
    assert babble("bleh", "baby", "pt", rng) != _table("pt")["babble.bleh"]
    assert babble("xyz", "baby", "pt", rng)


class Fake:
    def __init__(self, reply="pii! oi oi!", exc=None, facts=None):
        self.reply, self.exc, self.facts, self.calls = reply, exc, facts, []

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.calls.append((messages, num_predict, temperature))
        if self.exc:
            raise self.exc
        if "JSON" in messages[0]["content"] and self.facts is not None:
            return self.facts
        return self.reply

    def warm(self, model):
        pass

    def unload(self, model):
        pass


def make(fake, stage="baby"):
    bus = EventBus()
    w = LanguageWorker(fake, Config(), bus, lambda: {**STATE, "stage": stage}, lambda: [])
    w.state = "ready"
    return w, bus


def wait(bus, kind, n=1, t=1.0):
    got, end = [], time.time() + t
    while time.time() < end and len(got) < n:
        got += [e for e in bus.drain() if e.kind == kind]
        time.sleep(0.01)
    return got


def test_worker_falls_back_when_offline():
    w, bus = make(Fake(exc=LLMOffline("x")))
    w.request("oi")
    ev = wait(bus, "chat_out")
    assert ev and ev[0].data["source"] == "babble" and ev[0].data["lang"] == "pt"
    assert w.state == "offline"


def test_worker_llm_ok_and_loading_hint():
    w, bus = make(Fake())
    w.request("hello")
    assert wait(bus, "chat_out")[0].data == {"text": "pii! oi oi!", "lang": "en", "source": "llm"}
    w.state = "loading"
    w.request("hello")
    d = wait(bus, "chat_out")[0].data
    assert d["source"] == "babble" and d["text"].endswith("(brain loading)")


def test_worker_retry_then_babble():
    f = Fake(reply="fome 20 carinho 30")
    w, bus = make(f)
    w.request("oi")
    ev = wait(bus, "chat_out")
    assert ev[0].data["source"] == "babble" and len(f.calls) == 2
    assert f.calls[1][2] == 0.9


def test_odd_inputs():
    f = Fake()
    w, bus = make(f)
    w.request("")
    w.request("   ")
    w.request("x" * 5000)
    ev = wait(bus, "chat_out", 1)
    time.sleep(0.1)
    ev += wait(bus, "chat_out", 1, 0.2)
    assert len(ev) == 1
    assert len(f.calls[0][0][-1]["content"]) <= 500
    w.request("😀")
    assert wait(bus, "chat_out")


def test_facts_extraction_posts_event():
    w, bus = make(Fake(facts='{"facts":[["nome","Ana",0.9]],"topics":[["jogos",0.5]],"valence":0.4}'))
    w.request("meu nome é Ana")
    f = wait(bus, "facts")
    assert f and f[0].data["facts"] == [["nome", "Ana", 0.9]] and f[0].data["valence"] == 0.4
    w2, bus2 = make(Fake(facts="not json"))
    w2.request("meu nome é Ana")
    assert wait(bus2, "chat_out") and not wait(bus2, "facts", t=0.3)


def test_egg_uses_no_llm():
    f = Fake()
    w, bus = make(f, "egg")
    w.request("oi")
    assert wait(bus, "chat_out")[0].data["source"] == "babble" and not f.calls


def test_unexpected_error_still_answers():
    def boom():
        raise RuntimeError("x")
    bus = EventBus()
    w = LanguageWorker(Fake(), Config(), bus, boom, lambda: [])
    w.request("oi")
    ev = wait(bus, "chat_out")
    assert ev and ev[0].data["source"] == "babble"


def test_egg_does_not_warm_and_prompt_details():
    f = Fake()
    bus = EventBus()
    w = LanguageWorker(f, Config(), bus, lambda: {**STATE, "stage": "egg"}, lambda: [])
    w.request("oi")
    wait(bus, "chat_out")
    assert w.state == "offline"
    sys = build_messages(STATE, [], "x", "en")[0]["content"]
    assert "You are hungry and sleepy" in sys or "you are hungry and sleepy" in sys
    assert "  " not in sys
