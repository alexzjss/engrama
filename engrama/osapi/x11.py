"""Ligações mínimas com o X11 via ctypes (libX11, libXss, libXext). Só stdlib.

Tudo é inerte quando não há X: ``open`` devolve None e todo método público
captura qualquer exceção devolvendo o valor inerte.
"""
import ctypes
import ctypes.util
import os
import select
import threading

from engrama.osapi import ActiveWindow, Rect

MODMASK = {"shift": 1, "ctrl": 4, "control": 4, "alt": 8, "win": 64, "windows": 64}
LOCK_VARIANTS = (0, 2, 16, 18)  # nenhum, CapsLock, NumLock, ambos

_KEYPRESS = 2
_CLIENT_MESSAGE = 33
_SUBSTRUCTURE_MASK = (1 << 19) | (1 << 20)  # Redirect | Notify
_SHAPE_BOUNDING, _SHAPE_INPUT, _SHAPE_SET = 0, 2, 0

_last_error = 0  # último código de erro X (global do processo, como o handler)


def keysym_for(key: str) -> int | None:
    if not isinstance(key, str):
        return None
    k = key.strip().lower()
    if len(k) == 1 and ("a" <= k <= "z" or "0" <= k <= "9"):
        return ord(k)
    if k.startswith("f") and k[1:].isdigit() and not k[1:].startswith("0"):
        n = int(k[1:])
        if 1 <= n <= 24:
            return 0xFFBD + n
    return None


def _decode_utf8(data: bytes) -> str:
    try:
        return bytes(data).split(b"\0", 1)[0].decode("utf-8", "replace")
    except Exception:
        return ""


def _parse_wm_class(data: bytes) -> str:
    try:
        parts = [p for p in bytes(data).split(b"\0") if p]
        if not parts:
            return ""
        return parts[1 if len(parts) > 1 else 0].decode("utf-8", "replace").lower()
    except Exception:
        return ""


def _workarea_from(cards, current_desktop) -> Rect | None:
    try:
        cards = list(cards)
        n = len(cards) // 4
        if n < 1:
            return None
        d = int(current_desktop) if current_desktop is not None else 0
        if not 0 <= d < n:
            d = 0
        x, y, w, h = (int(c) for c in cards[4 * d:4 * d + 4])
        return (x, y, w, h)
    except Exception:
        return None


# --- estruturas ------------------------------------------------------------

class _XErrorEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("display", ctypes.c_void_p),
                ("resourceid", ctypes.c_ulong), ("serial", ctypes.c_ulong),
                ("error_code", ctypes.c_ubyte), ("request_code", ctypes.c_ubyte),
                ("minor_code", ctypes.c_ubyte)]


class _XClientMessage(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]


class _XEvent(ctypes.Union):
    _fields_ = [("type", ctypes.c_int), ("client", _XClientMessage),
                ("pad", ctypes.c_long * 24)]


class _SaverInfo(ctypes.Structure):
    _fields_ = [("window", ctypes.c_ulong), ("state", ctypes.c_int),
                ("kind", ctypes.c_int), ("til_or_since", ctypes.c_ulong),
                ("idle", ctypes.c_ulong), ("event_mask", ctypes.c_ulong)]


_ERR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_XErrorEvent))


def _on_error(_display, event):  # nunca deixa o Xlib encerrar o processo
    global _last_error
    try:
        _last_error = int(event.contents.error_code)
    except Exception:
        _last_error = 1
    return 0


_handler_ref = _ERR_HANDLER(_on_error)


