import threading
import time

import pytest

from engrama.services.perception.hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    GlobalHotkey,
    parse_hotkey,
)


class FakeApi:
    def __init__(self, register_ok=True, raise_on_register=False):
        self.register_ok = register_ok
        self.raise_on_register = raise_on_register
        self.registered = []
        self.unregistered = []
        self.quit_for = []
        self._queue = []
        self._cv = threading.Condition()

    def register(self, id, mods, vk):
        if self.raise_on_register:
            raise OSError("boom")
        self.registered.append((id, mods, vk))
        return self.register_ok

    def unregister(self, id):
        self.unregistered.append(id)

    def get_message(self):
        with self._cv:
            while not self._queue:
                self._cv.wait()
            item = self._queue.pop(0)
        return item

    def post_quit(self, thread_id):
        self.quit_for.append(thread_id)
        with self._cv:
            self._queue.append(None)
            self._cv.notify_all()

    def press(self, id=1):
        with self._cv:
            self._queue.append(id)
            self._cv.notify_all()


def test_parse_hotkey():
    mods, vk = parse_hotkey("ctrl+alt+e")
    assert mods == MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
    assert vk == ord("E")

    mods, vk = parse_hotkey("shift+win+f9")
    assert mods == MOD_SHIFT | MOD_WIN | MOD_NOREPEAT
    assert vk == 0x70 + 9 - 1

    assert parse_hotkey(" Ctrl + 5 ") == (MOD_CONTROL | MOD_NOREPEAT, ord("5"))
    assert parse_hotkey("ctrl+alt+f24")[1] == 0x87


@pytest.mark.parametrize(
    "spec", ["", "ctrl", "ctrl+alt", "ctrl+e+x", "ctrl+f25", "ctrl+f0", "ctrl+foo", "ctrl+ab"]
)
def test_parse_hotkey_invalid(spec):
    with pytest.raises(ValueError):
        parse_hotkey(spec)


def test_press_calls_callback():
    api = FakeApi()
    calls = threading.Event()
    hk = GlobalHotkey("ctrl+alt+e", calls.set, api=api)
    try:
        assert hk.start() is True
        assert hk.ok is True
        assert hk.error == ""
        assert api.registered == [(1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("E"))]
        api.press()
        assert calls.wait(1.0)
    finally:
        hk.stop()
    assert api.unregistered == [1]


def test_register_failure_reports_error():
    api = FakeApi(register_ok=False)
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, api=api)
    assert hk.start() is False
    assert hk.ok is False
    assert hk.error
    hk.stop()


def test_register_exception_reports_error():
    api = FakeApi(raise_on_register=True)
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, api=api)
    assert hk.start() is False
    assert hk.ok is False
    assert hk.error


def test_invalid_spec_reports_error_without_raising():
    api = FakeApi()
    hk = GlobalHotkey("nope", lambda: None, api=api)
    assert hk.start() is False
    assert hk.ok is False
    assert hk.error
    assert api.registered == []


@pytest.mark.perf
def test_stop_is_fast():
    api = FakeApi()
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, api=api)
    assert hk.start() is True
    started = time.monotonic()
    hk.stop()
    elapsed = time.monotonic() - started
    assert elapsed < 0.5
    assert hk.ok is False
    assert len(api.quit_for) == 1


def test_callback_exception_contained():
    api = FakeApi()
    seen = threading.Semaphore(0)

    def boom():
        seen.release()
        raise RuntimeError("callback failed")

    hk = GlobalHotkey("ctrl+alt+e", boom, api=api)
    try:
        assert hk.start() is True
        api.press()
        api.press()
        assert seen.acquire(timeout=1.0)
        assert seen.acquire(timeout=1.0)
    finally:
        hk.stop()


# --- M8: X11 ---------------------------------------------------------------
from engrama.osapi.session import Session  # noqa: E402
from engrama.services.perception import hotkey as hk_mod  # noqa: E402


class FakeKeyGrab:
    def __init__(self, presses=1):
        self.grabs, self.closed, self.ungrabbed = [], False, False
        self._presses = presses
        self._stop = threading.Event()

    def grab(self, mask, keysym):
        self.grabs.append((mask, keysym))
        return True

    def wait(self):
        if self._presses > 0:
            self._presses -= 1
            return True
        self._stop.wait(5)
        return False

    def wake(self):
        self._stop.set()

    def ungrab(self):
        self.ungrabbed = True

    def close(self):
        self.closed = True


def _sess(kind, platform="linux"):
    return Session(platform=platform, kind=kind, compositor="", env={})


def test_x11api_maps_mods_and_keysym():
    fake = FakeKeyGrab()
    api = hk_mod._X11Api(opener=lambda: fake)
    mods, vk = parse_hotkey("ctrl+alt+e")
    assert api.register(1, mods, vk) is True
    assert fake.grabs == [(12, 0x65)]
    api2 = hk_mod._X11Api(opener=lambda: FakeKeyGrab())
    mods, vk = parse_hotkey("shift+win+f9")
    api2.register(1, mods, vk)
    assert api2._kg.grabs == [(1 | 64, 0xFFBD + 9)]


def test_x11api_register_fails_without_connection():
    assert hk_mod._X11Api(opener=lambda: None).register(1, 4, ord("E")) is False


def test_x11api_loop_and_quit():
    fake = FakeKeyGrab(presses=1)
    hit = threading.Event()
    hk = GlobalHotkey("ctrl+alt+e", hit.set, api=hk_mod._X11Api(opener=lambda: fake))
    assert hk.start()
    assert hit.wait(1.0)
    hk.stop()
    assert fake.ungrabbed and fake.closed


@pytest.mark.perf
def test_x11api_stop_is_fast():
    fake = FakeKeyGrab(presses=1)
    hit = threading.Event()
    hk = GlobalHotkey("ctrl+alt+e", hit.set, api=hk_mod._X11Api(opener=lambda: fake))
    assert hk.start()
    assert hit.wait(1.0)
    t0 = time.monotonic()
    hk.stop()
    assert time.monotonic() - t0 < 0.6


def test_start_wayland_error():
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, session=_sess("wayland"))
    assert hk.start() is False
    assert hk.error == "wayland"


def test_start_unsupported():
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, session=_sess("none"))
    assert hk.start() is False and hk.error == "unsupported"


def test_start_windows_uses_winapi(monkeypatch):
    api = FakeApi()
    monkeypatch.setattr(hk_mod, "_WinApi", lambda: api)
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, session=_sess("none", "win32"))
    try:
        assert hk.start() and api.registered
    finally:
        hk.stop()


def test_start_x11_uses_x11api(monkeypatch):
    api = FakeApi()
    monkeypatch.setattr(hk_mod, "_X11Api", lambda: api)
    hk = GlobalHotkey("ctrl+alt+e", lambda: None, session=_sess("x11"))
    try:
        assert hk.start() and api.registered
    finally:
        hk.stop()
