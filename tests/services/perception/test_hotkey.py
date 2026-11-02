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
