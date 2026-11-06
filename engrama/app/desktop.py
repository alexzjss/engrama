"""Desktop API wrapper for the overlay mode (Windows via ctypes, inert elsewhere).

Never raises: every method falls back to an inert value on any failure.
"""
from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pygame

from engrama.app.glpresent import GLPresenter
from engrama.osapi import hyprland
from engrama.osapi.session import detect
from engrama.osapi.x11 import X11

COLORKEY = (255, 0, 255)
Rect = tuple[int, int, int, int]  # x, y, w, h in screen pixels

_FALLBACK_WORK: Rect = (0, 0, 1280, 720)


class Desktop:
    available: bool = False
    unavailable_reason: str = ""
    click_through: bool = True       # False: the OS cannot let clicks fall through transparent pixels (window stays tight)
    display_flags: int = 0           # extra pygame.display.set_mode flags for the overlay window (OPENGL on Wayland)
    offscreen: bool = False          # True: the overlay draws on a plain Surface that present() shows

    def work_area(self) -> Rect:
        return _FALLBACK_WORK

    def cursor(self) -> tuple[int, int] | None:
        return None

    def foreground_rect(self) -> Rect | None:
        return None

    def windows(self) -> list[Rect]:
        """Visible top-level windows (x, y, w, h), topmost first. Geometry only: never titles, classes or PIDs."""
        return []

    def prepare_window(self) -> None:
        """Called right before the overlay window is (re)created."""
        return None

    def present(self, surface: pygame.Surface) -> None:
        """Show the offscreen overlay surface (only for desktops with offscreen = True)."""
        return None

    def make_overlay(self, hwnd: int) -> bool:
        return False

    def place(self, hwnd: int, rect: Rect) -> None:
        return None

    def show(self, hwnd: int, visible: bool) -> None:
        return None

    def update_shape(self, hwnd: int, surface: pygame.Surface) -> None:
        return None

    def restore(self, hwnd: int) -> None:
        return None


class NullDesktop(Desktop):
    available = False

    def __init__(self, reason: str = "") -> None:
        self.unavailable_reason = reason


class FakeDesktop(Desktop):
    """Test double: settable work/cur/fg, records calls in .calls."""

    available = True

    def __init__(self, work: Rect = _FALLBACK_WORK, cur: tuple[int, int] | None = None,
                 fg: Rect | None = None, wins: list[Rect] | None = None) -> None:
        self.work = work
        self.cur = cur
        self.fg = fg
        self.wins: list[Rect] = list(wins or [])
        self.calls: list[tuple] = []
        self._last: dict[int, Rect] = {}
        self._shape: dict[int, tuple] = {}

    def work_area(self) -> Rect:
        return self.work

    def cursor(self) -> tuple[int, int] | None:
        return self.cur

    def foreground_rect(self) -> Rect | None:
        return self.fg

    def windows(self) -> list[Rect]:
        return list(self.wins)

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

    def update_shape(self, hwnd: int, surface: pygame.Surface) -> None:
        mask, w, h = shape_mask(surface)
        key = ((w, h), hashlib.blake2b(mask, digest_size=8).digest())
        if self._shape.get(hwnd) == key:
            return
        self._shape[hwnd] = key
        self.calls.append(("shape", hwnd, key[0], key[1]))

    def restore(self, hwnd: int) -> None:
        self._last.pop(hwnd, None)
        self._shape.pop(hwnd, None)
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
_DWMWA_CLOAKED = 14
_DWMWA_EXTENDED_FRAME_BOUNDS = 9
_SHELL_CLASSES = frozenset({"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"})
_SW_HIDE = 0
_SW_SHOWNA = 8


