import subprocess
from pathlib import Path

from engrama.config import Config
from engrama.services.language.server import OllamaServer


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


def test_server_env_points_to_drive_e(tmp_path):
    seen = {}

    def popen(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return FakeProc()

    cfg = _cfg(tmp_path)
    cfg.ollama_home = Path(r"E:\Ollama\home")
    cfg.ollama_models = Path(r"E:\Ollama\models")
    srv = OllamaServer(cfg, popen=popen, ping=_ping_after_start())
    assert srv.start() is True
    assert srv.started_by_us
    env = seen["kw"]["env"]
    assert env["OLLAMA_MODELS"] == str(cfg.ollama_models)
    assert env["USERPROFILE"] == env["HOME"] == str(cfg.ollama_home)
    assert seen["kw"]["creationflags"] & getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    assert seen["cmd"] == [str(cfg.ollama_exe), "serve"]


def test_stop_only_kills_what_we_started(tmp_path):
    called = []
    foreign = OllamaServer(_cfg(tmp_path), popen=lambda *a, **k: called.append(1), ping=lambda u, t: True)
    assert foreign.start() is True
    assert not foreign.started_by_us and not called
    foreign.stop()  # must not raise or touch anything

    proc = FakeProc()
    ours = OllamaServer(_cfg(tmp_path), popen=lambda *a, **k: proc, ping=_ping_after_start())
    ours.start()
    assert ours.started_by_us
    ours.stop()
    assert proc.terminated and not ours.started_by_us


def test_missing_exe_is_unavailable_not_error(tmp_path):
    cfg = Config(data_dir=tmp_path, ollama_exe=tmp_path / "missing.exe")
    srv = OllamaServer(cfg, ping=lambda u, t: False)
    assert not srv.available()
    assert srv.start() is False
    assert not srv.started_by_us


def test_available_when_running_without_exe(tmp_path):
    cfg = Config(data_dir=tmp_path, ollama_exe=tmp_path / "missing.exe")
    assert OllamaServer(cfg, ping=lambda u, t: True).available()


def test_start_timeout_returns_false(tmp_path):
    srv = OllamaServer(_cfg(tmp_path), popen=lambda *a, **k: FakeProc(), ping=lambda u, t: False,
                       start_timeout=0.3)
    assert srv.start() is False
