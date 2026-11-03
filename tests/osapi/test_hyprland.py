import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

from engrama.osapi import ActiveWindow, hyprland

FIX = Path(__file__).parent / "fixtures" / "hypr_activewindow.json"


def _server(path, reply: bytes | None, silent=False):
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(path))
    srv.listen(1)
    got = []

    def run():
        conn, _ = srv.accept()
        conn.settimeout(2)
        try:
            got.append(conn.recv(4096))
            if silent:
                time.sleep(1)
            elif reply is not None:
                conn.sendall(reply)
        except OSError:
            pass
        finally:
            conn.close()
            srv.close()

    threading.Thread(target=run, daemon=True).start()
    return got


def _env(tmp_path, sig="sig"):
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("sem AF_UNIX")
    tmp_path = Path(tempfile.mkdtemp(prefix="hy"))   # caminho curto: limite do sockaddr_un
    d = tmp_path / "hypr" / sig
    d.mkdir(parents=True)
    return {"XDG_RUNTIME_DIR": str(tmp_path), "HYPRLAND_INSTANCE_SIGNATURE": sig}, d / ".socket.sock"


def test_socket_path(tmp_path):
    env, sock = _env(tmp_path)
    assert hyprland.socket_path(env) == str(sock)
    assert hyprland.socket_path({}) is None
    assert hyprland.socket_path({"XDG_RUNTIME_DIR": str(tmp_path)}) is None


def test_socket_path_legacy(tmp_path):
    env = {"XDG_RUNTIME_DIR": str(tmp_path / "nada"), "HYPRLAND_INSTANCE_SIGNATURE": "zz"}
    assert hyprland.socket_path(env) == str(tmp_path / "nada/hypr/zz/.socket.sock")
    # sem o caminho novo existente, o antigo vale se existir
    assert hyprland.socket_path({"HYPRLAND_INSTANCE_SIGNATURE": "zz"}) == "/tmp/hypr/zz/.socket.sock"


def test_active_window_from_fixture(tmp_path):
    env, sock = _env(tmp_path)
    got = _server(sock, FIX.read_bytes())
    w = hyprland.active_window(env)
    assert got == [b"j/activewindow"]
    data = json.loads(FIX.read_text())
    assert w == ActiveWindow(
        pid=data["pid"], cls="code", title="Exemplo - Editor", fullscreen=False,
        rect=(data["at"][0], data["at"][1], data["size"][0], data["size"][1]))


def _win(**kw):
    base = {"pid": 7, "class": "Firefox", "title": "t", "at": [0, 0], "size": [10, 20], "fullscreen": 0}
    base.update(kw)
    return json.dumps(base).encode()


def test_fullscreen_flags():
    def aw(fs, **kw):
        return hyprland.active_window({"HYPRLAND_INSTANCE_SIGNATURE": "s", "XDG_RUNTIME_DIR": "/x"},
                                      connect=lambda p: _Fake(_win(fullscreen=fs, **kw)))
    assert aw(0).fullscreen is False
    assert aw(1).fullscreen is False      # maximizada, não tela cheia
    assert aw(2).fullscreen is True
    assert aw(3).fullscreen is True
    assert aw(0).cls == "firefox"


class _Fake:
    def __init__(self, reply):
        self.reply, self.sent = reply, b""

    def settimeout(self, t): pass
    def connect(self, p): pass
    def sendall(self, b): self.sent += b
    def recv(self, n):
        r, self.reply = self.reply[:n], self.reply[n:]
        return r
    def close(self): pass


def test_empty_object_is_none_and_bad_json():
    env = {"HYPRLAND_INSTANCE_SIGNATURE": "s", "XDG_RUNTIME_DIR": "/x"}
    assert hyprland.active_window(env, connect=lambda p: _Fake(b"{}")) is None
    assert hyprland.active_window(env, connect=lambda p: _Fake(b"{}\n")) is None
    assert hyprland.active_window(env, connect=lambda p: _Fake(b"nao json")) is None
    assert hyprland.active_window(env, connect=lambda p: _Fake(b"[1]")) is None


def test_missing_socket_none(tmp_path):
    assert hyprland.active_window({}) is None
    env = {"XDG_RUNTIME_DIR": str(tmp_path), "HYPRLAND_INSTANCE_SIGNATURE": "none"}
    assert hyprland.request("j/activewindow", env) is None
    assert hyprland.active_window(env) is None


def test_silent_socket_times_out(tmp_path):
    env, sock = _env(tmp_path)
    _server(sock, None, silent=True)
    t = time.monotonic()
    assert hyprland.request("j/activewindow", env) is None
    assert time.monotonic() - t <= 0.3