def filter_win_windows(entries: list[dict]) -> list[Rect]:
    """Keep the real, visible app windows (pure; `entries` come from EnumWindows, already topmost first)."""
    out: list[Rect] = []
    for e in entries:
        try:
            if e.get("cloaked") or e.get("minimized") or e.get("toolwindow") or e.get("cls") in _SHELL_CLASSES:
                continue
            x, y, w, h = (int(v) for v in e["rect"])
            if w < 40 or h < 24 or x <= -30000 or y <= -30000:    # minimized windows park at -32000
                continue
            out.append((x, y, w, h))
        except Exception:
            continue
    return out


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

            # On Wayland (and the dummy driver) get_wm_info() segfaults or has no native handle: no HWND.
            try:
                if pygame.display.get_driver() in ("wayland", "dummy"):
                    return 0
            except Exception:
                pass
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

    def windows(self) -> list[Rect]:
        try:
            return self._enum_windows()
        except Exception:
            return []

    def _enum_windows(self) -> list[Rect]:
        ct, wt, u = self._ct, self._wt, self._u
        dwm = ct.windll.dwmapi  # type: ignore[attr-defined]
        own = self._own_hwnd()
        entries: list[dict] = []

        @ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def cb(hwnd, _lparam):
            try:
                h = int(hwnd)
                if h == own or h in self._orig or not u.IsWindowVisible(hwnd):
                    return True
                cloaked = wt.DWORD(0)
                dwm.DwmGetWindowAttribute(hwnd, _DWMWA_CLOAKED, ct.byref(cloaked), ct.sizeof(cloaked))
                r = wt.RECT()
                if dwm.DwmGetWindowAttribute(hwnd, _DWMWA_EXTENDED_FRAME_BOUNDS, ct.byref(r), ct.sizeof(r)) != 0 \
                        and not u.GetWindowRect(hwnd, ct.byref(r)):
                    return True
                ex = int(self._get(h, _GWL_EXSTYLE))
                buf = ct.create_unicode_buffer(64)
                u.GetClassNameW(hwnd, buf, 64)
                entries.append({"rect": (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top)),
                                "cloaked": bool(cloaked.value), "minimized": bool(u.IsIconic(hwnd)),
                                "toolwindow": bool(ex & _WS_EX_TOOLWINDOW), "cls": buf.value})
            except Exception:
                pass
            return True

        u.EnumWindows(cb, 0)     # EnumWindows already walks top to bottom
        return filter_win_windows(entries)

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


def shape_mask(surface: pygame.Surface) -> tuple[bytes, int, int]:
    """XBM bitmap (LSB first, rows padded to bytes) of every pixel that is not the colour key."""
    w, h = surface.get_size()
    try:
        px = pygame.surfarray.pixels2d(surface)
    except Exception:
        px = pygame.surfarray.array2d(surface)
    solid = (px != surface.map_rgb(COLORKEY)).T          # (h, w)
    del px
    return np.packbits(solid, axis=1, bitorder="little").tobytes(), w, h


