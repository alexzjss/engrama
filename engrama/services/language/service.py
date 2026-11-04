"""LanguageService: prioritized background LLM jobs with a babble fallback.

Priorities: chat 0 > comment 1 > reflection 2 > facts 3 > index 4. Jobs with priority >= 1 run
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

from engrama.services.language.client import LLMOffline, LLMTimeout, strip_think
from engrama.services.language.lang import detect_lang
from engrama.services.language.persona import (build_farewell_messages, farewell_babble, OPINION_PROMPT, build_file_messages, REFLECT_PROMPT, SPEECH, SPONTANEOUS_PROMPT,
                                               PersonaState, apply_recall, babble, build_messages, clean_reply,
                                               strip_emoji, valence)
from engrama.services.memory import CONVERSATION_GAP_S, EMBED_BATCH, INDEX_EVERY_S
from engrama.services.memory.opinions import stance_word
from engrama.services.memory.recall import recall
from engrama.services.memory.topics import normalize_topic, plain_text

log = logging.getLogger(__name__)
MAX_INPUT = 500
OFFLINE_COOLDOWN = 30.0
P_CHAT, P_COMMENT, P_REFLECT, P_FACTS, P_INDEX = 0, 1, 2, 3, 4
FACTS_PROMPT = {
    "pt": ("Extraia da mensagem do usuário, em JSON puro e nada mais: "
           '{"facts":[[chave,valor,confianca]],"topics":[[assunto,delta]],"valence":-1..1}. '
           "facts: só fatos duradouros que o PRÓPRIO USUÁRIO afirma sobre si ou sua vida (nome, bichos, família, "
           "trabalho, hobbies, gostos), com chave curta e valor concreto, confianca 0..1. "
           "Nunca perguntas, nunca falas da criatura ou de um assistente, nunca clima ou acontecimentos de um dia só. "
           'Exemplo: "meu gato se chama Bolota" -> [["nome_do_gato","Bolota",0.9]]. '
           "Se não houver fato, facts deve ser lista vazia. "
           "topics: assuntos mencionados (delta -1..1); valence: humor da mensagem."),
    "en": ("From the user's message, output pure JSON and nothing else: "
           '{"facts":[[key,value,confidence]],"topics":[[name,delta]],"valence":-1..1}. '
           "facts: only durable facts the USER states about themselves or their life (name, pets, family, job, "
           "hobbies, likes), with a short key and a concrete value, confidence 0..1. "
           "Never questions, never words about the creature or an assistant, never weather or one-off events. "
           'Example: "my cat is called Pumpkin" -> [["cat_name","Pumpkin",0.9]]. '
           "If there is no fact, facts must be an empty list. "
           "topics: subjects mentioned (delta -1..1); valence: mood of the message."),
}
CLASSIFY_PROMPT = ("Classify the program by its process name only. Answer with exactly one word "
                   "from this list and nothing else: {cats}.")


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


_FACT_BAD_VALUES = {"true", "false", "yes", "no", "sim", "não", "nao", "null", "none", "n/a"}
_FACT_AI_RE = re.compile(
    r"\bassistant\b|\bassistente\b|\bai\b|\bia\b|language model|modelo de linguagem|alibaba|qwen|"
    r"\bchatbot\b|\bengrama\b", re.I)
_FACT_QUESTION_RE = re.compile(
    r"^(who|what|why|how|when|where|which|do|does|are|is|can|could|quem|qual|quais|que|o que|por que|porque|"
    r"como|quando|onde|quanto|voce|você)\b", re.I)
_FACT_STOP = {"going", "to", "the", "a", "an", "and", "or", "of", "in", "on", "is", "are", "it", "this", "that",
              "ir", "indo", "de", "do", "da", "em", "no", "na", "um", "uma", "o", "os", "as", "que", "e", "ou",
              "true", "false", "sleep", "rest"}


def sanitize_facts(facts: list) -> list:
    """Conservative deterministic filter for LLM-extracted facts [[key, value, conf], ...].

    Drops questions, yes/no values, talk about the assistant/AI, too-short keys/values and
    keys made only of stopwords. Never logs content.
    """
    out = []
    for k, v, c in facts:
        k, v = str(k).strip(), str(v).strip()
        if len(k) < 3 or len(v) < 2:
            continue
        if "?" in k or v.endswith("?") or _FACT_QUESTION_RE.match(k.replace("_", " ")):
            continue
        if v.lower().strip(" .!") in _FACT_BAD_VALUES:
            continue
        if _FACT_AI_RE.search(k) or _FACT_AI_RE.search(v):
            continue
        kw = [w for w in re.split(r"[\s_\-]+", k.lower()) if w]
        vw = [w for w in re.split(r"[\s_\-]+", v.lower().strip(" .!")) if w]
        if not kw or all(w in _FACT_STOP for w in kw) or all(w in _FACT_STOP for w in vw):
            continue
        if k.lower() == v.lower():
            continue
        out.append([k, v, c])
    return out


class LanguageService:
    """
    now_fn: wall clock (injectable). idle: background-jobs gate (injectable).
    sync=True: no threads; warm/unload/pull run inline and `pump()` drains the queue
    on the caller's thread (tests). sync=False: one daemon worker thread.
    """

    def __init__(self, client, server, cfg, memory, working, get_state: Callable[[], PersonaState],
                 food_name: Callable[[str, str], str], idle: Callable[[], bool] = lambda: True,
                 now_fn: Callable[[], float] = time.time, rng: random.Random | None = None,
                 sync: bool = False, lean_fn: Callable[[str], float] | None = None, embedder=None) -> None:
        self.client, self.server, self.cfg = client, server, cfg
        self.memory, self.working = memory, working
        self.embedder = embedder                # None = no recall by meaning (M8 behaviour)
        self._index_more = True                 # there may be memories without a vector
        self._index_queued = False
        self._next_index = 0.0
        self.get_state, self.food_name, self.idle = get_state, food_name, idle
        self._now = now_fn
        self._rng = rng or random.Random()
        self._sync = sync
        self._lean_fn = lean_fn or (lambda topic: 0.0)
        self._last_llm_reply: float | None = None
        self._reflect_due = False               # an llm conversation not yet reflected on
        self.replies: queue.Queue[Reply] = queue.Queue()
        self._state = "offline"      # offline | loading | ready
        self._pulling = False
        self._gen = 0
        self._down_until = 0.0
        self._last_activity: float | None = None
        self._last_lang = "pt"
        self._jobs: list[tuple[int, int, Callable[[], None]]] = []
        self._seq = 0
        self._chatting = 0                      # chat-priority LLM calls in flight
        self._pending: tuple[str, str, list[dict], float, int | None] | None = None   # message that arrived while loading
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

    @property
    def busy(self) -> bool:
        """True while a chat answer is being produced (LLM call in flight or waiting on warm-up)."""
        return self._chatting > 0 or (self._pending is not None and self._state == "loading")

    @property
    def embed_status(self) -> str:
        if self.embedder is None:
            return "off"
        try:
            return self.embedder.status
        except Exception:
            return "failed"

    def embed_counts(self) -> dict:
        try:
            return dict(self.memory.vector_counts())
        except Exception:
            return {}

    def set_embed_model(self, name: str) -> None:
        """Choose the embedding model. A different name drops every vector; indexing restarts on the next warm."""
        name = (name or "").strip()
        old = (self.cfg.embed_model or "").strip()
        self.cfg.embed_model = name
        if self.embedder is None or old == name:
            return
        self._switch_model(old)

    def set_semantic_recall(self, on: bool) -> None:
        """Off: drop every vector and unload the embedding model. On: it is checked on the next warm-up."""
        old = (self.cfg.embed_model or "").strip()
        self.cfg.semantic_recall = bool(on)
        if self.embedder is None:
            return
        if on:
            self._index_more = True
            return
        self._switch_model(old)

    def _embed_model(self) -> str:
        try:
            return self.embedder.model if self.embedder is not None else ""
        except Exception:
            return ""

    def _switch_model(self, old: str) -> None:
        """Vectors of the old model are useless: drop them, unload it, go cold."""
        try:
            self.memory.drop_vectors()
            new = self._embed_model()
            if new:
                self.memory.set_vector_model(new)
        except Exception:
            log.exception("could not drop vectors")
        self._index_more = True
        self._spawn(lambda: self._unload_embedder(old))

    def _unload_embedder(self, old: str = "") -> None:
        emb = self.embedder
        if emb is None:
            return
        try:
            client = getattr(emb, "client", None)
            if old and client is not None and getattr(client, "unload_embed", None) and old != self._embed_model():
                client.unload_embed(old)
        except Exception:
            pass
        try:
            emb.unload()
        except Exception:
            pass

    def _qvec(self, text: str):
        """Query embedding, only when the chat model and the embedder are both ready; else None."""
        emb = self.embedder
        if emb is None or not (text or "").strip():
            return None
        try:
            if self.status != "ready" or emb.status != "ready":
                return None
            vec = emb.query(text)
            if self._dim_changed():
                return None
            return vec
        except Exception:
            return None

    def _dim_changed(self) -> bool:
        """The embedder reported another dimension: same as a model switch (caller's flag is cleared here)."""
        emb = self.embedder
        if emb is None or not getattr(emb, "dim_changed", False):
            return False
        emb.dim_changed = False
        old = self._embed_model()
        try:
            self.memory.drop_vectors()
            if old:
                self.memory.set_vector_model(old)
        except Exception:
            log.exception("could not drop vectors")
        self._index_more = True
        self._unload_embedder("")
        return True

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
        t_msg = self._now()
        self._enqueue(P_CHAT, lambda: self._chat(text, t_msg))

    def share_file(self, glimpse) -> None:
        """The user dropped a file: comment on it (chat priority). Content lives in memory only."""
        self._enqueue(P_CHAT, lambda: self._share(glimpse))

    def comment(self, text: str) -> None:
        """Low-priority spontaneous remark about `text`; runs only when ready and idle."""
        text = (text or "").strip()[:MAX_INPUT]
        if text:
            self._enqueue(P_COMMENT, lambda: self._comment(text))

    def classify_app(self, process: str) -> None:
        """Low-priority: ask the LLM for a category of `process` (name only). Never raises."""
        try:
            process = (process or "").strip().lower()[:80]
            if process:
                self._enqueue(P_FACTS, lambda: self._classify_app(process))
        except Exception:
            log.exception("classify_app enqueue failed")

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
            self._unload_embedder("")
            try:
                self.memory.release_vectors()
            except Exception:
                pass
        self._spawn(work)

    def spontaneous(self, kind: str, topic: str | None = None) -> None:
        """Rare self-initiated remark (kind: current | opinion | past | activity | ancestral); low priority, ready + idle only."""
        if kind in SPONTANEOUS_PROMPT["pt"]:
            self._enqueue(P_COMMENT, lambda: self._spontaneous(kind, topic))

    def farewell(self, cause: str, on_text: Callable[[str], None]) -> None:
        """Last words at death (chat priority): short LLM goodbye when ready, else affectionate babble. Never raises."""
        try:
            self._enqueue(P_CHAT, lambda: self._farewell(cause, on_text))
        except Exception:
            log.exception("farewell enqueue failed")
            try:
                on_text(farewell_babble(self._last_lang, self._rng))
            except Exception:
                pass

    def _farewell(self, cause: str, on_text: Callable[[str], None]) -> None:
        lang = self._last_lang
        text = None
        try:
            state = self.get_state()
            max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
            if max_words > 0 and state.stage not in ("egg", "baby") and self.status == "ready":
                msgs = build_farewell_messages(state, cause, lang, self.food_name)
                self._chatting += 1
                try:
                    text = clean_reply(self.client.chat(self.cfg.model, msgs, 20 + 3 * max_words, 0.8), max_words)
                finally:
                    self._chatting -= 1
        except LLMOffline:
            self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
        except Exception:
            log.exception("farewell failed")
        if not text:
            text = farewell_babble(lang, self._rng)
        try:
            on_text(text)
        except Exception:
            log.exception("farewell callback failed")

    def tick(self, now: float) -> None:
        """Queue a reflection once a conversation went quiet; unload the model after keep_alive_s."""
        if (self._reflect_due and self._last_llm_reply is not None
                and now - self._last_llm_reply >= CONVERSATION_GAP_S):
            self._reflect_due = False
            self._enqueue(P_REFLECT, self._reflect)
        if (self._state == "ready" and self._last_activity is not None
                and now - self._last_activity > self.cfg.keep_alive_s):
            self.unload()
        emb = self.embedder
        if (emb is not None and self._index_more and not self._index_queued and self._state == "ready"
                and now >= self._next_index):
            try:
                if emb.status == "ready":
                    self._index_queued = True
                    self._enqueue(P_INDEX, self._index)
            except Exception:
                log.exception("index scheduling failed")

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
                pending = self._pending
                if pending is not None:
                    self._enqueue(P_CHAT, lambda: self._answer_pending(pending))
                self._warm_embedder(gen)
        except Exception as e:
            if gen == self._gen:
                self._state = "offline"
                self._pending = None
                if not isinstance(e, LLMTimeout):
                    self._down_until = self._now() + OFFLINE_COOLDOWN

    def _warm_embedder(self, gen: int) -> None:
        """Embedding model warms with the chat model. Its failure never touches the LLM state."""
        emb = self.embedder
        if emb is None:
            return
        try:
            st = emb.refresh()
            if st == "cold":
                emb.warm()
                st = emb.status
            if st == "ready" and gen == self._gen:
                self.memory.set_vector_model(emb.model)
                self._dim_changed()
                self._index_more = True
        except Exception:
            log.exception("embedder warm-up failed")

    def _index(self) -> None:
        """One batch of unindexed memories -> vectors. Never loads a model; writes only for the same model."""
        self._index_queued = False
        emb = self.embedder
        if emb is None or emb.status != "ready":
            return
        model = emb.model
        if not model:
            return
        mem = self.memory
        self._next_index = self._now() + INDEX_EVERY_S
        mem.set_vector_model(model)
        items = mem.unindexed(EMBED_BATCH)
        if not items:
            self._index_more = False
            return
        vecs = emb.documents([t for _, _, t, _ in items])
        if self._dim_changed() or vecs is None or len(vecs) != len(items):
            return
        wrote = mem.put_vectors(model, [(k, r, h, v) for (k, r, _t, h), v in zip(items, vecs)])
        if len(items) < EMBED_BATCH and wrote == len(items):
            self._index_more = False

    def _babble(self, text: str, stage: str, lang: str, hint: bool = False) -> Reply:
        out = babble(text, stage, lang, self._rng)
        if hint:
            out += " " + babble("", stage, lang, self._rng, key="brain_loading")
        return Reply(out, lang, "babble")

    def _chat(self, text: str, t_msg: float | None = None) -> None:
        lang = detect_lang(text, self._last_lang)
        self._last_lang = lang
        state = self.get_state()
        max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
        now = self._now()
        t_msg = now if t_msg is None else t_msg
        if max_words > 0:
            state = apply_recall(state, recall(self.memory, text, state.stage, lang, qvec=self._qvec(text)))
        if max_words > 0 and self.status == "offline" and now >= self._down_until:
            self.warm()
        st = self.status
        reply: Reply | None = None
        history = self.working.messages()
        if max_words > 0 and st == "ready":
            self._last_activity = now
            out = self._ask(state, history, text, lang, max_words)
            if out:
                reply = Reply(out, lang, "llm")
                self._pending = None
        if reply is None:
            reply = self._babble(text, state.stage, lang, hint=max_words > 0 and st == "loading")
        eid = self._record(text, reply, lang)
        if reply.source == "babble" and max_words > 0 and st == "loading":
            pending = self._pending = (text, lang, history, t_msg, eid)   # answered once warm-up finishes
            if self._state == "ready":       # warm-up finished while we were building the babble
                self._enqueue(P_CHAT, lambda: self._answer_pending(pending))
        self.replies.put(reply)
        if reply.source == "llm":
            self._mark_llm_reply()
            self._enqueue(P_FACTS, lambda: self._extract(text, lang, t_msg, eid))

    def _ask(self, state, history: list[dict], text: str, lang: str, max_words: int, file_ctx=None) -> str | None:
        if file_ctx is not None:
            msgs = build_file_messages(state, lang, file_ctx[0], file_ctx[1], text, self.food_name)
        else:
            msgs = build_messages(state, history, text, lang, self.food_name)
        num_predict = 20 + 3 * max_words
        out = None
        self._chatting += 1
        try:
            for temp in (0.8, 0.9):
                out = clean_reply(self.client.chat(self.cfg.model, msgs, num_predict, temp), max_words)
                if out:
                    break
        except LLMOffline:
            self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
        except LLMTimeout:
            self.warm()
        finally:
            self._chatting -= 1
        return out or None

    def _answer_pending(self, pending) -> None:
        if self._pending is not pending:     # superseded by a newer message, or already answered
            return
        text, lang, history, t_msg, eid, *extra = pending
        file_ctx = extra[0] if extra else None
        self._pending = None
        state = self.get_state()
        max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
        if max_words <= 0 or self.status != "ready":
            return
        if file_ctx is None:
            state = apply_recall(state, recall(self.memory, text, state.stage, lang, qvec=self._qvec(text)))
        self._last_activity = self._now()
        out = self._ask(state, history, text, lang, max_words, file_ctx)
        if not out:
            return
        self.working.add("assistant", out)
        self.replies.put(Reply(out, lang, "llm"))
        self._mark_llm_reply()
        if file_ctx is None:
            self._enqueue(P_FACTS, lambda: self._extract(text, lang, t_msg, eid))

    def _share(self, g) -> None:
        lang = self._last_lang
        state = self.get_state()
        max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
        kind = re.sub(r"[^a-z]", "", str(g.kind).lower()) or "arquivo"
        self._index_more = True
        try:
            self.memory.add_episode("arquivo", f"mostrou um arquivo de {kind}", importance=0.5)
        except Exception:
            log.exception("could not store file episode")
        now = self._now()
        if max_words > 0 and self.status == "offline" and now >= self._down_until:
            self.warm()
        st = self.status
        excerpt = g.text if g.text else ", ".join(g.entries) if g.entries else g.name
        excerpt = excerpt.strip()[:MAX_INPUT] or g.name
        ctx = (g.name, kind)
        reply: Reply | None = None
        if max_words > 0 and st == "ready":
            self._last_activity = now
            out = self._ask(state, [], excerpt, lang, max_words, ctx)
            if out:
                reply = Reply(out, lang, "llm")
                self._pending = None
                self.working.add("assistant", out)
        if reply is None:
            reply = self._babble("", state.stage, lang, hint=max_words > 0 and st == "loading")
            if max_words > 0 and st == "loading":
                pending = self._pending = (excerpt, lang, [], now, None, ctx)
                if self._state == "ready":
                    self._enqueue(P_CHAT, lambda: self._answer_pending(pending))
        self.replies.put(reply)
        if reply.source == "llm":
            self._mark_llm_reply()

    def _mark_llm_reply(self) -> None:
        self._last_llm_reply = self._now()
        self._reflect_due = True

    def _known_topics(self, text: str) -> list[str]:
        """Known topic names mentioned in `text` (normalized words, plus multi-word names)."""
        plain = plain_text(text)
        words = {normalize_topic(w) for w in re.split(r"[^a-z]+", plain) if w}
        out = []
        for r in self.memory.topic_rows():
            n = r["name"]
            if n in words or (" " in n and n in plain):
                out.append(n)
        return out

    def _record(self, text: str, reply: Reply, lang: str) -> int | None:
        self._index_more = True
        self.working.add("user", text)
        self.working.add("assistant", reply.text)
        try:
            clean = re.sub(r"\s+", " ", re.sub(r"\d+", "", strip_emoji(text))).strip()[:120]
            return self.memory.add_episode("chat", f"conversa: {clean}", valence(text, lang),
                                           topics=self._known_topics(text))
        except Exception:
            log.exception("could not store chat episode")
            return None

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

    def _classify_app(self, process: str) -> None:
        try:
            from engrama.services.perception.categories import CATEGORIES
            allowed = set(CATEGORIES) | {"programa"}
            if self.memory.app_category(process) is not None:
                return
            msgs = [{"role": "system", "content": CLASSIFY_PROMPT.format(cats=", ".join(sorted(allowed)))},
                    {"role": "user", "content": process}]
            out = self.client.chat(self.cfg.model, msgs, 8, 0.0)
            ans = plain_text(strip_think(out or "")).strip().strip(".,!\"' ")
            if ans in allowed:
                self.memory.set_app_category(process, ans, "llm")
        except LLMOffline:
            self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
        except Exception:
            log.exception("classify_app failed")

    def _extract(self, text: str, lang: str, t_msg: float | None = None, eid: int | None = None) -> None:
        t_msg = self._now() if t_msg is None else t_msg
        msgs = [{"role": "system", "content": FACTS_PROMPT[lang]}, {"role": "user", "content": text}]
        try:
            d = parse_facts(self.client.chat(self.cfg.model, msgs, 120, 0.2))
        except Exception:
            return
        if d is None:
            return
        mem = self.memory
        self._index_more = True
        topics, facts = [], []
        try:
            for k, v, c in sanitize_facts(d["facts"]):
                if mem.is_blocked("fact", k, since=t_msg):     # deleted after the message: stays deleted
                    continue
                mem.unblock_on_new_mention("fact", k, t_msg)
                if mem.upsert_fact(k, v, c, "chat"):
                    facts.append(k)
            for name, delta in d["topics"]:
                if mem.is_blocked("topic", name, since=t_msg):
                    continue
                mem.unblock_on_new_mention("topic", name, t_msg)
                key = mem.bump_topic(name, delta)
                if key:
                    mem.update_opinion(key, self._lean_fn, d["valence"])
                    topics.append(key)
            if eid is not None and (topics or facts):
                mem.link_episode(eid, topics=topics, facts=facts)
        except Exception:
            log.exception("could not store facts")

    def _reflect(self) -> None:
        lang = self._last_lang
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in self.working.messages()[-8:])
        if not convo:
            return
        msgs = [{"role": "system", "content": REFLECT_PROMPT[lang]}, {"role": "user", "content": convo}]
        try:
            raw = self.client.chat(self.cfg.model, msgs, 120, 0.3)
        except LLMOffline:
            self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
            return
        except Exception:
            return
        m = re.search(r"\{.*\}", strip_think(raw or ""), re.S)
        try:
            d = json.loads(m[0]) if m else None
            summary = re.sub(r"\s+", " ", re.sub(r"\d+", "", strip_emoji(str(d["summary"])))).strip()[:200]
            topic = d.get("topic")
            topic = normalize_topic(re.sub(r"\d+", "", strip_emoji(str(topic)))) if topic else ""
        except (ValueError, TypeError, KeyError, AttributeError):
            return
        if not summary:
            return
        mem = self.memory
        self._index_more = True
        try:
            if topic == "null" or (topic and mem.is_blocked("topic", topic)):
                topic = ""
            mem.add_episode("reflection", summary, importance=0.6, topics=[topic] if topic else [])
            op = mem.opinion(topic) if topic else None
            if op and not (op.get("phrase") and op.get("phrase_lang") == lang):
                self._write_opinion_phrase(topic, op["stance"], lang)
        except Exception:
            log.exception("reflection failed")

    def _write_opinion_phrase(self, topic: str, stance: float, lang: str) -> None:
        word = stance_word(stance, lang)
        msgs = [{"role": "system", "content": OPINION_PROMPT[lang].format(topic=topic, stance=word)},
                {"role": "user", "content": topic}]
        try:
            out = clean_reply(self.client.chat(self.cfg.model, msgs, 60, 0.6), 20)
        except Exception:
            return
        if out:
            self.memory.set_opinion_phrase(topic, out, lang)

    def _spontaneous(self, kind: str, topic: str | None) -> None:
        state = self.get_state()
        max_words = SPEECH.get(state.stage, SPEECH["baby"])[0]
        if max_words <= 0:
            return
        lang = self._last_lang
        topic = re.sub(r"\d+", "", topic or "").strip()
        state = apply_recall(state, recall(self.memory, topic, state.stage, lang, qvec=self._qvec(topic)))
        if kind == "ancestral":
            state.ancestral = [topic] if topic else []
        if topic and kind == "current":
            state.current_topics = [topic]
        elif topic and kind == "past":
            state.past_topics = [topic]
        msgs = build_messages(state, [], SPONTANEOUS_PROMPT[lang][kind].format(topic=topic or "?"), lang,
                              self.food_name)
        try:
            out = clean_reply(self.client.chat(self.cfg.model, msgs, 20 + 3 * max_words, 0.9), max_words)
        except LLMOffline:
            self._state, self._down_until = "offline", self._now() + OFFLINE_COOLDOWN
            return
        except LLMTimeout:
            return
        if out:
            self.replies.put(Reply(out, lang, "llm"))
