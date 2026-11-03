"""Desktop API wrapper for the overlay mode (Windows via ctypes, inert elsewhere).

Never raises: every method falls back to an inert value on any failure.
"""
from __future__ import annotations

import os
import sys

COLORKEY = (255, 0, 255)
Rect = tuple[int, int, int, int]  # x, y, w, h in screen pixels

_FALLBACK_WORK: Rect = (0, 0, 1280, 720)


class Desktop:
    available: bool = False

    def work_area(self) -> Rect:
        return _FALLBACK_WORK

    def cursor(self) -> tuple[int, int] | None:
        return None

    def foreground_rect(self) -> Rect | None:
        return None

    def make_overlay(self, hwnd: int) -> bool:
        return False

    def place(self, hwnd: int, rect: Rect) -> None:
        return None

    def show(self, hwnd: int, visible: bool) -> None:
        return None

    def restore(self, hwnd: int) -> None:
        return None


class NullDesktop(Desktop):
    available = False


class FakeDesktop(Desktop):
    """Test double: settable work/cur/fg, records calls in .calls."""

    available = True

    def __init__(self, work: Rect = _FALLBACK_WORK, cur: tuple[int, int] | None = None,
                 fg: Rect | None = None) -> None:
        self.work = work
        self.cur = cur
        self.fg = fg
        self.calls: list[tuple] = []
        self._last: dict[int, Rect] = {}

    def work_area(self) -> Rect:
        return self.work

    def cursor(self) -> tuple[int, int] | None:
        return self.cur

    def foreground_rect(self) -> Rect | None:
        return self.fg

    def make_overlay(self, hwnd: int) -> bool:
        self.calls.append(("make_overlay", hwnd))
        return True

    def place(self, hwnd: int, rect: Rect) -> None:
        rect = tuple(rect)  # type: ignore[assignment]
        if self._last.get(hwnd) == rect:
            return
        self._last[hwnd] = rect
        self.calls.append(("place", hwnd, rect))

    def show(self, hwnd: int, visible: bool) -> None:
        self.calls.append(("show", hwnd, bool(visible)))

    def restore(self, hwnd: int) -> None:
        self._last.pop(hwnd, None)
        self.calls.append(("restore", hwnd))


# Win32 constants
_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_WS_POPUP = 0x80000000
_WS_CAPTION = 0x00C00000
_WS_THICKFRAME = 0x00040000
_WS_BORDER = 0x00800000
_WS_EX_LAYERED = 0x00080000
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_TOPMOST = 0x00000008
_WS_EX_APPWINDOW = 0x00040000
_LWA_COLORKEY = 0x1
_SPI_GETWORKAREA = 0x0030
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020
_SWP_NOOWNERZORDER = 0x0200
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
_SW_HIDE = 0
_SW_SHOWNA = 8


