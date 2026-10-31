"""Chat: Ollama in a background thread, with a local babble fallback (works with no LLM)."""
import json
import os
import queue
import random
import re
import socket
import threading
import time
import urllib.error
import urllib.request

from creature import TRAIT_PT
from foods import taste_summary

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
DEFAULTS = {"model": "qwen3:1.7b", "ollama_url": "http://localhost:11434", "keep_alive": "10m"}
# (name, nota) tuned for an 8GB RAM laptop without dGPU
RECOMMENDED = [
    ("qwen3:1.7b", "recomendado: bom PT/EN, ~1.4GB"),
    ("gemma3:1b", "mais leve, ~0.8GB"),
    ("qwen2.5:1.5b", "alternativa leve, ~1GB"),
    ("llama3.2:1b", "leve, inglês melhor que português"),
    ("qwen3:4b", "mais esperto, mais pesado (~2.6GB), pode pesar com 8GB"),
]


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except FileNotFoundError:
        save_config(cfg)
    except Exception as e:
        print("config ignored:", e)
    if os.environ.get("CREATURE_MODEL"):
        cfg["model"] = os.environ["CREATURE_MODEL"]
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({k: cfg[k] for k in DEFAULTS}, f, indent=2)
    except Exception as e:
        print("config save failed:", e)


