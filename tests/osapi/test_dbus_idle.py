import subprocess
from types import SimpleNamespace

from engrama.osapi import dbus_idle


def _cp(out="", code=0):
    return SimpleNamespace(returncode=code, stdout=out, stderr="")


def test_mutter_reply_parsed():
    calls = []

    def run(args, **kw):
        calls.append(args)
        return _cp("(uint64 12345,)\n")
    dbus_idle._reset()
    assert dbus_idle.idle_ms(run) == 12345
    assert "org.gnome.Mutter.IdleMonitor" in calls[0]


def test_screensaver_fallback():
    def run(args, **kw):
        if "org.gnome.Mutter.IdleMonitor" in args:
            return _cp("", 1)
        return _cp("(uint32 7,)\n")
    dbus_idle._reset()
    assert dbus_idle.idle_ms(run) == 7000    # ScreenSaver: segundos (KDE)


def test_gdbus_missing_none():
    def run(args, **kw):
        raise FileNotFoundError("gdbus")
    dbus_idle._reset()
    assert dbus_idle.idle_ms(run) is None


def test_timeout_none():
    def run(args, **kw):
        raise subprocess.TimeoutExpired(args, 0.5)
    dbus_idle._reset()
    assert dbus_idle.idle_ms(run) is None


def test_garbage_none():
    dbus_idle._reset()
    assert dbus_idle.idle_ms(lambda a, **k: _cp("(nada,)")) is None


def test_remembers_working_backend():
    calls = []

    def run(args, **kw):
        calls.append(args)
        if "org.gnome.Mutter.IdleMonitor" in args:
            return _cp("", 1)
        return _cp("(uint32 3,)")
    dbus_idle._reset()
    dbus_idle.idle_ms(run)
    assert len(calls) == 2
    dbus_idle.idle_ms(run)
    assert len(calls) == 3          # só o ScreenSaver na segunda vez
    assert "org.freedesktop.ScreenSaver" in calls[2]
