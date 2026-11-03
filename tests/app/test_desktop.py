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