def http_json(url, body=None, timeout=20):
    """GET (body None) or POST JSON, return parsed JSON. Module-level so tests can monkeypatch it."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def http_stream(url, body, timeout=60):
    """POST JSON and yield one parsed dict per response line (Ollama ndjson streaming)."""
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            if line.strip():
                yield json.loads(line)


def strip_think(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<think>.*", "", text, flags=re.S).strip()

PT_WORDS = {"oi", "olá", "ola", "você", "voce", "não", "nao", "sim", "tudo", "bem", "quer", "comer", "brincar",
            "fome", "sono", "com", "como", "que", "uma", "meu", "bom", "boa", "dormir", "amo", "carinho", "tá", "ta", "to", "triste", "hoje", "estou",
            "gosta", "jogos", "muito", "feliz", "cansado", "obrigado", "também", "tambem"}


def is_pt(text):
    t = text.lower()
    if any(ch in t for ch in "ãõçáéíóúâêô"):
        return True
    return any(w in PT_WORDS for w in t.replace("?", " ").replace("!", " ").replace(",", " ").split())


def babble(text, stage="baby", seed=0):
    rng = random.Random(hash((text, time.time() // 1)) ^ seed)
    t = text.lower()
    pt = is_pt(text)
    if stage == "egg":
        return "... (o ovo vibra)" if pt else "... (the egg trembles)"
    if any(k in t for k in ("fome", "comer", "comida", "food", "hungry", "eat")):
        return rng.choice(["nom nom? * fome!", "mam... mam! brr", "nhom! nhom!"])
    if any(k in t for k in ("oi", "olá", "ola", "hi", "hello", "hey")):
        return rng.choice(["pii! * oi?", "gru? * pi-pi!", "hii... brr!"])
    if any(k in t for k in ("amo", "love", "fofo", "cute", "carinho")):
        return rng.choice(["prrr... * brr", "pi-pii! (feliz)", "mmm... gru gru"])
    if any(k in t for k in ("dorm", "sleep", "sono", "night", "noite")):
        return rng.choice(["zzz... gru", "uaaa... sono..."])
    syl = ["gru", "brr", "pi", "mu", "nha", "kii", "ra", "bu"]
    s = " ".join(rng.choice(syl) + rng.choice(["?", "!", "...", ""]) for _ in range(rng.randint(2, 4)))
    return s + " *"


# need -> phrase shown to the model (only when the urge is above URGE_T; the model never sees numbers)
URGE_T = 50
URGE_WORDS = {"fome": "you are hungry", "sono": "you are sleepy", "tedio": "you are bored and want to play",
              "carinho": "you want cuddles and attention", "curiosidade": "you are curious about everything"}
# trait -> (adjective when high, adjective when low)
TRAIT_WORDS = {"curiosidade": ("curious", "calm"), "sociabilidade": ("friendly", "shy"),
               "paciencia": ("patient", "impatient"), "independencia": ("independent", "clingy"),
               "criatividade": ("creative", "plain")}
# few-shot pairs (both languages); neutral on needs so they do not leak a fake mood
FEWSHOT = {True: [("oi!", "pii! oi oi!"), ("quer brincar?", "gru! sim sim! pii!"),
                  ("o que você é?", "engrama! bebê digi! pii!")],
           False: [("hi!", "pii! hi hi!"), ("what are you?", "engrama! me digi-baby, pii!"),
                   ("do you like music?", "brr... music! yes yes! gru!")]}
EMOJI_RE = re.compile("[🀀-🫿☀-➿⬀-⯿️‍]")
ASSISTANT_RE = re.compile(r"posso ajudar|em que posso|how can i (help|assist)|as an ai|assistente|assistant", re.I)


def mood_words(c):
    urges = sorted(((v, k) for k, v in c.needs.items() if v > URGE_T), reverse=True)[:2]
    return [URGE_WORDS[k] for _, k in urges]


def trait_words(c):
    ranked = sorted(c.traits.items(), key=lambda kv: kv[1])
    out = []
    if ranked[-1][1] >= 55:
        out.append(TRAIT_WORDS[ranked[-1][0]][0])
    if ranked[0][1] <= 40:
        out.append(TRAIT_WORDS[ranked[0][0]][1])
    return out


def build_system(c, memory, lang_hint):
    mood = "; ".join(mood_words(c)) or "you feel fine and calm"
    traits = ", ".join(trait_words(c)) or "gentle"
    style = ("Baby speech: one to six words, mixing simple words and baby sounds like 'gru', 'pii', 'brr'."
             if c.stage == "baby" else "You are still an egg: only muffled sounds.")
    memory = re.sub(r"\d+", "", memory or "").strip() or "nothing yet"
    return ("You are Engrama, a baby digital creature (Digimon-inspired, but original). You know you are a digital "
            "creature living in a small window on your human's PC. Your human is talking to you: RESPOND TO WHAT "
            f"THEY SAID, in character. {style} Never list stats or numbers. Never act like an assistant (no 'how can "
            f"I help'). No emojis, one short line. Right now {mood}. You are {traits}. {_taste(c)}"
            "(Mention foods only if the human talks about food.) "
            f"Recent memory: {memory}. "
            f"Reply in the SAME language the human wrote in (Portuguese or English): {lang_hint}")


def _taste(c):
    fav, bad = taste_summary(getattr(c, "prefs", None) or {})
    parts = []
    if fav:
        parts.append("Favorite foods: " + ", ".join(fav) + ".")
    if bad:
        parts.append("Foods you dislike: " + ", ".join(bad) + ".")
    return " ".join(parts) + (" " if parts else "")


def clean_reply(text):
    """Strip think blocks/emojis; return '' when the reply is unusable (numbers, stat dump, assistant-speak)."""
    text = EMOJI_RE.sub("", strip_think(text)).strip().strip('"').split("\n")[0].strip()
    if re.search(r"\d", text) or ASSISTANT_RE.search(text):
        return ""
    return text[:140]


def is_timeout(e):
    return isinstance(e, (TimeoutError, socket.timeout)) or (
        isinstance(e, urllib.error.URLError) and isinstance(e.reason, (TimeoutError, socket.timeout)))


def keep_seconds(v):
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)", str(v))
    return int(m[1]) * {"": 1, "s": 1, "m": 60, "h": 3600}[m[2]] if m else 600


class LLM:
    def __init__(self):
        self.cfg = load_config()
        self.out = queue.Queue()
        self.down_until = 0.0
        self.mode = "idle"  # last mode used: 'idle' (none yet) | 'ollama' | 'babble'
        self.state = "offline"  # offline | loading (model being loaded into RAM) | ready
        self.gen = 0  # bumped on warm/unload so stale background threads do not clobber state
        self.last_ok = 0.0
        self.history = []
        # model screen state (written by background threads, read by the UI)
        self.installed = None  # set of names, or None = unknown/unreachable
        self.tags_state = "idle"  # idle | loading | ok | down
        self.pull = None  # {"model","pct","status","error","done"} or None

    @property
    def model(self):
        return self.cfg["model"]

    def label(self):
        if self.state == "loading":
            return "llm: acordando..."
        return f"llm: {self.model}" if self.mode != "babble" else "llm: babble (offline)"

    def set_model(self, name):
        name = name.strip()
        if not name:
            return
        self.cfg["model"] = name
        self.history = []
        self.down_until = 0.0
        save_config(self.cfg)
        self.warm()

    def _fail(self, e, gen):
        """Connection refused / HTTP errors = offline with cooldown; a timeout is not a dead server."""
        if gen != self.gen:
            return
        self.state, self.mode = "offline", "babble"
        if not is_timeout(e):
            self.down_until = time.time() + 30

    def warm(self):
        """Load the model in the background (empty /api/generate). A cold load can take minutes."""
        self.gen += 1
        gen, self.state = self.gen, "loading"
        threading.Thread(target=self._warm, args=(gen,), daemon=True).start()

    def _warm(self, gen):
        try:
            http_json(self.cfg["ollama_url"] + "/api/generate", {"model": self.model, "prompt": "", "stream": False,
                                                                 "keep_alive": self.cfg["keep_alive"]}, timeout=300)
            if gen == self.gen:
                self.state, self.last_ok = "ready", time.time()
                if self.mode == "babble":
                    self.mode = "idle"
        except Exception as e:
            self._fail(e, gen)

    def unload(self):
        """Free the model's RAM now (keep_alive 0), e.g. for rest mode."""
        self.gen += 1
        self.state = "offline"
        model = self.model

        def work():
            try:
                http_json(self.cfg["ollama_url"] + "/api/generate", {"model": model, "keep_alive": 0, "stream": False}, timeout=20)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def is_installed(self, name):
        if not self.installed:
            return False
        return name in self.installed or (":" not in name and name + ":latest" in self.installed)

    def refresh_tags(self):
        def work():
            self.tags_state = "loading"
            try:
                d = http_json(self.cfg["ollama_url"] + "/api/tags", timeout=3)
                self.installed = {m["name"] for m in d.get("models", [])}
                self.tags_state = "ok"
            except Exception:
                self.installed, self.tags_state = None, "down"
        threading.Thread(target=work, daemon=True).start()

    def choose(self, name):
        """Activate a model; pull it first (background) if Ollama is up and it is not installed."""
        name = name.strip()
        if not name or (self.pull and not self.pull["done"]):
            return
        if self.tags_state != "ok" or self.is_installed(name):
            self.set_model(name)
            return
        self.pull = {"model": name, "pct": 0, "status": "iniciando...", "error": None, "done": False}
        threading.Thread(target=self._pull, args=(name,), daemon=True).start()

    def _pull(self, name):
        p = self.pull
        try:
            body = {"model": name, "stream": True}
            for d in http_stream(self.cfg["ollama_url"] + "/api/pull", body, timeout=120):
                if d.get("error"):
                    raise RuntimeError(d["error"])
                p["status"] = d.get("status", "")
                if d.get("total"):
                    p["pct"] = int(100 * d.get("completed", 0) / d["total"])
            p["pct"], p["status"] = 100, "pronto"
            self.set_model(name)
            self.refresh_tags()
        except Exception as e:
            p["error"] = str(e)[:60] or "falhou"
        p["done"] = True

    def ask(self, text, system, fallback_fn, use_llm=True):
        threading.Thread(target=self._work, args=(text, system, fallback_fn, use_llm), daemon=True).start()

    def _chat(self, text, system, temp, timeout):
        msgs = [{"role": "system", "content": system}]
        pt = is_pt(text)  # examples/history in the other language make a small model answer in that language
        for u, a in FEWSHOT[pt]:
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        hist = [m for i, m in enumerate(self.history) if is_pt(self.history[i - i % 2]["content"]) == pt]
        msgs += hist[-6:] + [{"role": "user", "content": text}]
        body = {"model": self.model, "messages": msgs, "stream": False, "think": False,
                "keep_alive": self.cfg["keep_alive"],
                "options": {"num_ctx": 2048, "num_predict": 60, "temperature": temp}}
        d = http_json(self.cfg["ollama_url"] + "/api/chat", body, timeout=timeout)
        return clean_reply(d["message"]["content"])

    def _work(self, text, system, fallback_fn, use_llm):
        reply, hint = None, ""
        if use_llm and self.state == "ready" and time.time() - self.last_ok > keep_seconds(self.cfg["keep_alive"]):
            self.warm()  # model was probably unloaded by keep_alive: do not wait on a cold chat
        if use_llm and self.state == "offline" and time.time() >= self.down_until:
            self.warm()
        if use_llm and self.state == "loading":
            hint = " zzz... (cérebro carregando)" if is_pt(text) else " zzz... (brain loading)"
        elif use_llm and self.state == "ready":
            gen = self.gen
            try:
                for temp in (0.8, 0.9):  # retry once if the reply has numbers / looks like a stat dump
                    reply = self._chat(text, system, temp, 45)
                    if reply:
                        break
                if reply:
                    self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
                    self.mode, self.last_ok = "ollama", time.time()
            except Exception as e:
                reply = None
                if is_timeout(e):
                    self.warm()  # probably went cold; wait for it without marking the server dead
                else:
                    self._fail(e, gen)
        if not reply:
            if self.state == "offline":
                self.mode = "babble"
            reply = fallback_fn(text) + hint
        self.out.put(reply)
