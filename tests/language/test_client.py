import urllib.error
from pathlib import Path

import pytest

from engrama.core.config import Config
from engrama.language.client import LLMOffline, LLMTimeout, OllamaClient, RECOMMENDED, strip_think
from engrama.language.server import OllamaServer


class FakeProc:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def _cfg(tmp_path):
    exe = tmp_path / "ollama.exe"
    exe.write_text("x")
    return Config(data_dir=tmp_path, ollama_exe=exe)


def _ping_after_start():
    state = {"up": False}

    def ping(url, timeout):
        up, state["up"] = state["up"], True
        return up

    return ping


def test_server_start_uses_e_drive_env(tmp_path):
    seen = {}

    def popen(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return FakeProc()

    cfg = _cfg(tmp_path)
    cfg.ollama_home = Path(r"E:\Ollama\home")
    cfg.ollama_models = Path(r"E:\Ollama\models")
    srv = OllamaServer(cfg, popen=popen, ping=_ping_after_start())
    assert srv.start() is True
    assert srv.owned
    env = seen["kw"]["env"]
    assert env["OLLAMA_MODELS"] == r"E:\Ollama\models"
    assert env["USERPROFILE"] == r"E:\Ollama\home"
    assert env["HOME"] == r"E:\Ollama\home"
    assert seen["cmd"] == [str(cfg.ollama_exe), "serve"]


def test_server_does_not_stop_foreign(tmp_path):
    called = []
    srv = OllamaServer(_cfg(tmp_path), popen=lambda *a, **k: called.append(1), ping=lambda u, t: True)
    assert srv.start() is True
    assert not srv.owned and not called
    srv.stop()  # must not raise or touch anything


def test_server_stop_terminates_owned(tmp_path):
    proc = FakeProc()
    srv = OllamaServer(_cfg(tmp_path), popen=lambda *a, **k: proc, ping=_ping_after_start())
    srv.start()
    srv.stop()
    assert proc.terminated


def test_server_unavailable_without_exe(tmp_path):
    cfg = Config(data_dir=tmp_path, ollama_exe=tmp_path / "missing.exe")
    srv = OllamaServer(cfg, ping=lambda u, t: False)
    assert not srv.available()
    assert srv.start() is False


def test_chat_body_has_think_false(tmp_path):
    seen = {}

    def http_json(url, body=None, timeout=20):
        seen.update(url=url, body=body, timeout=timeout)
        return {"message": {"content": "<think>x</think>pii!"}}

    c = OllamaClient(Config(data_dir=tmp_path), http_json=http_json)
    out = c.chat("m", [{"role": "user", "content": "oi"}], 60, 0.8)
    assert out == "pii!"
    assert seen["url"].endswith("/api/chat")
    assert seen["body"]["think"] is False
    assert seen["body"]["options"] == {"num_ctx": 2048, "num_predict": 60, "temperature": 0.8}
    assert seen["timeout"] == 45


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
    c = OllamaClient(Config(data_dir=tmp_path), http_json=lambda u, b=None, timeout=20: calls.append((u, b, timeout)) or {})
    c.warm("m")
    c.unload("m")
    assert calls[0][1]["keep_alive"] == "10m" and calls[0][2] == 300
    assert calls[1][1]["keep_alive"] == 0


def test_strip_think_closed_and_unclosed():
    assert strip_think("<think>a\nb</think> oi") == "oi"
    assert strip_think("oi <think>nunca fecha") == "oi"


def test_recommended_default_first():
    assert RECOMMENDED[0] == ("qwen3:1.7b", "model.note.qwen3_1_7b")
    assert [n for n, _ in RECOMMENDED][1:] == ["gemma3:1b", "qwen2.5:1.5b", "llama3.2:1b", "qwen3:4b"]


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