class X11Desktop(Desktop):
    """Overlay on an X11 session: always-on-top borderless window shaped by the colour-key mask."""

    available = True
    _STATES = ("_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER", "_NET_WM_STATE_STICKY")

    def __init__(self, x, window=None) -> None:
        self._x = x
        self._window_fn = window or pygame.Window.from_display_module
        self._last: dict[int, Rect] = {}
        self._shape: dict[int, tuple] = {}
        self._own: Rect | None = None

    def _win(self):
        try:
            return self._window_fn()
        except Exception:
            return None

    def work_area(self) -> Rect:
        try:
            r = self._x.work_area()
            if r:
                return tuple(int(v) for v in r)  # type: ignore[return-value]
            sz = self._x.screen_size()
            if sz:
                return (0, 0, int(sz[0]), int(sz[1]))
        except Exception:
            pass
        return _FALLBACK_WORK

    def cursor(self) -> tuple[int, int] | None:
        try:
            return self._x.pointer()
        except Exception:
            return None

    def foreground_rect(self) -> Rect | None:
        try:
            a = self._x.active()
            if a is None or a.rect is None:
                return None
            if a.pid == os.getpid() or (self._own is not None and tuple(a.rect) == self._own):
                return None   # our own overlay window
            return tuple(a.rect)  # type: ignore[return-value]
        except Exception:
            return None

    def windows(self) -> list[Rect]:
        try:
            return self._x.windows(os.getpid())
        except Exception:
            return []

    def make_overlay(self, hwnd: int) -> bool:
        try:
            win = self._win()
            if win is None or self._x is None or not hwnd:
                return False
            win.always_on_top = True
            for atom in self._STATES:
                self._x.set_state(hwnd, atom, True)
            self._last.pop(hwnd, None)
            self._shape.pop(hwnd, None)
            return True
        except Exception:
            return False

    def place(self, hwnd: int, rect: Rect) -> None:
        try:
            rect = tuple(int(v) for v in rect)  # type: ignore[assignment]
            if self._last.get(hwnd) == rect:
                return
            win = self._win()
            if win is None:
                return
            x, y, w, h = rect
            if tuple(win.size) != (w, h):
                win.size = (w, h)
            win.position = (x, y)
            self._last[hwnd] = rect
            self._own = rect
        except Exception:
            pass

    def show(self, hwnd: int, visible: bool) -> None:
        try:
            win = self._win()
            if win is not None:
                win.show() if visible else win.hide()
        except Exception:
            pass

    def update_shape(self, hwnd: int, surface: pygame.Surface) -> None:
        try:
            mask, w, h = shape_mask(surface)
            key = ((w, h), hashlib.blake2b(mask, digest_size=8).digest())
            if self._shape.get(hwnd) == key:
                return
            if self._x.set_shape(hwnd, mask, w, h):
                self._shape[hwnd] = key
        except Exception:
            pass

    def restore(self, hwnd: int) -> None:
        try:
            self._last.pop(hwnd, None)
            self._shape.pop(hwnd, None)
            self._own = None
            self._x.set_shape(hwnd, None, 0, 0)
            for atom in self._STATES:
                self._x.set_state(hwnd, atom, False)
            win = self._win()
            if win is not None:
                win.always_on_top = False
        except Exception:
            pass


OVERLAY_CLASS = "engrama-overlay"      # app_id of the overlay window on Wayland (the Hyprland rules match it)


