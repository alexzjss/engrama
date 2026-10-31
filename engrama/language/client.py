import json
import re
import socket
import urllib.error
import urllib.request
from typing import Callable, Iterator

from engrama.core.config import Config

# (model name, i18n note key); the first one is the default
RECOMMENDED: list[tuple[str, str]] = [
    ("qwen3:1.7b", "model.note.qwen3_1_7b"),
    ("gemma3:1b", "model.note.gemma3_1b"),
    ("qwen2.5:1.5b", "model.note.qwen2_5_1_5b"),
    ("llama3.2:1b", "model.note.llama3_2_1b"),
    ("qwen3:4b", "model.note.qwen3_4b"),
]


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
        self._json(self._url("/api/generate"),
                   {"model": model, "prompt": "", "stream": False, "keep_alive": self.cfg.keep_alive}, 300)

    def unload(self, model: str) -> None:
        self._json(self._url("/api/generate"), {"model": model, "keep_alive": 0, "stream": False}, 20)

    def chat(self, model: str, messages: list[dict], num_predict: int, temperature: float,
             timeout: float = 45) -> str:
        body = {"model": model, "messages": messages, "stream": False, "think": False,
                "keep_alive": self.cfg.keep_alive,
                "options": {"num_ctx": 2048, "num_predict": num_predict, "temperature": temperature}}
        try:
            d = self._json(self._url("/api/chat"), body, timeout)
        except Exception as e:
            if _is_timeout(e):
                raise LLMTimeout(str(e)) from e
            if isinstance(e, (urllib.error.URLError, ConnectionError, OSError)):
                raise LLMOffline(str(e)) from e
            raise
        return strip_think(d["message"]["content"])
