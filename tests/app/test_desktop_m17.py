"""M17: window geometry per platform, the Hyprland desktop and the GL presenter (all with fakes)."""
import sys
import pygame
import pytest

from engrama.app import desktop as dk
from engrama.app import glpresent
from engrama.osapi import ActiveWindow
from engrama.osapi.session import Session


def test_filter_win_windows_skips_cloaked_minimized_tool_and_shell():
    ents = [{"rect": (0, 0, 800, 600), "cls": "Notepad"},
            {"rect": (0, 0, 800, 600), "cls": "x", "cloaked": True},
            {"rect": (0, 0, 800, 600), "cls": "x", "minimized": True},
            {"rect": (0, 0, 800, 600), "cls": "x", "toolwindow": True},
            {"rect": (0, 0, 1920, 40), "cls": "Shell_TrayWnd"},
            {"rect": (-32000, -32000, 160, 28), "cls": "x"},
            {"rect": (5, 5, 10, 10), "cls": "x"},
            {"rect": None, "cls": "x"}, {}]
    assert dk.filter_win_windows(ents) == [(0, 0, 800, 600)]


class FakeX:
    def windows(self, pid):
        self.pid = pid
        return [(1, 2, 300, 200)]


def test_x11desktop_windows_delegates_and_never_raises():
    d = dk.X11Desktop(FakeX(), window=lambda: None)
    assert d.windows() == [(1, 2, 300, 200)]

    class Broken:
        def windows(self, pid):
            raise RuntimeError

    assert dk.X11Desktop(Broken(), window=lambda: None).windows() == []


class FakeIpc:
    def __init__(self):
        self.moved, self.rules, self.area = [], 0, (60, 10, 1850, 1060)

    def work_area(self, env=None):
        return self.area

    def cursor_pos(self, env=None):
        return (5, 6)

    def active_window(self, env=None):
        return ActiveWindow(pid=1, cls="firefox", title="t", fullscreen=False, rect=(1, 2, 3, 4))

    def windows(self, env=None, own_pid=None, own_class=""):
        return [(9, 9, 99, 99)]

    def apply_overlay_rules(self, cls, env=None):
        self.rules += 1
        return True

    def move_window(self, cls, x, y, env=None):
        self.moved.append((x, y))
        return True


def hypr(clock=None):
    d = dk.HyprlandDesktop(clock=clock or (lambda: 0.0))
    d._ipc = FakeIpc()
    return d


def test_hyprland_desktop_reads_the_compositor():
    d = hypr()
    assert d.available and not d.click_through and d.offscreen and d.display_flags == pygame.OPENGL
    assert d.work_area() == (60, 10, 1850, 1060) and d.cursor() == (5, 6)
    assert d.foreground_rect() == (1, 2, 3, 4) and d.windows() == [(9, 9, 99, 99)]


def test_hyprland_work_area_is_cached_for_a_second():
    t = [0.0]
    d = hypr(lambda: t[0])
    d.work_area()
    d._ipc.area = (0, 0, 10, 10)
    assert d.work_area() == (60, 10, 1850, 1060)
    t[0] = 2.0
    assert d.work_area() == (0, 0, 10, 10)


def test_hyprland_place_moves_only_on_change_throttled_and_retries_failures():
    t = [0.0]
    d = hypr(lambda: t[0])
    d.place(0, (10, 20, 100, 50))
    d.place(0, (10, 20, 120, 60))        # same position, new size: no move
    t[0] = 1.0
    d.place(0, (11, 20, 100, 50))
    d.place(0, (12, 20, 100, 50))        # too soon: held back
    assert d._ipc.moved == [(10, 20), (11, 20)]
    t[0] = 1.2
    d.cursor()                           # the next poll flushes the last position
    assert d._ipc.moved[-1] == (12, 20) and d._pending is None
    d._ipc.move_window = lambda *a, **k: False
    t[0] = 3.0
    d.place(0, (50, 50, 1, 1))
    assert d._last[:2] == (12, 20)       # a failed move is not remembered


