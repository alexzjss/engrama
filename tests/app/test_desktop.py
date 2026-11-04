import sys

import pytest

from engrama.app.desktop import COLORKEY, FakeDesktop, NullDesktop, get_desktop


def test_null_is_inert_and_never_raises():
    d = NullDesktop()
    assert d.available is False
    assert d.work_area() == (0, 0, 1280, 720)
    assert d.cursor() is None
    assert d.foreground_rect() is None
    assert d.make_overlay(123) is False
    d.place(1, (0, 0, 10, 10))
    d.show(1, True)
    d.restore(1)


def test_fake_place_only_records_on_change():
    d = FakeDesktop()
    d.place(1, (0, 0, 10, 10))
    d.place(1, (0, 0, 10, 10))
    d.place(1, (5, 0, 10, 10))
    assert [c for c in d.calls if c[0] == "place"] == [("place", 1, (0, 0, 10, 10)), ("place", 1, (5, 0, 10, 10))]
    d.work, d.cur, d.fg = (0, 0, 800, 600), (3, 4), (1, 2, 3, 4)
    assert (d.work_area(), d.cursor(), d.foreground_rect()) == ((0, 0, 800, 600), (3, 4), (1, 2, 3, 4))
    assert d.make_overlay(1) is True and d.available


def test_get_desktop_dummy_driver_is_null(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    assert isinstance(get_desktop(), NullDesktop)


def test_colorkey():
    assert COLORKEY == (255, 0, 255)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_win_desktop_work_area_and_overlay_safe():
    from engrama.app.desktop import WinDesktop

    d = WinDesktop()
    x, y, w, h = d.work_area()
    assert all(isinstance(v, int) for v in (x, y, w, h)) and w > 0 and h > 0
    assert d.make_overlay(0) is False
    d.restore(0)
    d.place(0, (0, 0, 10, 10))
    d.show(0, False)


# ------------------------------------------------------------------ M8: X11 / Wayland
import pygame  # noqa: E402

from engrama.app import desktop as dk  # noqa: E402
from engrama.osapi import ActiveWindow  # noqa: E402
from engrama.osapi.session import Session  # noqa: E402


def _session(kind, platform="linux"):
    return Session(platform=platform, kind=kind, compositor="other", env={})


def test_get_desktop_windows_unchanged(monkeypatch):
    class Sentinel(dk.Desktop):
        available = True

    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    monkeypatch.setattr(dk.sys, "platform", "win32")
    monkeypatch.setattr(dk, "WinDesktop", Sentinel)
    assert isinstance(get_desktop(), Sentinel)


def test_get_desktop_wayland_null_with_reason(monkeypatch):
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    monkeypatch.setattr(dk.sys, "platform", "linux")
    monkeypatch.setattr(dk, "detect", lambda: _session("wayland"))
    d = get_desktop()
    assert isinstance(d, NullDesktop) and d.unavailable_reason == "wayland" and not d.available


def test_get_desktop_dummy_unsupported(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    d = get_desktop()
    assert isinstance(d, NullDesktop) and d.unavailable_reason == "unsupported"


def test_get_desktop_x11_and_fallbacks(monkeypatch):
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    monkeypatch.setattr(dk.sys, "platform", "linux")
    monkeypatch.setattr(dk, "detect", lambda: _session("x11"))
    monkeypatch.setattr(pygame.display, "get_driver", lambda: "x11")
    fx = FakeX()
    monkeypatch.setattr(dk.X11, "open", classmethod(lambda cls, display=None: fx))
    assert isinstance(get_desktop(), dk.X11Desktop)
    monkeypatch.setattr(dk.X11, "open", classmethod(lambda cls, display=None: None))
    assert get_desktop().unavailable_reason == "unsupported"
    monkeypatch.setattr(pygame.display, "get_driver", lambda: "wayland")
    assert get_desktop().unavailable_reason == "unsupported"


class FakeX:
    def __init__(self):
        self.states, self.shapes = [], []
        self.area = (0, 24, 1000, 700)
        self.act = None

    def work_area(self):
        return self.area

    def screen_size(self):
        return (1920, 1080)

    def pointer(self):
        return (5, 6)

    def active(self):
        return self.act

    def set_state(self, win, atom, on):
        self.states.append((win, atom, on))
        return True

    def set_shape(self, win, mask, w, h):
        self.shapes.append((win, mask, w, h))
        return True


class FakeWin:
    def __init__(self):
        self.always_on_top = False
        self.position = (0, 0)
        self.size = (10, 10)
        self.shown = []

    def show(self):
        self.shown.append(True)

    def hide(self):
        self.shown.append(False)


def test_x11desktop_with_fake_x():
    fx, win = FakeX(), FakeWin()
    d = dk.X11Desktop(fx, window=lambda: win)
    assert d.available and d.work_area() == (0, 24, 1000, 700) and d.cursor() == (5, 6)
    assert d.make_overlay(42) is True and win.always_on_top
    on = {a for (_, a, o) in fx.states if o}
    assert on == {"_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER", "_NET_WM_STATE_STICKY"}
    d.place(42, (10, 20, 100, 50))
    assert win.position == (10, 20) and win.size == (100, 50)
    win.position = (99, 99)
    d.place(42, (10, 20, 100, 50))   # unchanged rect: nothing resent
    assert win.position == (99, 99)
    d.show(42, False)
    d.show(42, True)
    assert win.shown == [False, True]
    d.update_shape(42, _shape_surface())
    assert len(fx.shapes) == 1
    d.restore(42)
    assert fx.shapes[-1][1] is None and not win.always_on_top
    off = {a for (_, a, o) in fx.states if not o}
    assert off == on
    d.place(42, (10, 20, 100, 50))
    assert win.position == (10, 20)   # cache forgotten


def test_x11desktop_fallbacks_and_foreground():
    fx, win = FakeX(), FakeWin()
    d = dk.X11Desktop(fx, window=lambda: win)
    fx.area = None
    assert d.work_area() == (0, 0, 1920, 1080)
    fx.screen_size = lambda: None
    assert d.work_area() == dk._FALLBACK_WORK
    fx.act = ActiveWindow(pid=1, cls="a", title="t", fullscreen=False, rect=(1, 2, 3, 4))
    assert d.foreground_rect() == (1, 2, 3, 4)
    d.place(7, (1, 2, 3, 4))
    assert d.foreground_rect() is None   # own window
    assert dk.X11Desktop(None, window=lambda: None).make_overlay(1) is False


def _shape_surface():
    s = pygame.Surface((10, 3), 0, 32)
    s.fill(COLORKEY)
    s.set_at((0, 0), (1, 2, 3))
    s.set_at((9, 2), (4, 5, 6))
    return s


def test_shape_mask_bits():
    mask, w, h = dk.shape_mask(_shape_surface())
    assert (w, h) == (10, 3)
    assert mask == bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x02])


def test_shape_sent_only_on_change():
    fx = FakeX()
    d = dk.X11Desktop(fx, window=lambda: FakeWin())
    s = _shape_surface()
    d.update_shape(1, s)
    d.update_shape(1, s)
    assert len(fx.shapes) == 1
    s.set_at((3, 1), (7, 7, 7))
    d.update_shape(1, s)
    assert len(fx.shapes) == 2
    d.update_shape(1, pygame.Surface((12, 3), 0, 32))
    assert len(fx.shapes) == 3


@pytest.mark.parametrize("driver", ["dummy", "wayland"])
def test_own_hwnd_is_zero_without_wm_info_on_dummy_or_wayland(monkeypatch, driver):
    import pygame

    from engrama.app.desktop import WinDesktop

    calls = []   # the production code swallows exceptions, so record the call instead of raising
    monkeypatch.setattr(pygame.display, "get_driver", lambda: driver)
    monkeypatch.setattr(pygame.display, "get_wm_info", lambda: calls.append(driver) or {"window": 99})
    # _own_hwnd only touches pygame, so the Win32 __init__ (which cannot run on Linux) is skipped.
    d = object.__new__(WinDesktop)
    assert d._own_hwnd() == 0
    assert calls == []