def _load_x(loader, with_ext: bool):
    """Carrega libs e declara argtypes/restype. Levanta se algo faltar de essencial."""
    name = loader("X11")
    if not name:
        raise OSError("libX11")
    x = ctypes.CDLL(name)
    c = ctypes
    vp, ul, i, ui = c.c_void_p, c.c_ulong, c.c_int, c.c_uint
    sig = {
        "XOpenDisplay": ([c.c_char_p], vp),
        "XCloseDisplay": ([vp], i),
        "XSetErrorHandler": ([_ERR_HANDLER], vp),
        "XDefaultRootWindow": ([vp], ul),
        "XDefaultScreen": ([vp], i),
        "XDisplayWidth": ([vp, i], i),
        "XDisplayHeight": ([vp, i], i),
        "XInternAtom": ([vp, c.c_char_p, i], ul),
        "XGetWindowProperty": ([vp, ul, ul, c.c_long, c.c_long, i, ul, c.POINTER(ul),
                                c.POINTER(i), c.POINTER(ul), c.POINTER(ul),
                                c.POINTER(c.POINTER(c.c_ubyte))], i),
        "XFree": ([vp], i),
        "XGetGeometry": ([vp, ul, c.POINTER(ul), c.POINTER(i), c.POINTER(i),
                          c.POINTER(ui), c.POINTER(ui), c.POINTER(ui), c.POINTER(ui)], i),
        "XTranslateCoordinates": ([vp, ul, ul, i, i, c.POINTER(i), c.POINTER(i),
                                   c.POINTER(ul)], i),
        "XQueryPointer": ([vp, ul, c.POINTER(ul), c.POINTER(ul), c.POINTER(i),
                           c.POINTER(i), c.POINTER(i), c.POINTER(i), c.POINTER(ui)], i),
        "XSendEvent": ([vp, ul, i, c.c_long, c.POINTER(_XEvent)], i),
        "XFlush": ([vp], i),
        "XSync": ([vp, i], i),
        "XPending": ([vp], i),
        "XNextEvent": ([vp, c.POINTER(_XEvent)], i),
        "XConnectionNumber": ([vp], i),
        "XKeysymToKeycode": ([vp, ul], c.c_ubyte),
        "XGrabKey": ([vp, i, ui, ul, i, i, i], i),
        "XUngrabKey": ([vp, i, ui, ul], i),
        "XCreateBitmapFromData": ([vp, ul, c.c_char_p, ui, ui], ul),
        "XFreePixmap": ([vp, ul], i),
    }
    for fn, (args, res) in sig.items():
        f = getattr(x, fn)
        f.argtypes, f.restype = args, res
    xss = xext = None
    n = loader("Xss")
    if n:
        try:
            xss = ctypes.CDLL(n)
            xss.XScreenSaverQueryInfo.argtypes = [vp, ul, c.POINTER(_SaverInfo)]
            xss.XScreenSaverQueryInfo.restype = i
        except Exception:
            xss = None
    if with_ext:
        n = loader("Xext")
        if n:
            try:
                xext = ctypes.CDLL(n)
                xext.XShapeCombineMask.argtypes = [vp, ul, i, i, i, ul, i]
                xext.XShapeCombineMask.restype = None
            except Exception:
                xext = None
    return x, xss, xext


def _open_display(x, display):
    if display is None:
        display = os.environ.get("DISPLAY")
    if not display:
        return None
    x.XSetErrorHandler(_handler_ref)
    dpy = x.XOpenDisplay(display.encode())
    return dpy or None