class HyprlandDesktop(Desktop):
    """Overlay on Hyprland, native Wayland (M17).

    SDL2 on Wayland cannot position a window nor pass clicks through transparent pixels, so: transparency comes
    from an EGL surface with alpha (GLPresenter), position and flags from Hyprland (window rules + IPC dispatch),
    and the window stays tight around the creature (click_through = False) so it blocks as little as possible.
    """

    available = True
    click_through = False
    display_flags = pygame.OPENGL
    offscreen = True
    _WORK_TTL = 1.0
    _MOVE_GAP = 0.06         # at most ~16 moves a second over IPC
    _CURSOR_TTL = 0.18       # the cursor is read over IPC: 5 times a second is plenty for "is it near me"

    def __init__(self, env=None, clock=None) -> None:
        import time
        self._env = env
        self._clock = clock or time.monotonic
        self._ipc = hyprland
        self._gl = GLPresenter(COLORKEY)
        self._rules_done = False
        self._fresh = False           # the overlay toplevel was created with our app_id
        self._last: Rect | None = None
        self._work: tuple[float, Rect] | None = None
        self._cursor: tuple[float, tuple[int, int] | None] | None = None
        self._pending: Rect | None = None
        self._moved_at = -1e9

    def _win(self):
        try:
            return pygame.Window.from_display_module()
        except Exception:
            return None

    def work_area(self) -> Rect:
        now = self._clock()
        if self._work is not None and now - self._work[0] < self._WORK_TTL:
            return self._work[1]
        try:
            r = self._ipc.work_area(self._env)
        except Exception:
            r = None
        if r is None:
            return self._work[1] if self._work else _FALLBACK_WORK
        self._work = (now, r)
        return r

    def cursor(self) -> tuple[int, int] | None:
        now = self._clock()
        if self._pending is not None:
            self._send_move(self._pending, now)
        if self._cursor is not None and now - self._cursor[0] < self._CURSOR_TTL:
            return self._cursor[1]
        try:
            pos = self._ipc.cursor_pos(self._env)
        except Exception:
            pos = None
        self._cursor = (now, pos)
        return pos

    def foreground_rect(self) -> Rect | None:
        try:
            a = self._ipc.active_window(self._env)
            if a is None or a.rect is None or a.pid == os.getpid() or a.cls == OVERLAY_CLASS:
                return None
            return tuple(a.rect)  # type: ignore[return-value]
        except Exception:
            return None

    def windows(self) -> list[Rect]:
        try:
            return self._ipc.windows(self._env, own_pid=os.getpid(), own_class=OVERLAY_CLASS)
        except Exception:
            return []

    def prepare_window(self) -> None:
        os.environ["SDL_VIDEO_EGL_ALLOW_TRANSPARENCY"] = "1"
        os.environ["SDL_VIDEO_WAYLAND_WMCLASS"] = OVERLAY_CLASS
        if not self._rules_done:
            self._rules_done = bool(self._ipc.apply_overlay_rules(OVERLAY_CLASS, self._env))
        if not self._fresh:
            self._recreate_display()     # SDL fixes the Wayland app_id when the toplevel is created
            self._fresh = True
        try:
            pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)      # EGL config with an alpha channel
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 2)
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 1)
        except Exception:
            pass
        self._gl.reset()
        self._last = None

    @staticmethod
    def _recreate_display() -> None:
        try:
            pygame.display.quit()
            pygame.display.init()
        except Exception:
            pass

    def make_overlay(self, hwnd: int) -> bool:
        self._last = None
        self._pending = None
        return self._gl.ok and self._rules_done

    def present(self, surface: pygame.Surface) -> None:
        try:
            self._gl.present(surface)
        except Exception:
            pass

    def place(self, hwnd: int, rect: Rect) -> None:
        try:
            rect = tuple(int(v) for v in rect)  # type: ignore[assignment]
            if self._last is not None and self._last[:2] == rect[:2]:
                self._pending = None
                return
            now = self._clock()
            if self._last is not None and now - self._moved_at < self._MOVE_GAP:
                self._pending = rect          # too soon: flushed by the next poll (cursor())
                return
            self._send_move(rect, now)
        except Exception:
            pass

    def _send_move(self, rect: Rect, now: float) -> None:
        self._pending = None
        if self._ipc.move_window(OVERLAY_CLASS, rect[0], rect[1], self._env):
            self._last = rect
            self._moved_at = now

    def show(self, hwnd: int, visible: bool) -> None:
        try:
            win = self._win()
            if win is not None:
                win.show() if visible else win.hide()
        except Exception:
            pass

    def restore(self, hwnd: int) -> None:
        self._last = None
        self._pending = None
        self._gl.reset()
        os.environ.pop("SDL_VIDEO_WAYLAND_WMCLASS", None)
        if self._fresh:
            self._fresh = False
            self._recreate_display()     # the next window is the ordinary terrarium one, outside the overlay rules


def prefer_wayland_on_hyprland(env=None) -> bool:
    """On Hyprland, ask SDL for its native Wayland driver (XWayland ignores the window shape), unless the user chose one."""
    env = os.environ if env is None else env
    if env.get("SDL_VIDEODRIVER") or sys.platform == "win32":
        return False
    try:
        s = detect(env)
    except Exception:
        return False
    if s.kind == "wayland" and s.compositor == "hyprland":
        env["SDL_VIDEODRIVER"] = "wayland"
        return True
    return False


def get_desktop() -> Desktop:
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return NullDesktop("unsupported")
    if sys.platform == "win32":
        try:
            return WinDesktop()
        except Exception:
            return NullDesktop("unsupported")
    if sys.platform.startswith("linux"):
        try:
            kind = detect().kind
            if kind == "wayland":
                if detect().compositor == "hyprland" and pygame.display.get_driver() == "wayland":
                    return HyprlandDesktop()
                return NullDesktop("wayland")
            if kind == "x11" and pygame.display.get_driver() == "x11":
                x = X11.open()
                if x is not None:
                    return X11Desktop(x)
        except Exception:
            pass
    return NullDesktop("unsupported")
