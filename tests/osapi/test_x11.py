import os

import pytest

from engrama.osapi import x11
from engrama.osapi.x11 import X11, X11KeyGrab, keysym_for


def test_keysym_for():
    assert keysym_for("e") == 0x65
    assert keysym_for("5") == 0x35
    assert keysym_for("f1") == 0xFFBE
    assert keysym_for("F12") == 0xFFC9
    assert keysym_for("f24") == 0xFFD5
    for bad in ("", "ee", "f0", "f25", "!", "é", "f01"):
        assert keysym_for(bad) is None


def test_open_without_display_is_none(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    assert X11.open() is None
    assert X11KeyGrab.open() is None


def test_open_without_lib_is_none():
    assert X11.open(":99", loader=lambda name: None) is None
    assert X11KeyGrab.open(":99", loader=lambda name: None) is None


def test_open_unreachable_display_is_none():
    assert X11.open(":987") is None


def test_parse_wm_class():
    assert x11._parse_wm_class(b"navigator\0Firefox\0") == "firefox"
    assert x11._parse_wm_class(b"solo\0") == "solo"
    assert x11._parse_wm_class(b"") == ""


def test_decode_utf8():
    assert x11._decode_utf8("olá\0lixo".encode()) == "olá"
    assert x11._decode_utf8(b"\xff\xfeok") != ""


def test_workarea_from():
    cards = [0, 0, 1920, 1040, 10, 20, 800, 600]
    assert x11._workarea_from(cards, 0) == (0, 0, 1920, 1040)
    assert x11._workarea_from(cards, 1) == (10, 20, 800, 600)
    assert x11._workarea_from(cards, 7) == (0, 0, 1920, 1040)
    assert x11._workarea_from([1, 2], 0) is None
    assert x11._workarea_from([], None) is None


@pytest.mark.skipif(os.environ.get("XDG_SESSION_TYPE") != "x11" or not os.environ.get("DISPLAY"),
                    reason="needs a real X11 session")
def test_real_x11_smoke():
    x = X11.open()
    assert x is not None
    x.active(), x.idle_ms(), x.pointer(), x.work_area(), x.screen_size()
    x.close()
