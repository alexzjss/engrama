"""LanguageService: prioritized background LLM jobs with a babble fallback.

Priorities: chat 0 > comment 1 > reflection 2 > facts 3. Jobs with priority >= 1 run
only when the LLM is `ready` and the injected `idle()` is true. The LLM never picks
actions; it only produces speech. Nothing here raises into the caller's thread.
"""
from __future__ import annotations

import json
import logging
import queue
import random
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from engrama.services.language.client import LLMOffline, LLMTimeout
from engrama.services.language.lang import detect_lang
from engrama.services.language.persona import (SPEECH, PersonaState, babble, build_messages, clean_reply,
                                               strip_emoji, valence)

log = logging.getLogger(__name__)
MAX_INPUT = 500
OFFLINE_COOLDOWN = 30.0
P_CHAT, P_COMMENT, P_REFLECT, P_FACTS = 0, 1, 2, 3
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


@dataclass(frozen=True)
class Reply:
    text: str
    lang: str
    source: str  # "llm" | "babble"


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


class LanguageService:
    """
    now_fn: wall clock (injectable). idle: background-jobs gate (injectable).
    sync=True: no threads; warm/unload/pull run inline and `pump()` drains the queue
    on the caller's thread (tests). sync=False: one daemon worker thread.
    """

    def __init__(self, client, server, cfg, memory, working, get_state: Callable[[], PersonaState],
                 food_name: Callable[[str, str], str], idle: Callable[[], bool] = lambda: True,
                 now_fn: Callable[[], float] = time.time, rng: random.Random | None = None,
                 sync: bool = False) -> None:
        self.client, self.server, self.cfg = client, server, cfg
        self.memory, self.working = memory, working
        self.get_state, self.food_name, self.idle = get_state, food_name, idle
        self._now = now_fn
        self._rng = rng or random.Random()
        self._sync = sync
        self.replies: queue.Queue[Reply] = queue.Queue()
        self._state = "offline"      # offline | loading | ready
        self._pulling = False
        self._gen = 0
        self._down_until = 0.0
        self._last_activity: float | None = None
        self._last_lang = "pt"
        self._jobs: list[tuple[int, int, Callable[[], None]]] = []
        self._seq = 0
        self._cv = threading.Condition()
        self._stop = False
        self._thread: threading.Thread | None = None
        if not sync:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="language-service")
            self._thread.start()

    # ---- status -------------------------------------------------------
    @property
    def status(self) -> str:
        if self._pulling:
            return "pulling"
        try:
            if not self.server.available():
                return "missing"
        except Exception:
            return "missing"
        return self._state

    def installed_models(self) -> set[str] | None:
        try:
            return self.client.tags()
        except Exception:
            return None

    # ---- public API ---------------------------------------------------
    def request(self, text: str) -> None:
        text = (text or "").strip()[:MAX_INPUT]
        if not text:
            return
        self._enqueue(P_CHAT, lambda: self._chat(text))

    def comment(self, text: str) -> None:
        """Low-priority spontaneous remark about `text`; runs only when ready and idle."""
        text = (text or "").strip()[:MAX_INPUT]
        if text:
            self._enqueue(P_COMMENT, lambda: self._comment(text))

    def submit_job(self, priority: int, fn: Callable[[], None]) -> None:
        """Generic background job (priority 1-3); runs only when ready and idle."""
        self._enqueue(max(P_COMMENT, priority), fn)

    def warm(self) -> None:
        self._gen += 1
        gen = self._gen
        self._state = "loading"
        self._spawn(lambda: self._warm(gen))

    def unload(self) -> None:
        self._gen += 1
        self._state = "offline"
        self._down_until = 0.0

        def work():
            try:
                self.client.unload(self.cfg.model)
            except Exception:
                pass
        self._spawn(work)

    def tick(self, now: float) -> None:
        """Unload the model after keep_alive_s without conversation."""
        if (self._state == "ready" and self._last_activity is not None
                and now - self._last_activity > self.cfg.keep_alive_s):
            self.unload()

    def pull(self, name: str, on_progress: Callable[[int, str], None]) -> None:
        """Non-blocking download. on_progress(pct, status); on failure on_progress(-1, "error: ...")."""
        self._pulling = True

        def work():
            try:
                if not self.server.running() and not self.server.start():
                    raise LLMOffline("ollama not running")
                self.client.pull(name, on_progress)
            except Exception as e:
                try:
                    on_progress(-1, f"error: {e}")
                except Exception:
                    pass
            finally:
                self._pulling = False
        self._spawn(work)

    def shutdown(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=0.5)

    def pump(self) -> int:
        """Synchronously run every eligible queued job (sync mode / tests). Returns the count."""
        n = 0
        while True:
            job = self._take()
            if job is None:
                return n
            self._run(job)
            n += 1

    # ---- internals ----------------------------------------------------
    def _spawn(self, fn: Callable[[], None]) -> None:
        if self._sync:
            fn()
        else:
            threading.Thread(target=fn, daemon=True, name="language-io").start()

    def _enqueue(self, prio: int, fn: Callable[[], None]) -> None:
        with self._cv:
            self._seq += 1
            self._jobs.append((prio, self._seq, fn))
            self._cv.notify_all()

    def _eligible(self, prio: int) -> bool:
        if prio == P_CHAT:
            return True
        try:
            return self.status == "ready" and bool(self.idle())
        except Exception:
            return False

    def _take(self):
        with self._cv:
            for job in sorted(self._jobs, key=lambda j: (j[0], j[1])):
                if self._eligible(job[0]):
                    self._jobs.remove(job)
                    return job
        return None

    def _run(self, job) -> None:
        try:
            job[2]()
        except Exception:
            log.exception("language job failed")
            if job[0] == P_CHAT:
                try:
                    self.replies.put(Reply(babble("", "baby", self._last_lang, self._rng), self._last_lang, "babble"))
                except Exception:
                    log.exception("babble fallback failed")

    def _loop(self) -> None:
        while True:
            with self._cv:
                if self._stop:
                    return
            job = self._take()
            if job is None:
                with self._cv:
                    if self._stop:
                        return
                    self._cv.wait(0.2)
                continue
            self._run(job)

    def _warm(self, gen: int) -> None:
        try:
            if not self.server.running() and not self.server.start():
                raise LLMOffline("ollama not running")
            self.client.warm(self.cfg.model)
            if gen == self._gen:
                self._state = "ready"
                self._last_activity = self._now()
        except Exception as e:
            if gen == self._gen:
                self._state = "offline"
                if not isinstance(e, LLMTimeout):
                    self._down_until = self._now() + OFFLINE_COOLDOWN

    def _babble(self, text: str, stage: str, lang: str, hint: bool = False) -> Reply:
        out = babble(text, stage, lang, self._rng)
        if hint:
            out += " " + babble("", stage, lang, self._rng, key="brain_loading")
        return Reply(out, lang, "babble")

    def _chat(self, text: str) -> None:
        lang = detect_lang(text, self._last_lang)
        self._last_lang = lang
        state = self.get_state()
        max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
        now = self._now()
        if max_words > 0 and self.status == "offline" and now >= self._down_until:
            self.warm()
        st = self.status
        reply: Reply | None = None
        if max_words > 0 and st == "ready":
            self._last_activity = now
            msgs = build_messages(state, self.working.messages(), text, lang, self.food_name)
            num_predict = 20 + 3 * max_words
            out = None
            try:
                for temp in (0.8, 0.9):
                    out = clean_reply(self.client.chat(self.cfg.model, msgs, num_predict, temp), max_words)
                    if out:
                        break
            except LLMOffline:
                self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
            except LLMTimeout:
                self.warm()
            if out:
                reply = Reply(out, lang, "llm")
        if reply is None:
            reply = self._babble(text, state.stage, lang, hint=max_words > 0 and st == "loading")
        self._record(text, reply, lang)
        self.replies.put(reply)
        if reply.source == "llm":
            self._enqueue(P_FACTS, lambda: self._extract(text, lang))

    def _record(self, text: str, reply: Reply, lang: str) -> None:
        self.working.add("user", text)
        self.working.add("assistant", reply.text)
        try:
            clean = re.sub(r"\s+", " ", re.sub(r"\d+", "", strip_emoji(text))).strip()[:120]
            self.memory.add_episode("chat", f"conversa: {clean}", valence(text, lang))
        except Exception:
            log.exception("could not store chat episode")

    def _comment(self, text: str) -> None:
        state = self.get_state()
        max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
        if max_words <= 0:
            return
        lang = self._last_lang
        msgs = build_messages(state, [], text, lang, self.food_name)
        try:
            out = clean_reply(self.client.chat(self.cfg.model, msgs, 20 + 3 * max_words, 0.9), max_words)
        except LLMOffline:
            self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
            return
        except LLMTimeout:
            return
        if out:
            self.replies.put(Reply(out, lang, "llm"))

    def _extract(self, text: str, lang: str) -> None:
        msgs = [{"role": "system", "content": FACTS_PROMPT[lang]}, {"role": "user", "content": text}]
        try:
            d = parse_facts(self.client.chat(self.cfg.model, msgs, 120, 0.2))
        except Exception:
            return
        if d is None:
            return
        try:
            for k, v, c in d["facts"]:
                self.memory.upsert_fact(k, v, c, "chat")
            for name, delta in d["topics"]:
                self.memory.bump_topic(name, delta)
        except Exception:
            log.exception("could not store facts")
