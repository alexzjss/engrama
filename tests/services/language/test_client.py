import urllib.error

import pytest

from engrama.config import Config
from engrama.services.language.client import LLMOffline, LLMTimeout, OllamaClient, strip_think


def test_chat_body_has_think_false_and_keep_alive(tmp_path):
    seen = {}

    def http_json(url, body=None, timeout=20):
        seen.update(url=url, body=body, timeout=timeout)
        return {"message": {"content": "<think>x</think>pii!"}}

    c = OllamaClient(Config(data_dir=tmp_path), http_json=http_json)
    out = c.chat("m", [{"role": "user", "content": "oi"}], 60, 0.8)
    assert out == "pii!"
    assert seen["url"] == "http://127.0.0.1:11434/api/chat"
    assert seen["body"]["think"] is False
    assert seen["body"]["keep_alive"] == "600s"
    assert seen["body"]["options"] == {"num_ctx": 2048, "num_predict": 60, "temperature": 0.8}
    assert seen["timeout"] == 45


def test_keep_alive_follows_config(tmp_path):
    seen = {}
    cfg = Config(data_dir=tmp_path, keep_alive_s=120.0)
    OllamaClient(cfg, http_json=lambda u, b=None, timeout=20: seen.update(b=b) or {}).warm("m")
    assert seen["b"]["keep_alive"] == "120s"


def test_client_offline_raises_LLMOffline(tmp_path):
    def http_json(url, body=None, timeout=20):
        raise urllib.error.URLError(ConnectionRefusedError())

    c = OllamaClient(Config(data_dir=tmp_path), http_json=http_json)
    with pytest.raises(LLMOffline):
        c.chat("m", [], 10, 0.5)


def test_client_timeout_raises_LLMTimeout(tmp_path):
    def http_json(url, body=None, timeout=20):
        raise TimeoutError()

    c = OllamaClient(Config(data_dir=tmp_path), http_json=http_json)
    with pytest.raises(LLMTimeout):
        c.chat("m", [], 10, 0.5)


def test_client_offline_tags_none(tmp_path):
    def http_json(url, body=None, timeout=20):
        raise ConnectionRefusedError()

    assert OllamaClient(Config(data_dir=tmp_path), http_json=http_json).tags() is None


def test_tags_returns_names(tmp_path):
    c = OllamaClient(Config(data_dir=tmp_path), http_json=lambda u, b=None, timeout=20: {"models": [{"name": "a:1"}]})
    assert c.tags() == {"a:1"}


def test_warm_and_unload_bodies(tmp_path):
    calls = []
    c = OllamaClient(Config(data_dir=tmp_path),
                     http_json=lambda u, b=None, timeout=20: calls.append((u, b, timeout)) or {})
    c.warm("m")
    c.unload("m")
    assert calls[0][1]["keep_alive"] == "600s" and calls[0][2] == 300
    assert calls[1][1]["keep_alive"] == 0


def test_strip_think_closed_and_unclosed():
    assert strip_think("<think>a\nb</think> oi") == "oi"
    assert strip_think("oi <think>nunca fecha") == "oi"


def test_pull_progress(tmp_path):
    def http_stream(url, body, timeout=120):
        yield {"status": "pulling"}
        yield {"status": "pulling", "total": 200, "completed": 100}
        yield {"status": "success", "total": 200, "completed": 200}

    got = []
    c = OllamaClient(Config(data_dir=tmp_path), http_stream=http_stream)
    c.pull("m", lambda pct, st: got.append((pct, st)))
    assert got[-1][0] == 100 and (50, "pulling") in got


def test_pull_error_raises(tmp_path):
    c = OllamaClient(Config(data_dir=tmp_path), http_stream=lambda u, b, timeout=120: iter([{"error": "nope"}]))
    with pytest.raises(RuntimeError):
        c.pull("m", lambda p, s: None)


def test_embed_request_body(tmp_path):
    seen = {}

    def http_json(url, body=None, timeout=20):
        seen.update(url=url, body=body, timeout=timeout)
        return {"embeddings": [[1.0, 0.0]]}

    c = OllamaClient(Config(data_dir=tmp_path), http_json=http_json)
    assert c.embed("m", ["a"], 2.5) == [[1.0, 0.0]]
    assert seen["url"].endswith("/api/embed") and seen["timeout"] == 2.5
    assert seen["body"]["input"] == ["a"] and seen["body"]["truncate"] is True
    assert seen["body"]["model"] == "m" and seen["body"]["keep_alive"].endswith("s")


def test_embed_error_raises(tmp_path):
    c = OllamaClient(Config(data_dir=tmp_path), http_json=lambda u, b=None, timeout=20: {"error": "does not support embeddings"})
    with pytest.raises(RuntimeError):
        c.embed("m", ["a"], 1)


def test_embed_timeout_and_offline(tmp_path):
    def slow(url, body=None, timeout=20):
        raise TimeoutError("t")

    def down(url, body=None, timeout=20):
        raise urllib.error.URLError(ConnectionRefusedError())

    with pytest.raises(LLMTimeout):
        OllamaClient(Config(data_dir=tmp_path), http_json=slow).embed("m", ["a"], 1)
    with pytest.raises(LLMOffline):
        OllamaClient(Config(data_dir=tmp_path), http_json=down).embed("m", ["a"], 1)


def test_unload_embed_keep_alive_zero(tmp_path):
    seen = {}
    OllamaClient(Config(data_dir=tmp_path),
                 http_json=lambda u, b=None, timeout=20: seen.update(u=u, b=b) or {}).unload_embed("m")
    assert seen["b"]["keep_alive"] == 0 and seen["b"]["model"] == "m"
