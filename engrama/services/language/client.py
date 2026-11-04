import json
import re
import socket
import urllib.error
import urllib.request
from typing import Callable, Iterator

from engrama.config import Config

CHAT_NUM_CTX = 2048   # context for chat and warm-up (must match, or Ollama reloads the model)


class LLMOffline(Exception):
    pass


class LLMTimeout(Exception):
    pass


def http_json(url: str, body: dict | None = None, timeout: float = 20):
    """GET (body None) or POST JSON; returns parsed JSON."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def http_stream(url: str, body: dict, timeout: float = 120) -> Iterator[dict]:
    """POST JSON and yield one parsed dict per ndjson line."""
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            if line.strip():
                yield json.loads(line)


def strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<think>.*", "", text, flags=re.S).strip()


def _is_timeout(e: BaseException) -> bool:
    if isinstance(e, urllib.error.URLError) and not isinstance(e, urllib.error.HTTPError):
        e = e.reason if isinstance(e.reason, BaseException) else e
    return isinstance(e, (TimeoutError, socket.timeout))


class OllamaClient:
    def __init__(self, cfg: Config, http_json=http_json, http_stream=http_stream):
        self.cfg = cfg
        self._json = http_json
        self._stream = http_stream

    def _url(self, path: str) -> str:
        return self.cfg.ollama_url + path

    def _keep_alive(self) -> str:
        return f"{int(self.cfg.keep_alive_s)}s"

    def tags(self) -> set[str] | None:
        try:
            d = self._json(self._url("/api/tags"), None, 3)
            return {m["name"] for m in d.get("models", [])}
        except Exception:
            return None

    def pull(self, name: str, on_progress: Callable[[int, str], None]) -> None:
        pct = 0
        for d in self._stream(self._url("/api/pull"), {"model": name, "stream": True}, 120):
            if d.get("error"):
                raise RuntimeError(d["error"])
            if d.get("total"):
                pct = int(100 * d.get("completed", 0) / d["total"])
            on_progress(pct, d.get("status", ""))

    def warm(self, model: str) -> None:
        # same num_ctx as chat(): a different context size makes Ollama reload the model on the first chat
        self._json(self._url("/api/generate"),
                   {"model": model, "prompt": "", "stream": False, "keep_alive": self._keep_alive(),
                    "options": {"num_ctx": CHAT_NUM_CTX}}, 300)

    def unload(self, model: str) -> None:
        self._json(self._url("/api/generate"), {"model": model, "keep_alive": 0, "stream": False}, 20)

    def chat(self, model: str, messages: list[dict], num_predict: int, temperature: float,
             timeout: float = 45) -> str:
        body = {"model": model, "messages": messages, "stream": False, "think": False,
                "keep_alive": self._keep_alive(),
                "options": {"num_ctx": CHAT_NUM_CTX, "num_predict": num_predict, "temperature": temperature}}
        try:
            d = self._json(self._url("/api/chat"), body, timeout)
        except Exception as e:
            if _is_timeout(e):
                raise LLMTimeout(str(e)) from e
            if isinstance(e, (urllib.error.URLError, ConnectionError, OSError)):
                raise LLMOffline(str(e)) from e
            raise
        return strip_think(d["message"]["content"])

    def embed(self, model: str, texts: list[str], timeout: float) -> list[list[float]]:
        body = {"model": model, "input": texts, "truncate": True, "keep_alive": self._keep_alive()}
        try:
            d = self._json(self._url("/api/embed"), body, timeout)
        except Exception as e:
            if _is_timeout(e):
                raise LLMTimeout(str(e)) from e
            if isinstance(e, (urllib.error.URLError, ConnectionError, OSError)):
                raise LLMOffline(str(e)) from e
            raise
        if isinstance(d, dict) and d.get("error"):
            raise RuntimeError(str(d["error"]))
        return d["embeddings"]

    def unload_embed(self, model: str) -> None:
        # Ollama documents unloading with keep_alive 0; for an embedding-only model the
        # request goes to /api/embed with an empty input (/api/generate refuses such models).
        # Not verified against Ollama 0.18 here (no model installed on the reference machine).
        self._json(self._url("/api/embed"), {"model": model, "input": [], "keep_alive": 0}, 20)
