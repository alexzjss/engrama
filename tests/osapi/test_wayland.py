import socket
import struct
import threading
import time

import pytest

from engrama.osapi import wayland as wl

ENV = {"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000"}


def test_encode_decode_roundtrip():
    raw = wl.encode(7, 3, b"abcd") + wl.encode(9, 1)
    msgs, rest = wl.decode(raw)
    assert msgs == [(7, 3, b"abcd"), (9, 1, b"")]
    assert rest == b""


def test_decode_partial_message_kept():
    raw = wl.encode(7, 3, b"abcd") + wl.encode(9, 1, b"wxyz")
    msgs, rest = wl.decode(raw[:-2])
    assert msgs == [(7, 3, b"abcd")]
    assert rest == raw[12:-2]
    msgs, rest = wl.decode(rest + raw[-2:])
    assert msgs == [(9, 1, b"wxyz")] and rest == b""
    assert wl.decode(b"\x01\x00") == ([], b"\x01\x00")


def test_wl_string_padding():
    assert wl.wl_string("ab") == struct.pack("<I", 3) + b"ab\x00\x00"
    assert wl.wl_string("abc") == struct.pack("<I", 4) + b"abc\x00"
    assert wl.wl_string("abcd") == struct.pack("<I", 5) + b"abcd\x00\x00\x00\x00"


class FakeCompositor(threading.Thread):
    def __init__(self, sock, globals_=None, answer=True):
        super().__init__(daemon=True)
        self.sock = sock
        self.globals = globals_ if globals_ is not None else [
            (1, "wl_seat", 7), (2, "ext_idle_notifier_v1", 1)]
        self.answer = answer
        self.requests = []
        self.notif_id = None
        self.buf = b""
        self.stop = False

    def run(self):
        self.sock.settimeout(0.05)
        while not self.stop:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return
            msgs, self.buf = wl.decode(self.buf + data)
            for obj, op, pl in msgs:
                self.requests.append((obj, op, pl))
                if not self.answer:
                    continue
                if obj == 1 and op == 1:  # get_registry
                    reg = struct.unpack("<I", pl)[0]
                    for name, iface, ver in self.globals:
                        self.sock.sendall(wl.encode(
                            reg, 0, struct.pack("<I", name) + wl.wl_string(iface)
                            + struct.pack("<I", ver)))
                elif obj == 1 and op == 0:  # sync
                    cb = struct.unpack("<I", pl)[0]
                    self.sock.sendall(wl.encode(cb, 0, struct.pack("<I", 0)))
                elif op == 1 and len(pl) == 12:  # get_idle_notification
                    self.notif_id = struct.unpack("<I", pl[:4])[0]

    def send(self, data):
        self.sock.sendall(data)

    def wait_notif(self):
        for _ in range(100):
            if self.notif_id:
                return
            time.sleep(0.01)
        raise AssertionError("no get_idle_notification")


def make(globals_=None, answer=True, timeout=120.0, now=time.monotonic):
    client, server = socket.socketpair()
    comp = FakeCompositor(server, globals_, answer)
    comp.start()
    w = wl.IdleWatcher(timeout, env=ENV, connect=lambda path: client, now=now)
    return w, comp


def test_idle_watcher_full_flow():
    t = [100.0]
    w, comp = make(timeout=120.0, now=lambda: t[0])
    assert w.start() is True
    comp.wait_notif()
    assert w.idle_seconds() == 0.0
    notif = [r for r in comp.requests if r[1] == 1 and len(r[2]) == 12][0]
    nid, ms, seat = struct.unpack("<III", notif[2])
    assert ms == 120000 and nid == comp.notif_id
    t[0] = 200.0
    comp.send(wl.encode(comp.notif_id, 0))
    time.sleep(0.1)
    assert w.idle_seconds() == 120.0
    t[0] = 210.0
    assert w.idle_seconds() == 130.0
    comp.send(wl.encode(comp.notif_id, 1))
    time.sleep(0.1)
    assert w.idle_seconds() < 1
    w.close()
    comp.stop = True


def test_no_notifier_global_returns_false():
    w, comp = make(globals_=[(1, "wl_seat", 7)])
    assert w.start() is False
    assert w.idle_seconds() is None
    comp.stop = True


def test_display_error_breaks_watcher():
    w, comp = make()
    assert w.start()
    comp.wait_notif()
    msg = struct.pack("<II", 5, 1) + wl.wl_string("boom")
    comp.send(wl.encode(1, 0, msg))
    time.sleep(0.1)
    assert w.idle_seconds() is None
    assert w.idle_seconds() is None
    comp.stop = True


def test_closed_socket_returns_none():
    w, comp = make()
    assert w.start()
    comp.wait_notif()
    comp.stop = True
    time.sleep(0.15)
    comp.sock.close()
    assert w.idle_seconds() is None


def test_garbage_size_breaks_watcher():
    w, comp = make()
    assert w.start()
    comp.wait_notif()
    comp.send(struct.pack("<II", 5, (5000 << 16) | 0))
    time.sleep(0.1)
    assert w.idle_seconds() is None
    w2, comp2 = make()
    assert w2.start()
    comp2.wait_notif()
    comp2.send(struct.pack("<II", 5, (4 << 16) | 0))
    time.sleep(0.1)
    assert w2.idle_seconds() is None
    comp.stop = comp2.stop = True


def test_event_split_across_recv():
    w, comp = make(timeout=10.0)
    assert w.start()
    comp.wait_notif()
    raw = wl.encode(comp.notif_id, 0)
    comp.send(raw[:5])
    time.sleep(0.1)
    assert w.idle_seconds() == 0.0
    comp.send(raw[5:])
    time.sleep(0.1)
    assert w.idle_seconds() >= 10.0
    comp.stop = True


def test_no_wayland_display_false():
    called = []
    w = wl.IdleWatcher(60, env={}, connect=lambda p: called.append(p))
    assert w.start() is False
    assert w.idle_seconds() is None
    assert not called


@pytest.mark.perf
def test_silent_compositor_times_out():
    w, comp = make(answer=False)
    t0 = time.monotonic()
    assert w.start() is False
    assert time.monotonic() - t0 <= 1.2
    comp.stop = True


def test_connect_failure_false():
    def boom(path):
        raise OSError("nope")
    assert wl.IdleWatcher(60, env=ENV, connect=boom).start() is False


def test_socket_path():
    assert wl.socket_path(ENV) == "/run/user/1000/wayland-0"
    assert wl.socket_path({"WAYLAND_DISPLAY": "/tmp/s"}) == "/tmp/s"
    assert wl.socket_path({"WAYLAND_DISPLAY": "w"}) is None
    assert wl.socket_path({}) is None
