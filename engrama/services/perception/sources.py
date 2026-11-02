"""OS sources. WinSources uses ctypes + psutil; every call is guarded."""
import sys
from typing import Protocol


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


def make_sources() -> Sources:
    if sys.platform != "win32":
        return NullSources()
    try:
        return WinSources()
    except Exception:
        return NullSources()