def test_hyprland_prepare_installs_rules_once_and_sets_env(monkeypatch):
    monkeypatch.setattr(dk.HyprlandDesktop, "_recreate_display", staticmethod(lambda: None))
    monkeypatch.delenv("SDL_VIDEO_WAYLAND_WMCLASS", raising=False)
    d = hypr()
    d.prepare_window()
    d.prepare_window()
    assert d._ipc.rules == 1
    import os
    assert os.environ["SDL_VIDEO_WAYLAND_WMCLASS"] == dk.OVERLAY_CLASS
    assert os.environ["SDL_VIDEO_EGL_ALLOW_TRANSPARENCY"] == "1"
    d.restore(0)
    assert "SDL_VIDEO_WAYLAND_WMCLASS" not in os.environ


def test_get_desktop_hyprland_native_wayland(monkeypatch):
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    monkeypatch.setattr(dk.sys, "platform", "linux")
    monkeypatch.setattr(dk, "detect", lambda: Session("linux", "wayland", "hyprland", {}))
    monkeypatch.setattr(pygame.display, "get_driver", lambda: "wayland")
    assert isinstance(dk.get_desktop(), dk.HyprlandDesktop)
    monkeypatch.setattr(pygame.display, "get_driver", lambda: "x11")      # XWayland ignores the window shape
    assert isinstance(dk.get_desktop(), dk.NullDesktop)
    monkeypatch.setattr(dk, "detect", lambda: Session("linux", "wayland", "sway", {}))
    monkeypatch.setattr(pygame.display, "get_driver", lambda: "wayland")
    assert dk.get_desktop().unavailable_reason == "wayland"


@pytest.mark.skipif(sys.platform == "win32", reason="Hyprland/Wayland driver choice is Linux-only; returns False on Windows")
def test_prefer_wayland_on_hyprland():
    hypr_env = {"XDG_SESSION_TYPE": "wayland", "HYPRLAND_INSTANCE_SIGNATURE": "x"}
    env = dict(hypr_env)
    assert dk.prefer_wayland_on_hyprland(env) is True and env["SDL_VIDEODRIVER"] == "wayland"
    chosen = dict(hypr_env, SDL_VIDEODRIVER="x11")
    assert dk.prefer_wayland_on_hyprland(chosen) is False and chosen["SDL_VIDEODRIVER"] == "x11"
    sway = {"XDG_SESSION_TYPE": "wayland", "SWAYSOCK": "x"}
    assert dk.prefer_wayland_on_hyprland(sway) is False and "SDL_VIDEODRIVER" not in sway


# ------------------------------------------------------------------ GL presenter
def test_rgba_bytes_turns_the_colour_key_into_transparent_pixels():
    s = pygame.Surface((2, 2))
    s.fill(dk.COLORKEY)
    s.set_at((0, 0), (10, 20, 30))
    data = glpresent.rgba_bytes(s, dk.COLORKEY)
    px = [tuple(data[i:i + 4]) for i in range(0, 16, 4)]
    assert (10, 20, 30, 255) in px and px.count((0, 0, 0, 0)) == 3
    assert px[2] == (10, 20, 30, 255)             # row 0 is the last one: GL's origin is the bottom-left corner


class FakeGL:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def f(*a):
            self.calls.append(name)
            if name == "glGenTextures":
                a[1]._obj.value = 7
        return f


def test_presenter_uploads_a_texture_and_draws_a_quad():
    gl = FakeGL()
    p = glpresent.GLPresenter(dk.COLORKEY, gl=gl)
    assert p.ok
    s = pygame.Surface((4, 4))
    p.present(s)
    p.present(s)
    assert gl.calls.count("glGenTextures") == 1 and gl.calls.count("glTexImage2D") == 1
    assert gl.calls.count("glTexSubImage2D") == 1
    assert gl.calls.count("glVertex2f") == 8
    p.reset()
    p.present(s)
    assert gl.calls.count("glGenTextures") == 2


def test_presenter_without_gl_is_inert():
    p = glpresent.GLPresenter(dk.COLORKEY, gl=None)
    p.gl = None
    assert not p.ok
    p.present(pygame.Surface((2, 2)))


def test_load_gl_failure_returns_none():
    assert glpresent.load_gl(find=lambda n: None, cdll=lambda n: (_ for _ in ()).throw(OSError)) is None


@pytest.mark.parametrize("cls", [dk.NullDesktop, dk.FakeDesktop])
def test_base_desktops_have_inert_new_hooks(cls):
    d = cls()
    d.prepare_window()
    d.present(pygame.Surface((1, 1)))
    assert d.click_through and not d.offscreen and d.display_flags == 0
