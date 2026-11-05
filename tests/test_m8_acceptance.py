"""M8 acceptance (spec section 7): Linux support with fake sessions, sockets and backends.

Criteria 1 (suite on the reference machine) and 16 (manual smoke on Hyprland/X11) are not automated here:
1 is `python -m pytest -q` including the two budget tests, 16 is the manual checklist in the plan.
Criteria 6-9 (Sway, Wayland idle, DBus idle, X11 API) are covered by tests/osapi/*; this file adds the end-to-end
wiring on top of them."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import engrama.services.perception.sources as S
from engrama import vocab
from engrama.app.desktop import FakeDesktop, NullDesktop, get_desktop
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window
from engrama.clock import SimClock
from engrama.config import Config
from engrama.osapi import hyprland
from engrama.osapi.session import Session, detect
from engrama.osapi.x11 import LOCK_VARIANTS, X11KeyGrab
from engrama.services.perception import IDLE_AFTER_S, PRIVATE
from engrama.services.perception.categories import table_category
from engrama.services.perception.hotkey import GlobalHotkey
from engrama.services.perception.service import PerceptionService
from engrama.services.perception.sources import LinuxSources, make_sources

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "engrama" / "recipes" / "minimal-v1.toml"
FIXTURE = ROOT / "tests" / "fixtures" / "m6_sim_1d_seed1_attentive.json"
ENV = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
SECRET = "Plano Secreto do Projeto Zeta 123"
HYPR_ENV = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-1", "HYPRLAND_INSTANCE_SIGNATURE": "sig",
            "XDG_RUNTIME_DIR": "/x"}


class FakeTime:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


class _Conn:
    """A Hyprland socket that answers j/activewindow with fixed bytes."""
    def __init__(self, reply):
        self.reply, self.sent = reply, b""

    def settimeout(self, t): pass
    def connect(self, p): pass
    def sendall(self, b): self.sent += b
    def close(self): pass

    def recv(self, n):
        r, self.reply = self.reply[:n], self.reply[n:]
        return r


class FakeIdle:
    """Stands in for the Wayland IdleWatcher."""
    value = 0.0
    closed = 0

    def __init__(self, *a, **k): pass
    def start(self): return True
    def idle_seconds(self): return FakeIdle.value
    def close(self): FakeIdle.closed += 1


class BoomIdle(FakeIdle):
    def start(self): raise RuntimeError("x")


_REAL_HYPR = hyprland.active_window


class FakeHypr:
    def __init__(self):
        self.win = {"pid": 4242, "class": "code", "title": SECRET, "at": [0, 0], "size": [10, 10], "fullscreen": 0}
        self.calls = 0

    def __call__(self, env=None):
        self.calls += 1
        return _REAL_HYPR(env, connect=lambda p: _Conn(json.dumps(self.win).encode()))


def _hypr_sources(monkeypatch, name="code", idle=FakeIdle):
    import psutil

    class P:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            return name
    monkeypatch.setattr(psutil, "Process", P)
    monkeypatch.setattr(S.X11, "open", classmethod(lambda cls, *a, **k: None))
    monkeypatch.setattr(S, "IdleWatcher", idle)
    monkeypatch.setattr(S.dbus_idle, "idle_ms", lambda *a, **k: None)
    hypr = FakeHypr()
    monkeypatch.setattr(S.hyprland, "active_window", hypr)
    src = make_sources(env=HYPR_ENV, platform="linux")
    assert isinstance(src, LinuxSources)
    return src, hypr


def _cfg(tmp, *perms, blocklist=()):
    cfg = Config(data_dir=tmp)
    cfg.perception_asked = True
    cfg.perception_interval_s = 15.0
    cfg.perception_blocklist = list(blocklist)
    for p in perms:
        cfg.permissions[p] = True
    return cfg


def _host(tmp, cfg, ft):
    from engrama.app.host import Host
    return Host(cfg, tmp, MINIMAL, seed=7, clock=SimClock(1.0, now_fn=ft), ram_free_mb_fn=lambda: 8000.0)


def _blob(tmp) -> bytes:
    out = b""
    for p in sorted(tmp.rglob("*")):
        if p.is_file() and p.name != "config.json":
            out += p.read_bytes()
    return out


def _run(svc, ft, host, secs=300, step=5.0):
    end = ft.t + secs
    while ft.t < end:
        svc.tick(ft.t)
        host.pump(1)
        ft.tick(step)


class _Proc:
    def terminate(self): pass
    def wait(self, timeout=None): return 0


def _ping_after_start():
    state = {"up": False}

    def ping(url, timeout):
        up, state["up"] = state["up"], True
        return up
    return ping


# 2 -------------------------------------------------------------------------------------------------------
def test_windows_choices_unchanged(monkeypatch, tmp_path):
    from engrama.app import desktop as dk
    from engrama.services.language import server as server_mod
    from engrama.services.language.server import OllamaServer
    from engrama.services.perception import hotkey as hk

    class Marker:
        pass

    monkeypatch.setattr(sys, "platform", "win32")
    cfg = Config()
    assert str(cfg.ollama_exe) == r"E:\Ollama\ollama.exe"
    assert cfg.ollama_home == Path(r"E:\Ollama\home") and cfg.ollama_models == Path(r"E:\Ollama\models")
    monkeypatch.setattr(server_mod.sys, "platform", "win32")
    seen = {}
    exe = tmp_path / "ollama.exe"
    exe.write_text("x")
    c2 = Config(data_dir=tmp_path, ollama_exe=exe, ollama_home=Path(r"E:\Ollama\home"),
                ollama_models=Path(r"E:\Ollama\models"))

    def popen(cmd, **kw):
        seen.update(cmd=cmd, kw=kw)
        return _Proc()
    assert OllamaServer(c2, popen=popen, ping=_ping_after_start()).start() is True
    assert seen["kw"]["creationflags"] & 0x08000000
    assert seen["kw"]["env"]["OLLAMA_MODELS"] == r"E:\Ollama\models"
    assert seen["kw"]["env"]["HOME"] == seen["kw"]["env"]["USERPROFILE"] == r"E:\Ollama\home"
    monkeypatch.setattr(S, "WinSources", Marker)
    assert isinstance(make_sources(env={}, platform="win32"), Marker)
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    monkeypatch.setattr(dk, "WinDesktop", Marker)
    monkeypatch.setattr(dk.sys, "platform", "win32")
    assert isinstance(get_desktop(), Marker)
    monkeypatch.setattr(hk, "_WinApi", Marker)
    g = GlobalHotkey("ctrl+alt+e", lambda: None, session=Session("win32", "none", "", {}))
    g.start()
    g.stop()
    assert isinstance(g._api, Marker)


# 3, 4 ----------------------------------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform == "win32", reason="simula Linux: caminhos POSIX")
def test_linux_config_and_ollama(tmp_path, monkeypatch):
    from engrama import config as config_mod
    from engrama.app.i18n import _ui_locale_name
    from engrama.services.language import server as server_mod
    from engrama.services.language.server import OllamaServer

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(config_mod.shutil, "which", lambda n: "/usr/bin/ollama")
    p = tmp_path / "config.json"
    cfg = Config.load(p)
    assert "E:" not in p.read_text(encoding="utf-8")
    assert cfg.ollama_home is None and cfg.ollama_models is None
    p.write_text(json.dumps({"ollama_exe": "E:\\Ollama\\ollama.exe"}), encoding="utf-8")
    assert str(Config.load(p).ollama_exe) == "/usr/bin/ollama"
    monkeypatch.setattr(server_mod.sys, "platform", "linux")
    seen = {}

    def popen(cmd, **kw):
        seen.update(cmd=cmd, kw=kw)
        return _Proc()
    exe = tmp_path / "ollama"
    exe.write_text("x")
    c = Config(data_dir=tmp_path, ollama_exe=exe, ollama_home=None, ollama_models=None)
    assert OllamaServer(c, popen=popen, ping=_ping_after_start()).start() is True
    assert "creationflags" not in seen["kw"]
    env = seen["kw"].get("env")
    assert env is None or env.get("HOME") == os.environ.get("HOME")
    # criterion 4: UI language from the environment
    assert _ui_locale_name({"LANG": "pt_BR.UTF-8"}, "linux").startswith("pt")
    assert _ui_locale_name({"LANGUAGE": "en_US:pt_BR", "LANG": "pt_BR.UTF-8"}, "linux").startswith("en")
    assert _ui_locale_name({"LANG": "C"}, "linux") == ""


# 5, 10 ---------------------------------------------------------------------------------------------------
def test_hyprland_perception_end_to_end(tmp_path, monkeypatch):
    from engrama.services.memory.store import MemoryStore
    from engrama.services.perception.themes import make_theme_sink

    ft = FakeTime()
    cfg = _cfg(tmp_path, "process", "active_window", "idle", "system_load")
    host = _host(tmp_path, cfg, ft)
    mem = MemoryStore(tmp_path / "memory.sqlite", now_fn=ft)
    FakeIdle.value = 0.0
    src, hypr = _hypr_sources(monkeypatch)
    posts = []

    def rec(kind, data=None):
        posts.append((kind, dict(data or {})))
        host.post(kind, data)
    svc = PerceptionService(rec, src, lambda: cfg, lambda: False, now_fn=ft, on_theme=make_theme_sink(mem, ft))
    _run(svc, ft, host, 120)
    assert ("app_focus", {"category": "programacao"}) in posts
    assert not any(k == "fullscreen_on" for k, _ in posts)
    hypr.win["fullscreen"] = 2
    _run(svc, ft, host, 120)
    assert any(k == "fullscreen_on" for k, _ in posts)
    FakeIdle.value = float(IDLE_AFTER_S) + 5
    _run(svc, ft, host, 120)
    assert any(k == "user_idle" for k, _ in posts)
    snap_repr = repr(host.snapshot())
    host._save()
    host.stop()
    mem.close()
    blob = _blob(tmp_path).lower()
    assert SECRET.lower() not in snap_repr.lower()
    assert SECRET.lower().encode() not in blob and b"secreto" not in blob
    assert not any("secreto" in repr(d).lower() for _, d in posts)


def test_blocked_app_linux_never_leaks(tmp_path, monkeypatch):
    ft = FakeTime()
    cfg = _cfg(tmp_path, "process", "active_window", "idle", "system_load", blocklist=["firefox"])
    host = _host(tmp_path, cfg, ft)
    src, hypr = _hypr_sources(monkeypatch, name="firefox")
    hypr.win["class"] = "firefox"
    posts = []

    def rec(kind, data=None):
        posts.append((kind, dict(data or {})))
        host.post(kind, data)
    svc = PerceptionService(rec, src, lambda: cfg, lambda: False, now_fn=ft)
    _run(svc, ft, host, 300)
    assert ("app_focus", {"category": PRIVATE}) in posts
    snap_repr = repr(host.snapshot())
    host._save()
    host.stop()
    blob = _blob(tmp_path).lower()
    for s in (SECRET, "projeto zeta", "firefox"):
        assert s.lower().encode() not in blob and s.lower() not in snap_repr.lower(), s
        assert not any(s.lower() in repr(d).lower() for _, d in posts), s


def test_eyes_closed_and_missing_permission_never_read_on_linux(tmp_path, monkeypatch):
    ft = FakeTime()
    cfg = _cfg(tmp_path, "idle")                         # only idle is allowed
    host = _host(tmp_path, cfg, ft)
    src, hypr = _hypr_sources(monkeypatch)
    svc = PerceptionService(lambda k, d=None: None, src, lambda: cfg, lambda: False, now_fn=ft)
    _run(svc, ft, host, 300)
    assert hypr.calls == 0                               # window source never read without permission
    cfg2 = _cfg(tmp_path, "process", "active_window", "idle", "system_load")
    svc2 = PerceptionService(lambda k, d=None: None, src, lambda: cfg2, lambda: True, now_fn=ft)
    _run(svc2, ft, host, 300)
    assert hypr.calls == 0                               # eyes closed: nothing read at all
    host.stop()


# 14 ------------------------------------------------------------------------------------------------------
def test_all_backends_failing_harmless(tmp_path, monkeypatch):
    ft = FakeTime()
    cfg = _cfg(tmp_path, "process", "active_window", "idle", "system_load")
    host = _host(tmp_path, cfg, ft)

    def boom(*a, **k):
        raise RuntimeError("backend down")
    src, _ = _hypr_sources(monkeypatch, idle=BoomIdle)
    monkeypatch.setattr(S.hyprland, "active_window", boom)
    monkeypatch.setattr(S.dbus_idle, "idle_ms", boom)
    svc = PerceptionService(lambda k, d=None: None, src, lambda: cfg, lambda: False, now_fn=ft)
    _run(svc, ft, host, 300)
    assert src.foreground() is None and src.is_fullscreen() is None and src.idle_seconds() is None
    host.stop()
    good = LinuxSources(boom, [boom, lambda: 4.0])   # a failing window backend leaves the idle chain alone
    assert good.idle_seconds() == 4.0 and good.foreground() is None


# 11 ------------------------------------------------------------------------------------------------------
def test_linux_categories():
    assert table_category("firefox") == "navegador"
    assert table_category("code") == "programacao"
    assert table_category("kitty") == "terminal"
    assert table_category("hollow_knight.x86_64") == "jogo"
    assert table_category("HollowKnight.exe") == "jogo"
    assert table_category("spotify") == "musica"
    assert table_category("chrome.exe") == "navegador" and table_category("code.exe") == "programacao"
    from engrama.services.perception.themes import extract_theme
    assert extract_theme("spotify", "Artista - Faixa", "musica")


# 12 ------------------------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="SIGUSR1")
def test_eyes_command_end_to_end(tmp_path):
    r = subprocess.run([sys.executable, "-m", "engrama", "--eyes", "toggle", "--data-dir", str(tmp_path / "none")],
                       env=ENV, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and r.stderr.strip()
    d = tmp_path / "d"
    app = subprocess.Popen([sys.executable, "-m", "engrama", "--no-llm", "--seconds", "8", "--data-dir", str(d)],
                           env=ENV)
    try:
        from engrama.app.instance import InstanceLock
        t0 = time.monotonic()
        while InstanceLock.holder_pid(d) is None and time.monotonic() - t0 < 30:
            time.sleep(0.1)
        time.sleep(2.0)
        r = subprocess.run([sys.executable, "-m", "engrama", "--eyes", "toggle", "--data-dir", str(d)],
                           env=ENV, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0
        app.wait(timeout=60)
    finally:
        if app.poll() is None:
            app.kill()
    assert json.loads((d / "config.json").read_text())["eyes_closed"] is True


def test_eyes_windows_exit_code_and_x11_lock_variants(tmp_path, monkeypatch, capsys):
    from engrama.app import instance
    monkeypatch.setattr(instance.sys, "platform", "win32")
    assert instance.send_eyes_toggle(tmp_path) == 2
    assert capsys.readouterr().out.strip()
    assert len(LOCK_VARIANTS) == 4          # none, NumLock, CapsLock, both

    class FakeXLib:
        def __init__(self): self.grabs = []
        def XKeysymToKeycode(self, dpy, ks): return 26
        def XGrabKey(self, dpy, code, mods, root, *a): self.grabs.append(mods)
        def XSync(self, *a): pass
        def XDefaultRootWindow(self, dpy): return 1
        def XConnectionNumber(self, dpy): return 3

    x = FakeXLib()
    kg = X11KeyGrab(x, object(), 0, 0)
    assert kg.grab(0x4, 0x65) is True
    assert sorted(x.grabs) == sorted(0x4 | v for v in LOCK_VARIANTS)


# 13 ------------------------------------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform == "win32", reason="simula Linux: get_desktop usa a plataforma real")
def test_overlay_wayland_notice_and_x11_fake(monkeypatch):
    from engrama.app import desktop as dk
    from engrama.app import i18n
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    monkeypatch.setattr(dk, "detect", lambda: Session("linux", "wayland", "hyprland", {}))
    d = get_desktop()
    assert isinstance(d, NullDesktop) and d.unavailable_reason == "wayland"
    cfg = Config()
    cfg.perception_asked = True
    w = Window(lambda: Snapshot(look={"seed": 3}, stage="adult"), lambda k, dd=None: None)
    w.desktop, w.config, w.save_config = d, cfg, lambda: None
    assert w.set_mode("overlay") is False and w.mode == "terrarium"
    assert w._notice[0] == i18n.t("ui.overlay.unavailable_wayland")
    w2 = Window(lambda: Snapshot(look={"seed": 3}, stage="adult"), lambda k, dd=None: None)
    w2.desktop, w2.config, w2.save_config = FakeDesktop(work=(0, 0, 1280, 680)), cfg, lambda: None
    assert w2.set_mode("overlay") is True and w2.mode == "overlay"
    w2.frame(1.0)
    g = GlobalHotkey("ctrl+alt+e", lambda: None, session=Session("linux", "wayland", "hyprland", {}))
    assert g.start() is False and g.error == "wayland"   # the panel turns this raw code into the command hint
    g = GlobalHotkey("ctrl+alt+e", lambda: None, session=Session("linux", "none", "", {}))
    assert g.start() is False and g.error == "unsupported"


def test_x11desktop_and_strange_sessions_are_inert():
    from engrama.app import desktop as dk
    from tests.app.test_desktop import FakeWin, FakeX
    fx, win = FakeX(), FakeWin()
    d = dk.X11Desktop(fx, window=lambda: win)
    assert d.make_overlay(1) is True and win.always_on_top
    d.restore(1)
    assert not win.always_on_top
    for env in ({}, {"XDG_SESSION_TYPE": "tty"}, {"SDL_VIDEODRIVER": "dummy", "DISPLAY": ":0"}):
        assert detect(env, "linux").kind == "none"
        assert isinstance(make_sources(env=env, platform="linux"), S.NullSources)
    assert detect({"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}, "linux").kind == "wayland"   # never X11


# 15 ------------------------------------------------------------------------------------------------------
@pytest.mark.slow
def test_lab_identical_to_m7(capsys):
    from engrama.lab.cli import main as lab_main
    assert lab_main(["sim", "--recipe", str(ROOT / "engrama" / "recipes" / "default-v1.toml"), "--days", "1", "--seed", "1",
                     "--profile", "attentive"]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_vocab_frozen():
    assert vocab.DIGITAL_IDS == ("ram", "defrag", "update", "cache", "cooler")
    assert vocab.VARIANTS == ("jump", "dance", "yawn", "nap_clock", "chase", "look_cursor", "peek", "dig", "found")
    assert vocab.DISPLAY_MODES == ("terrarium", "overlay")


# wiring --------------------------------------------------------------------------------------------------
def test_sources_close_closes_wayland_connection(monkeypatch):
    FakeIdle.closed = 0
    src, _ = _hypr_sources(monkeypatch)
    assert src.idle_seconds() is not None
    src.close()
    assert FakeIdle.closed >= 1


@pytest.mark.slow
def test_smoke_frames(tmp_path):
    r = subprocess.run([sys.executable, "-m", "engrama", "--frames", "120", "--no-llm", "--data-dir",
                        str(tmp_path / "smoke")], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-500:]
