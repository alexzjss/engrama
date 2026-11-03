"""OS sources. WinSources uses ctypes + psutil; every call is guarded."""
import sys
import time
from collections.abc import Callable, Sequence
from typing import Protocol

from engrama.osapi import BACKEND_RETRY_S, ActiveWindow, dbus_idle, hyprland, sway
from engrama.osapi.session import Session, detect
from engrama.osapi.wayland import IdleWatcher
from engrama.osapi.x11 import X11

from . import IDLE_AFTER_S


class Sources(Protocol):
    def foreground(self) -> tuple[str, str] | None: ...
    def idle_seconds(self) -> float | None: ...
    def is_fullscreen(self) -> bool | None: ...
    def cpu_percent(self) -> float | None: ...


class NullSources:
    def foreground(self): return None
    def idle_seconds(self): return None
    def is_fullscreen(self): return None
    def cpu_percent(self): return None


class ScriptedSources:
    """Deterministic fake machine (bench / smoke): rotates through a few apps, never idle, never heavy."""
    _APPS = (("code.exe", "main.py - engrama"), ("spotify.exe", "Song - Artist"),
             ("chrome.exe", "Docs"), ("hollow_knight.exe", "Hollow Knight"))

    def __init__(self):
        self._n = 0

    def foreground(self):
        self._n += 1
        return self._APPS[(self._n // 3) % len(self._APPS)]

    def idle_seconds(self): return 1.0
    def is_fullscreen(self): return False
    def cpu_percent(self): return 15.0


_SHELL_CLASSES = {"progman", "workerw", "shell_traywnd", "shell_secondarytraywnd"}


class WinSources:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._ct, self._wt = ctypes, wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        self._u, self._k = u, k
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        k.GetTickCount64.restype = ctypes.c_ulonglong

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        self._LII, self._MI = LASTINPUTINFO, MONITORINFO

    def _text(self, fn, hwnd, n=512) -> str:
        buf = self._ct.create_unicode_buffer(n)
        fn(hwnd, buf, n)
        return buf.value

    def foreground(self):
        try:
            hwnd = self._u.GetForegroundWindow()
            if not hwnd:
                return None
            pid = self._wt.DWORD(0)
            self._u.GetWindowThreadProcessId(hwnd, self._ct.byref(pid))
            if not pid.value:
                return None
            import psutil
            name = psutil.Process(pid.value).name().lower()
            title = self._text(self._u.GetWindowTextW, hwnd)
            if not name:
                return None
            return name, title
        except Exception:
            return None

    def idle_seconds(self):
        try:
            info = self._LII()
            info.cbSize = self._ct.sizeof(info)
            if not self._u.GetLastInputInfo(self._ct.byref(info)):
                return None
            now = self._k.GetTickCount64() & 0xFFFFFFFF
            return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
        except Exception:
            return None

    def is_fullscreen(self):
        try:
            hwnd = self._u.GetForegroundWindow()
            if not hwnd:
                return None
            if self._text(self._u.GetClassNameW, hwnd, 256).lower() in _SHELL_CLASSES:
                return False
            rect = self._wt.RECT()
            if not self._u.GetWindowRect(hwnd, self._ct.byref(rect)):
                return None
            mon = self._u.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            mi = self._MI()
            mi.cbSize = self._ct.sizeof(mi)
            if not mon or not self._u.GetMonitorInfoW(mon, self._ct.byref(mi)):
                return None
            m = mi.rcMonitor
            return (rect.left <= m.left and rect.top <= m.top
                    and rect.right >= m.right and rect.bottom >= m.bottom)
        except Exception:
            return None

    def cpu_percent(self):
        try:
            import psutil
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            return None


_SANDBOX_NAMES = {"bwrap", "flatpak-bwrap"}


class LinuxSources:
    """Sources over the Linux backends. Every call is guarded; a failing idle backend rests BACKEND_RETRY_S."""

    def __init__(self, window: Callable[[], ActiveWindow | None] | None,
                 idle: Sequence[Callable[[], float | None]], now=time.monotonic) -> None:
        self._window = window
        self._idle = list(idle)
        self._now = now
        self._off_until = [float("-inf")] * len(self._idle)

    def _active(self) -> ActiveWindow | None:
        if self._window is None:
            return None
        try:
            return self._window()
        except Exception:
            return None

    def foreground(self):
        try:
            aw = self._active()
            if aw is None:
                return None
            name = ""
            if aw.pid:
                try:
                    import psutil
                    name = psutil.Process(aw.pid).name().strip().lower()
                except Exception:
                    name = ""
            if not name or name in _SANDBOX_NAMES:
                name = (aw.cls or "").strip().lower()
            if not name:
                return None
            return name, aw.title or ""
        except Exception:
            return None

    def idle_seconds(self):
        now = self._now()
        for i, fn in enumerate(self._idle):
            if now < self._off_until[i]:
                continue
            try:
                v = fn()
            except Exception:
                v = None
            if v is None:
                self._off_until[i] = now + BACKEND_RETRY_S
                continue
            return float(v)
        return None

    def is_fullscreen(self):
        aw = self._active()
        return None if aw is None else aw.fullscreen

    def cpu_percent(self):
        try:
            import psutil
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            return None


def _ms_to_s(fn: Callable[[], int | None]) -> Callable[[], float | None]:
    def call():
        v = fn()
        return None if v is None else v / 1000.0
    return call


def _wayland_idle(env) -> Callable[[], float | None]:
    state: dict = {"w": None}

    def call():
        w = state["w"]
        if w is None:
            w = IdleWatcher(IDLE_AFTER_S, env=env)
            if not w.start():
                w.close()
                return None
            state["w"] = w
        v = w.idle_seconds()
        if v is None:
            w.close()
            state["w"] = None
        return v
    return call


def build_linux_sources(session: Session) -> Sources:
    window = None
    idle: list[Callable[[], float | None]] = []
    if session.kind == "wayland":
        env = session.env
        if session.compositor == "hyprland":
            window = lambda: hyprland.active_window(env)  # noqa: E731
        elif session.compositor == "sway":
            window = lambda: sway.active_window(env)  # noqa: E731
        idle.append(_wayland_idle(env))
        idle.append(_ms_to_s(lambda: dbus_idle.idle_ms()))
    elif session.kind == "x11":
        x = X11.open()
        if x is not None:
            window = x.active
            idle.append(_ms_to_s(x.idle_ms))
        idle.append(_ms_to_s(lambda: dbus_idle.idle_ms()))
    else:
        return NullSources()
    return LinuxSources(window, idle)


def make_sources(env=None, platform: str | None = None) -> Sources:
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        try:
            return WinSources()
        except Exception:
            return NullSources()
    if platform.startswith("linux"):
        try:
            return build_linux_sources(detect(env, platform))
        except Exception:
            return NullSources()
    return NullSources()
