import types

import pytest

import engrama.services.perception.sources as S
from engrama.osapi import ActiveWindow
from engrama.osapi.session import detect
from engrama.services.perception.categories import Categorizer
from engrama.services.perception.sources import LinuxSources, NullSources, make_sources
from tests.services.perception.test_service import FakeCfg, make, run


def aw(pid=None, cls="", title="", fs=None):
    return ActiveWindow(pid=pid, cls=cls, title=title, fullscreen=fs, rect=None)


def fake_psutil(monkeypatch, names=None, exc=None):
    import psutil

    class P:
        def __init__(self, pid):
            if exc:
                raise exc(pid)
            self.pid = pid

        def name(self):
            return names[self.pid]
    monkeypatch.setattr(psutil, "Process", P)


def test_foreground_pid_name(monkeypatch):
    fake_psutil(monkeypatch, {42: "Firefox"})
    s = LinuxSources(lambda: aw(42, "navigator", "Docs"), [])
    assert s.foreground() == ("firefox", "Docs")


@pytest.mark.parametrize("generic", ["bwrap", "flatpak-bwrap"])
def test_foreground_sandbox_falls_back_to_class(monkeypatch, generic):
    fake_psutil(monkeypatch, {7: generic})
    s = LinuxSources(lambda: aw(7, "org.mozilla.firefox", "x"), [])
    assert s.foreground() == ("org.mozilla.firefox", "x")


@pytest.mark.parametrize("pid", [None, 9])
def test_foreground_dead_pid_class(monkeypatch, pid):
    import psutil
    fake_psutil(monkeypatch, exc=psutil.NoSuchProcess)
    s = LinuxSources(lambda: aw(pid, "kitty", "t"), [])
    assert s.foreground() == ("kitty", "t")
    fake_psutil(monkeypatch, exc=psutil.AccessDenied)
    assert s.foreground() == ("kitty", "t")


def test_foreground_empty_and_none():
    assert LinuxSources(lambda: aw(None, "", "t"), []).foreground() is None
    assert LinuxSources(lambda: None, []).foreground() is None
    assert LinuxSources(None, []).foreground() is None


def test_fullscreen_passthrough():
    for v in (True, False, None):
        assert LinuxSources(lambda v=v: aw(1, "x", "", v), []).is_fullscreen() is v
    assert LinuxSources(None, []).is_fullscreen() is None


def test_idle_chain_first_wins():
    calls = []

    def mk(tag, v):
        def f():
            calls.append(tag)
            return v
        return f
    s = LinuxSources(None, [mk("a", None), mk("b", 3.5), mk("c", 9.0)])
    assert s.idle_seconds() == 3.5
    assert calls == ["a", "b"]
    assert LinuxSources(None, []).idle_seconds() is None


def test_idle_backend_disabled_then_retried():
    t = [0.0]
    n = {"a": 0, "b": 0}

    def a():
        n["a"] += 1
        return None

    def b():
        n["b"] += 1
        return 1.0
    s = LinuxSources(None, [a, b], now=lambda: t[0])
    assert s.idle_seconds() == 1.0 and n == {"a": 1, "b": 1}
    t[0] = 59.0
    s.idle_seconds()
    assert n["a"] == 1
    t[0] = 61.0
    s.idle_seconds()
    assert n["a"] == 2


def test_backend_exceptions_harmless(monkeypatch):
    def boom():
        raise RuntimeError("x")
    s = LinuxSources(lambda: 1 / 0, [boom, lambda: 2.0])
    assert s.idle_seconds() == 2.0
    assert s.foreground() is None and s.is_fullscreen() is None
    import psutil
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 1 / 0)
    assert s.cpu_percent() is None
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 12)
    assert s.cpu_percent() == 12.0


class Marker:
    pass


def test_make_sources_windows_unchanged(monkeypatch):
    monkeypatch.setattr(S, "WinSources", Marker)
    assert isinstance(make_sources(env={}, platform="win32"), Marker)


def _no_backends(monkeypatch):
    monkeypatch.setattr(S.X11, "open", classmethod(lambda cls, *a, **k: None))


