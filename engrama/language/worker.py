import json
import logging
import queue
import random
import re
import threading
import time
from typing import Callable

from engrama.core.bus import Event, EventBus
from engrama.core.config import Config
from engrama.language.client import LLMOffline, LLMTimeout, OllamaClient
from engrama.language.lang import detect_lang
from engrama.language.persona import SPEECH, babble, build_messages, clean_reply

log = logging.getLogger(__name__)
MAX_INPUT = 500
OFFLINE_COOLDOWN = 30.0
FACTS_PROMPT = {
    "pt": ("Extraia da mensagem do usuário, em JSON puro e nada mais: "
           '{"facts":[[chave,valor,confianca]],"topics":[[assunto,delta]],"valence":-1..1}. '
           "facts: fatos sobre o usuário (confianca 0..1); topics: assuntos mencionados (delta -1..1); "
           "valence: humor da mensagem. Listas vazias se não houver nada."),
    "en": ("From the user's message, output pure JSON and nothing else: "
           '{"facts":[[key,value,confidence]],"topics":[[name,delta]],"valence":-1..1}. '
           "facts: facts about the user (confidence 0..1); topics: subjects mentioned (delta -1..1); "
           "valence: mood of the message. Empty lists if nothing applies."),
}


def parse_facts(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m[0])
        facts = [[str(k), str(v), float(c)] for k, v, c in d.get("facts", [])]
        topics = [[str(n), float(x)] for n, x in d.get("topics", [])]
        val = max(-1.0, min(1.0, float(d.get("valence", 0.0))))
    except (ValueError, TypeError, AttributeError):
        return None
    return {"facts": facts, "topics": topics, "valence": val}


class LanguageWorker:
    def __init__(self, client: OllamaClient, cfg: Config, bus: EventBus,
                 get_state: Callable[[], dict], get_history: Callable[[], list[dict]]):
        self.client, self.cfg, self.bus = client, cfg, bus
        self.get_state, self.get_history = get_state, get_history
        self.state = "offline"  # offline | loading | ready
        self._gen = 0
        self._down_until = 0.0
        self._last_lang = "pt"
        self._rng = random.Random()
        self._q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name="language-worker").start()

    def request(self, text: str) -> None:
        self._q.put(text)

    def warm(self) -> None:
        self._gen += 1
        gen, self.state = self._gen, "loading"
        threading.Thread(target=self._warm, args=(gen,), daemon=True).start()

    def _warm(self, gen: int) -> None:
        try:
            self.client.warm(self.cfg.model)
            if gen == self._gen:
                self.state = "ready"
        except Exception as e:
            if gen == self._gen:
                self.state = "offline"
                if not isinstance(e, LLMTimeout):
                    self._down_until = time.time() + OFFLINE_COOLDOWN

    def unload(self) -> None:
        self._gen += 1
        self.state = "offline"

        def work():
            try:
                self.client.unload(self.cfg.model)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _loop(self) -> None:
        while True:
            text = self._q.get()
            try:
                self._handle(text)
            except Exception:
                log.exception("language worker failed on a request")
                try:
                    self._post(babble(text, "baby", detect_lang(text, self._last_lang), self._rng),
                               self._last_lang, "babble")
                except Exception:
                    log.exception("babble fallback failed")

    def _post(self, text: str, lang: str, source: str) -> None:
        self.bus.post(Event("chat_out", {"text": text, "lang": lang, "source": source}))

    def _babble(self, text: str, stage: str, lang: str, hint: bool = False) -> None:
        out = babble(text, stage, lang, self._rng)
        if hint:
            out += " " + babble("", stage, lang, self._rng, key="brain_loading")
        self._post(out, lang, "babble")

    def _handle(self, text: str) -> None:
        text = (text or "").strip()[:MAX_INPUT]
        if not text:
            return
        lang = detect_lang(text, self._last_lang)
        self._last_lang = lang
        state = self.get_state()
        stage = state.get("stage", "baby")
        max_words = SPEECH.get(stage, SPEECH["baby"])[0]
        if max_words > 0 and self.state == "offline" and time.time() >= self._down_until:
            self.warm()
        if max_words == 0 or self.state != "ready":
            self._babble(text, stage, lang, hint=max_words > 0 and self.state == "loading")
            return
        msgs = build_messages(state, self.get_history(), text, lang)
        num_predict = 20 + 3 * max_words
        reply = None
        try:
            for temp in (0.8, 0.9):
                reply = clean_reply(self.client.chat(self.cfg.model, msgs, num_predict, temp), max_words)
                if reply:
                    break
        except LLMOffline:
            self.state, self._down_until = "offline", time.time() + OFFLINE_COOLDOWN
        except LLMTimeout:
            self.warm()
        if not reply:
            self._babble(text, stage, lang)
            return
        self._post(reply, lang, "llm")
        threading.Thread(target=self._extract, args=(text, lang), daemon=True).start()

    def _extract(self, text: str, lang: str) -> None:
        if self.state != "ready":
            return
        msgs = [{"role": "system", "content": FACTS_PROMPT[lang]}, {"role": "user", "content": text}]
        try:
            d = parse_facts(self.client.chat(self.cfg.model, msgs, 120, 0.2))
        except Exception:
            return
        if d is not None:
            self.bus.post(Event("facts", {**d, "text": text, "lang": lang}))
