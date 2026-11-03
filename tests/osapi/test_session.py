import dataclasses

import pytest

from engrama.osapi import ActiveWindow
from engrama.osapi.session import Session, detect


def test_detect_windows():
    s = detect({"DISPLAY": ":0"}, platform="win32")
    assert (s.platform, s.kind, s.compositor) == ("win32", "none", "")


def test_detect_dummy_is_none():
    s = detect({"SDL_VIDEODRIVER": "dummy", "DISPLAY": ":0"}, platform="linux")
    assert (s.platform, s.kind, s.compositor) == ("linux", "none", "")


def test_detect_hyprland():
    env = {
        "XDG_SESSION_TYPE": "wayland",
        "XDG_CURRENT_DESKTOP": "Hyprland",
        "WAYLAND_DISPLAY": "wayland-1",
        "DISPLAY": ":1",
        "HYPRLAND_INSTANCE_SIGNATURE": "x",
    }
    s = detect(env, platform="linux")
    assert (s.platform, s.kind, s.compositor) == ("linux", "wayland", "hyprland")


def test_detect_x11_kde():
    s = detect({"DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE"}, platform="linux")
    assert (s.platform, s.kind, s.compositor) == ("linux", "x11", "kde")


def test_detect_sway():
    s = detect({"WAYLAND_DISPLAY": "wayland-1", "SWAYSOCK": "/run/user/1000/sway.sock"}, platform="linux")
    assert (s.platform, s.kind, s.compositor) == ("linux", "wayland", "sway")


def test_detect_x11_with_wayland_display_stays_x11():
    s = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"}, platform="linux")
    assert (s.kind, s.compositor) == ("x11", "other")


def test_detect_tty_none():
    s = detect({"XDG_SESSION_TYPE": "tty"}, platform="linux")
    assert (s.platform, s.kind, s.compositor) == ("linux", "none", "")


def test_detect_defaults_to_environment_and_platform():
    s = detect()
    assert isinstance(s, Session)
    assert s.platform


def test_active_window_frozen():
    w = ActiveWindow(pid=1, cls="firefox", title="t", fullscreen=False, rect=(0, 0, 10, 10))
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.title = "other"