def test_make_sources_hyprland_picks_ipc(monkeypatch):
    _no_backends(monkeypatch)
    seen = []
    monkeypatch.setattr(S.hyprland, "active_window", lambda env=None: seen.append(env) or aw(None, "kitty", "t", True))
    env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-1",
           "HYPRLAND_INSTANCE_SIGNATURE": "sig"}
    src = make_sources(env=env, platform="linux")
    assert isinstance(src, LinuxSources)
    assert src.foreground() == ("kitty", "t") and src.is_fullscreen() is True
    assert seen and seen[0] == env


def test_make_sources_sway_picks_ipc(monkeypatch):
    _no_backends(monkeypatch)
    monkeypatch.setattr(S.sway, "active_window", lambda env=None: aw(None, "foot", "t"))
    env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "SWAYSOCK": "/x"}
    assert make_sources(env=env, platform="linux").foreground() == ("foot", "t")


def test_make_sources_wayland_never_x11(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("X11 opened on Wayland")
    monkeypatch.setattr(S.X11, "open", classmethod(boom))
    env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "DISPLAY": ":0",
           "XDG_CURRENT_DESKTOP": "GNOME"}
    src = make_sources(env=env, platform="linux")
    assert isinstance(src, LinuxSources)
    assert src.foreground() is None and src.is_fullscreen() is None


def test_make_sources_x11_uses_x11(monkeypatch):
    class FakeX:
        def active(self):
            return aw(None, "code", "t", False)

        def idle_ms(self):
            return 4000
    monkeypatch.setattr(S.X11, "open", classmethod(lambda cls, *a, **k: FakeX()))
    src = make_sources(env={"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}, platform="linux")
    assert src.foreground() == ("code", "t") and src.idle_seconds() == 4.0


def test_make_sources_x11_dbus_fallback(monkeypatch):
    _no_backends(monkeypatch)
    monkeypatch.setattr(S.dbus_idle, "idle_ms", lambda: 7000)
    src = make_sources(env={"DISPLAY": ":0"}, platform="linux")
    assert src.idle_seconds() == 7.0


def test_make_sources_tty_null():
    assert isinstance(make_sources(env={}, platform="linux"), NullSources)


def test_make_sources_dummy_video_null():
    env = {"SDL_VIDEODRIVER": "dummy", "DISPLAY": ":0"}
    assert isinstance(make_sources(env=env, platform="linux"), NullSources)


def test_make_sources_darwin_null():
    assert isinstance(make_sources(env={"DISPLAY": ":0"}, platform="darwin"), NullSources)


def test_wayland_idle_watcher_lazy(monkeypatch):
    started = []

    class W:
        def __init__(self, timeout, env=None):
            started.append(timeout)

        def start(self):
            return True

        def idle_seconds(self):
            return 130.0

        def close(self):
            pass
    monkeypatch.setattr(S, "IdleWatcher", W)
    monkeypatch.setattr(S.dbus_idle, "idle_ms", lambda: None)
    env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w"}
    src = S.build_linux_sources(detect(env, "linux"))
    assert started == []
    assert src.idle_seconds() == 130.0 and started == [S.IDLE_AFTER_S]


def test_permission_order_with_linux_sources():
    calls = {"w": 0, "i": 0}

    def win():
        calls["w"] += 1
        return aw(None, "code", "main.py")

    def idle():
        calls["i"] += 1
        return 1.0
    src = LinuxSources(win, [idle])
    svc, posts, _, _ = make(FakeCfg(), src)
    run(svc, secs=100)
    assert calls == {"w": 0, "i": 0} and posts == []
    calls.update(w=0, i=0)
    themes = []
    blocked = LinuxSources(lambda: aw(None, "bradesco", "Internet Banking"), [idle])
    svc, posts, _, _ = make(FakeCfg(process=True, active_window=True), blocked,
                            on_theme=lambda *a: themes.append(a))
    run(svc, secs=100)
    assert posts == [("app_focus", {"category": "privado"})]
    assert themes == []