class WinDesktop(Desktop):
    available = True

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ct = ctypes
        self._wt = wintypes
        u = ctypes.windll.user32  # type: ignore[attr-defined]
        self._u = u
        H, I = wintypes.HWND, ctypes.c_int
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.restype = wintypes.BOOL
        u.GetForegroundWindow.argtypes = []
        u.GetForegroundWindow.restype = H
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowRect.restype = wintypes.BOOL
        u.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        u.SystemParametersInfoW.restype = wintypes.BOOL
        u.SetWindowPos.argtypes = [H, H, I, I, I, I, wintypes.UINT]
        u.SetWindowPos.restype = wintypes.BOOL
        u.ShowWindow.argtypes = [H, I]
        u.ShowWindow.restype = wintypes.BOOL
        u.SetLayeredWindowAttributes.argtypes = [H, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
        u.SetLayeredWindowAttributes.restype = wintypes.BOOL
        self._ptr = hasattr(u, "GetWindowLongPtrW")
        gw = u.GetWindowLongPtrW if self._ptr else u.GetWindowLongW
        sw = u.SetWindowLongPtrW if self._ptr else u.SetWindowLongW
        rt = ctypes.c_ssize_t if self._ptr else ctypes.c_long
        gw.argtypes = [H, I]
        gw.restype = rt
        sw.argtypes = [H, I, rt]
        sw.restype = rt
        self._get, self._set = gw, sw
        self._orig: dict[int, tuple[int, int]] = {}
        self._last: dict[int, Rect] = {}
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
        except Exception:
            try:
                u.SetProcessDPIAware()
            except Exception:
                pass

    def _signed(self, v: int) -> int:
        bits = 64 if self._ptr else 32
        v &= (1 << bits) - 1
        return v - (1 << bits) if v >= 1 << (bits - 1) else v

    def work_area(self) -> Rect:
        try:
            r = self._wt.RECT()
            if not self._u.SystemParametersInfoW(_SPI_GETWORKAREA, 0, self._ct.byref(r), 0):
                return _FALLBACK_WORK
            w, h = int(r.right - r.left), int(r.bottom - r.top)
            if w <= 0 or h <= 0:
                return _FALLBACK_WORK
            return (int(r.left), int(r.top), w, h)
        except Exception:
            return _FALLBACK_WORK

    def cursor(self) -> tuple[int, int] | None:
        try:
            p = self._wt.POINT()
            if not self._u.GetCursorPos(self._ct.byref(p)):
                return None
            return (int(p.x), int(p.y))
        except Exception:
            return None

    def _own_hwnd(self) -> int:
        try:
            import pygame

            return int(pygame.display.get_wm_info().get("window", 0))
        except Exception:
            return 0

    def foreground_rect(self) -> Rect | None:
        try:
            h = self._u.GetForegroundWindow()
            if not h:
                return None
            h = int(h)
            if h == self._own_hwnd() or h in self._orig:
                return None
            r = self._wt.RECT()
            if not self._u.GetWindowRect(h, self._ct.byref(r)):
                return None
            return (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
        except Exception:
            return None

    def make_overlay(self, hwnd: int) -> bool:
        try:
            if not hwnd:
                return False
            hwnd = int(hwnd)
            style = int(self._get(hwnd, _GWL_STYLE))
            ex = int(self._get(hwnd, _GWL_EXSTYLE))
            self._orig.setdefault(hwnd, (style, ex))
            new_style = (style & ~(_WS_CAPTION | _WS_THICKFRAME | _WS_BORDER)) | _WS_POPUP
            new_ex = (ex | _WS_EX_LAYERED | _WS_EX_TOOLWINDOW | _WS_EX_TOPMOST) & ~_WS_EX_APPWINDOW
            self._set(hwnd, _GWL_STYLE, self._signed(new_style))
            self._set(hwnd, _GWL_EXSTYLE, self._signed(new_ex))
            r, g, b = COLORKEY
            ok = self._u.SetLayeredWindowAttributes(hwnd, r | (g << 8) | (b << 16), 0, _LWA_COLORKEY)
            self._u.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0,
                                 _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE | _SWP_FRAMECHANGED)
            return bool(ok)
        except Exception:
            return False

    def place(self, hwnd: int, rect: Rect) -> None:
        try:
            rect = tuple(int(v) for v in rect)  # type: ignore[assignment]
            if self._last.get(hwnd) == rect:
                return
            x, y, w, h = rect
            if self._u.SetWindowPos(hwnd, _HWND_TOPMOST, x, y, w, h, _SWP_NOACTIVATE | _SWP_NOOWNERZORDER):
                self._last[hwnd] = rect
        except Exception:
            pass

    def show(self, hwnd: int, visible: bool) -> None:
        try:
            self._u.ShowWindow(hwnd, _SW_SHOWNA if visible else _SW_HIDE)
        except Exception:
            pass

    def restore(self, hwnd: int) -> None:
        try:
            self._last.pop(hwnd, None)
            orig = self._orig.pop(int(hwnd), None)
            if orig is None:
                return
            style, ex = orig
            self._set(hwnd, _GWL_STYLE, self._signed(style))
            self._set(hwnd, _GWL_EXSTYLE, self._signed(ex))
            self._u.SetWindowPos(hwnd, _HWND_NOTOPMOST, 0, 0, 0, 0,
                                 _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE | _SWP_FRAMECHANGED)
        except Exception:
            pass


def get_desktop() -> Desktop:
    if sys.platform != "win32" or os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return NullDesktop()
    try:
        return WinDesktop()
    except Exception:
        return NullDesktop()