class X11:
    def __init__(self, x, xss, xext, dpy):
        self._x, self._xss, self._xext, self._dpy = x, xss, xext, dpy
        self._lock = threading.RLock()
        self._root = x.XDefaultRootWindow(dpy)
        self._atoms: dict[str, int] = {}

    @classmethod
    def open(cls, display: str | None = None, loader=ctypes.util.find_library) -> "X11 | None":
        try:
            if display is None and not os.environ.get("DISPLAY"):
                return None
            x, xss, xext = _load_x(loader, True)
            dpy = _open_display(x, display)
            if not dpy:
                return None
            return cls(x, xss, xext, dpy)
        except Exception:
            return None

    # --- auxiliares ----------------------------------------------------
    def _atom(self, name: str) -> int:
        a = self._atoms.get(name)
        if a is None:
            a = int(self._x.XInternAtom(self._dpy, name.encode(), 0))
            self._atoms[name] = a
        return a

    def _prop(self, win: int, name: str, max_items: int = 1024):
        """(formato, lista de ints | bytes) ou None. Sempre libera com XFree."""
        c = ctypes
        atype, fmt = c.c_ulong(), c.c_int()
        n, after = c.c_ulong(), c.c_ulong()
        ptr = c.POINTER(c.c_ubyte)()
        r = self._x.XGetWindowProperty(
            self._dpy, win, self._atom(name), 0, max_items, 0, 0,  # AnyPropertyType
            c.byref(atype), c.byref(fmt), c.byref(n), c.byref(after), c.byref(ptr))
        if r != 0 or not ptr:
            return None
        try:
            count = int(n.value)
            if count == 0 or fmt.value not in (8, 16, 32):
                return None
            if fmt.value == 8:
                return 8, bytes(c.string_at(ptr, count))
            ctype = {16: c.c_ushort, 32: c.c_ulong}[fmt.value]
            arr = c.cast(ptr, c.POINTER(ctype))
            return fmt.value, [int(arr[i]) for i in range(count)]
        finally:
            self._x.XFree(ptr)

    def _cardinals(self, win: int, name: str) -> list[int] | None:
        p = self._prop(win, name)
        return p[1] if p and p[0] != 8 else None

    # --- API ------------------------------------------------------------
    def active(self) -> ActiveWindow | None:
        try:
            with self._lock:
                act = self._cardinals(self._root, "_NET_ACTIVE_WINDOW")
                if not act or not act[0]:
                    return None
                win = act[0]
                pid_l = self._cardinals(win, "_NET_WM_PID")
                pid = pid_l[0] if pid_l and pid_l[0] > 0 else None
                cp = self._prop(win, "WM_CLASS")
                cls = _parse_wm_class(cp[1]) if cp and cp[0] == 8 else ""
                tp = self._prop(win, "_NET_WM_NAME") or self._prop(win, "WM_NAME")
                title = _decode_utf8(tp[1]) if tp and tp[0] == 8 else ""
                st = self._cardinals(win, "_NET_WM_STATE")
                fullscreen = (self._atom("_NET_WM_STATE_FULLSCREEN") in st) if st is not None else False
                return ActiveWindow(pid, cls, title, fullscreen, self._rect(win))
        except Exception:
            return None

    def _rect(self, win: int) -> Rect | None:
        c = ctypes
        root = c.c_ulong()
        gx, gy = c.c_int(), c.c_int()
        w, h, bw, depth = (c.c_uint() for _ in range(4))
        if not self._x.XGetGeometry(self._dpy, win, c.byref(root), c.byref(gx), c.byref(gy),
                                    c.byref(w), c.byref(h), c.byref(bw), c.byref(depth)):
            return None
        dx, dy, child = c.c_int(), c.c_int(), c.c_ulong()
        if not self._x.XTranslateCoordinates(self._dpy, win, self._root, 0, 0,
                                             c.byref(dx), c.byref(dy), c.byref(child)):
            return None
        return (dx.value, dy.value, int(w.value), int(h.value))

    def idle_ms(self) -> int | None:
        try:
            if self._xss is None:
                return None
            with self._lock:
                info = _SaverInfo()
                if not self._xss.XScreenSaverQueryInfo(self._dpy, self._root, ctypes.byref(info)):
                    return None
                return int(info.idle)
        except Exception:
            return None

    def work_area(self) -> Rect | None:
        try:
            with self._lock:
                cards = self._cardinals(self._root, "_NET_WORKAREA")
                if not cards:
                    return None
                cur = self._cardinals(self._root, "_NET_CURRENT_DESKTOP")
                return _workarea_from(cards, cur[0] if cur else 0)
        except Exception:
            return None

    def screen_size(self) -> tuple[int, int] | None:
        try:
            with self._lock:
                s = self._x.XDefaultScreen(self._dpy)
                w, h = int(self._x.XDisplayWidth(self._dpy, s)), int(self._x.XDisplayHeight(self._dpy, s))
            return (w, h) if w > 0 and h > 0 else None
        except Exception:
            return None

    def pointer(self) -> tuple[int, int] | None:
        try:
            c = ctypes
            with self._lock:
                root, child = c.c_ulong(), c.c_ulong()
                rx, ry, wx, wy = (c.c_int() for _ in range(4))
                mask = c.c_uint()
                if not self._x.XQueryPointer(self._dpy, self._root, c.byref(root), c.byref(child),
                                             c.byref(rx), c.byref(ry), c.byref(wx), c.byref(wy),
                                             c.byref(mask)):
                    return None
                return (rx.value, ry.value)
        except Exception:
            return None

    def set_state(self, win: int, atom: str, on: bool) -> bool:
        try:
            with self._lock:
                ev = _XEvent()
                ev.client.type = _CLIENT_MESSAGE
                ev.client.send_event = 1
                ev.client.display = self._dpy
                ev.client.window = win
                ev.client.message_type = self._atom("_NET_WM_STATE")
                ev.client.format = 32
                ev.client.data[0] = 1 if on else 0  # _NET_WM_STATE_ADD / REMOVE
                ev.client.data[1] = self._atom(atom)
                ev.client.data[2] = 0
                ev.client.data[3] = 1  # origem: aplicativo normal
                ok = self._x.XSendEvent(self._dpy, self._root, 0, _SUBSTRUCTURE_MASK, ctypes.byref(ev))
                self._x.XFlush(self._dpy)
                return bool(ok)
        except Exception:
            return False

    def set_shape(self, win: int, mask: bytes | None, w: int, h: int) -> bool:
        try:
            if self._xext is None:
                return False
            with self._lock:
                pix = 0
                if mask is not None:
                    need = ((w + 7) // 8) * h
                    if w <= 0 or h <= 0 or len(mask) < need:
                        return False
                    pix = self._x.XCreateBitmapFromData(self._dpy, self._root, bytes(mask), w, h)
                    if not pix:
                        return False
                for kind in (_SHAPE_BOUNDING, _SHAPE_INPUT):
                    self._xext.XShapeCombineMask(self._dpy, win, kind, 0, 0, pix, _SHAPE_SET)
                if pix:
                    self._x.XFreePixmap(self._dpy, pix)
                self._x.XFlush(self._dpy)
                return True
        except Exception:
            return False

    def close(self) -> None:
        try:
            with self._lock:
                if self._dpy:
                    self._x.XCloseDisplay(self._dpy)
                    self._dpy = None
        except Exception:
            pass
        self._dpy = None


class X11KeyGrab:
    """Conexão própria para a thread do atalho global."""

    def __init__(self, x, dpy, rfd: int, wfd: int):
        self._x, self._dpy = x, dpy
        self._root = x.XDefaultRootWindow(dpy)
        self._fd = x.XConnectionNumber(dpy)
        self._rfd, self._wfd = rfd, wfd
        self._grabbed: list[tuple[int, int]] = []
        self._closed = False

    @classmethod
    def open(cls, display: str | None = None, loader=ctypes.util.find_library) -> "X11KeyGrab | None":
        try:
            if display is None and not os.environ.get("DISPLAY"):
                return None
            x, _, _ = _load_x(loader, False)
            dpy = _open_display(x, display)
            if not dpy:
                return None
            rfd, wfd = os.pipe()
            os.set_blocking(rfd, False)
            os.set_blocking(wfd, False)
            return cls(x, dpy, rfd, wfd)
        except Exception:
            return None

    def grab(self, mask: int, keysym: int) -> bool:
        global _last_error
        try:
            if self._closed:
                return False
            code = int(self._x.XKeysymToKeycode(self._dpy, keysym))
            if code == 0:
                return False
            _last_error = 0
            for lock in LOCK_VARIANTS:
                self._x.XGrabKey(self._dpy, code, mask | lock, self._root, 0, 1, 1)  # async
            self._x.XSync(self._dpy, 0)
            if _last_error:  # BadAccess: outro cliente já tem a combinação
                for lock in LOCK_VARIANTS:
                    self._x.XUngrabKey(self._dpy, code, mask | lock, self._root)
                self._x.XSync(self._dpy, 0)
                _last_error = 0
                return False
            self._grabbed.append((code, mask))
            return True
        except Exception:
            return False

    def wait(self) -> bool:
        """True = tecla; False = parar (wake/close) ou erro."""
        try:
            ev = _XEvent()
            while not self._closed:
                while self._x.XPending(self._dpy):
                    self._x.XNextEvent(self._dpy, ctypes.byref(ev))
                    if ev.type == _KEYPRESS:
                        return True
                r, _, _ = select.select([self._fd, self._rfd], [], [])
                if self._rfd in r:
                    try:
                        os.read(self._rfd, 64)
                    except BlockingIOError:
                        pass
                    return False
            return False
        except Exception:
            return False

    def wake(self) -> None:
        try:
            os.write(self._wfd, b"x")
        except Exception:
            pass

    def ungrab(self) -> None:
        try:
            if self._closed:
                return
            for code, mask in self._grabbed:
                for lock in LOCK_VARIANTS:
                    self._x.XUngrabKey(self._dpy, code, mask | lock, self._root)
            self._grabbed.clear()
            self._x.XFlush(self._dpy)
        except Exception:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self.ungrab()
        self._closed = True
        try:
            self._x.XCloseDisplay(self._dpy)
        except Exception:
            pass
        for fd in (self._rfd, self._wfd):
            try:
                os.close(fd)
            except Exception:
                pass
