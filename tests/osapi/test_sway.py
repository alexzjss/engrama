import json
import struct

from engrama.osapi import ActiveWindow, sway

ENV = {"SWAYSOCK": "/run/sway.sock"}


class _Fake:
    def __init__(self, reply=b""):
        self.reply, self.sent, self.timeout = reply, b"", None

    def settimeout(self, t): self.timeout = t
    def sendall(self, b): self.sent += b
    def recv(self, n):
        r, self.reply = self.reply[:n], self.reply[n:]
        return r
    def close(self): pass


def _frame(payload, typ=4):
    body = json.dumps(payload).encode()
    return b"i3-ipc" + struct.pack("<II", len(body), typ) + body


def _tree(focused_node):
    return {"focused": False, "nodes": [
        {"focused": False, "nodes": [{"focused": False, "nodes": [], "floating_nodes": []}],
         "floating_nodes": [focused_node]}], "floating_nodes": []}


def test_socket_path():
    assert sway.socket_path(ENV) == "/run/sway.sock"
    assert sway.socket_path({}) is None


def test_ipc_header():
    f = _Fake(_frame({}, 4))
    out = sway.request(4, b"", ENV, connect=lambda p: f)
    assert f.sent == b"i3-ipc" + struct.pack("<II", 0, 4)
    assert out == b"{}"
    f = _Fake(b"")
    sway.request(2, b"abc", ENV, connect=lambda p: f)
    assert f.sent == b"i3-ipc" + struct.pack("<II", 3, 2) + b"abc"


def test_focused_node_found():
    node = {"focused": True, "pid": 42, "app_id": "Foot", "name": "vim", "fullscreen_mode": 0,
            "rect": {"x": 1, "y": 2, "width": 30, "height": 40}, "nodes": [], "floating_nodes": []}
    w = sway.active_window(ENV, connect=lambda p: _Fake(_frame(_tree(node))))
    assert w == ActiveWindow(pid=42, cls="foot", title="vim", fullscreen=False, rect=(1, 2, 30, 40))


def test_fullscreen_mode():
    node = {"focused": True, "pid": 1, "app_id": "a", "name": "n", "fullscreen_mode": 1,
            "rect": {"x": 0, "y": 0, "width": 1, "height": 1}}
    w = sway.active_window(ENV, connect=lambda p: _Fake(_frame(node)))
    assert w.fullscreen is True


def test_xwayland_class_fallback():
    node = {"focused": True, "pid": 5, "app_id": None, "name": "Steam", "fullscreen_mode": 0,
            "window_properties": {"class": "Steam"}, "rect": {"x": 0, "y": 0, "width": 5, "height": 5}}
    w = sway.active_window(ENV, connect=lambda p: _Fake(_frame(node)))
    assert w.cls == "steam"


def test_no_focus_none_and_errors():
    tree = {"focused": False, "nodes": [{"focused": False, "nodes": []}]}
    assert sway.active_window(ENV, connect=lambda p: _Fake(_frame(tree))) is None
    assert sway.active_window({}) is None
    assert sway.active_window(ENV, connect=lambda p: _Fake(b"")) is None
    assert sway.active_window(ENV, connect=lambda p: _Fake(b"i3-ipc" + struct.pack("<II", 99, 4) + b"{")) is None
    assert sway.active_window(ENV, connect=lambda p: _Fake(b"lixo" * 5)) is None

    def boom(p):
        raise OSError("x")
    assert sway.active_window(ENV, connect=boom) is None
