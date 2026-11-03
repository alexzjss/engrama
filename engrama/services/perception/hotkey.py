"""Atalho global para os olhos: RegisterHotKey no Windows, XGrabKey numa sessão X11.

Só stdlib. A API do sistema é injetável (`api`) para os testes; a real usa
ctypes.windll.user32 e só existe no Windows.
"""

from __future__ import annotations

import threading
from typing import Callable

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

HOTKEY_ID = 1

_MODIFIERS = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}


def parse_hotkey(spec: str) -> tuple[int, int]:
    """Converte "ctrl+alt+e" em (modificadores, código virtual).

    Levanta ValueError para qualquer spec sem exatamente uma tecla final válida.
    """
    if not isinstance(spec, str):
        raise ValueError(f"hotkey inválida: {spec!r}")
    parts = [p.strip().lower() for p in spec.split("+")]
    if not parts or any(not p for p in parts):
        raise ValueError(f"hotkey inválida: {spec!r}")
    *mod_names, key = parts
    mods = MOD_NOREPEAT
    for name in mod_names:
        if name not in _MODIFIERS:
            raise ValueError(f"modificador desconhecido: {name!r}")
        mods |= _MODIFIERS[name]
    if len(key) == 1 and key.isalpha():
        vk = ord(key.upper())
    elif len(key) == 1 and key.isdigit():
        vk = ord(key)
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"tecla desconhecida: {key!r}")
    return mods, vk


class _WinApi:
    """Chamadas reais do Windows. Criada só quando a plataforma é Windows."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = ctypes.windll.user32
        self._msg = wintypes.MSG()

    def register(self, id: int, mods: int, vk: int) -> bool:
        return bool(self._user32.RegisterHotKey(None, id, mods, vk))

    def unregister(self, id: int) -> None:
        self._user32.UnregisterHotKey(None, id)

    def get_message(self) -> int | None:
        """Bloqueia até um WM_HOTKEY (devolve o id) ou WM_QUIT/erro (devolve None)."""
        while True:
            r = self._user32.GetMessageW(self._ctypes.byref(self._msg), None, 0, 0)
            if r <= 0:
                return None
            if self._msg.message == WM_HOTKEY:
                return int(self._msg.wParam)

    def post_quit(self, thread_id: int) -> None:
        self._user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)


class _X11Api:
    """Mesma interface de `_WinApi`, sobre `X11KeyGrab` (conexão própria da thread do atalho)."""

    def __init__(self, opener=None) -> None:
        self._opener = opener
        self._kg = None

    def register(self, id: int, mods: int, vk: int) -> bool:
        from engrama.osapi.x11 import MODMASK, X11KeyGrab

        opener = self._opener or X11KeyGrab.open
        kg = opener()
        if kg is None:
            return False
        mask = 0
        if mods & MOD_SHIFT:
            mask |= MODMASK["shift"]
        if mods & MOD_CONTROL:
            mask |= MODMASK["ctrl"]
        if mods & MOD_ALT:
            mask |= MODMASK["alt"]
        if mods & MOD_WIN:
            mask |= MODMASK["win"]
        if 0x70 <= vk <= 0x87:   # F1..F24
            keysym = 0xFFBE + (vk - 0x70)
        else:
            keysym = ord(chr(vk).lower())
        self._kg = kg
        if not kg.grab(mask, keysym):
            self._kg = None
            kg.close()
            return False
        return True

    def unregister(self, id: int) -> None:
        kg, self._kg = self._kg, None
        if kg is not None:
            kg.ungrab()
            kg.close()

    def get_message(self) -> int | None:
        kg = self._kg
        if kg is None:
            return None
        return HOTKEY_ID if kg.wait() else None

    def post_quit(self, thread_id: int) -> None:
        kg = self._kg
        if kg is not None:
            kg.wake()


class GlobalHotkey:
    def __init__(
        self,
        spec: str,
        on_press: Callable[[], None],
        api=None,
        session=None,
    ) -> None:
        self.spec = spec
        self._session = session
        self._on_press = on_press
        self._api = api
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._thread_id: int | None = None
        self._reg_ok = False
        self.ok = False
        self.error = ""

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return self.ok
        if self._api is None:
            from engrama.osapi.session import detect

            sess = self._session or detect()
            try:
                if sess.platform == "win32":
                    self._api = _WinApi()
                elif sess.platform == "linux" and sess.kind == "x11":
                    self._api = _X11Api()
                elif sess.platform == "linux" and sess.kind == "wayland":
                    self.ok = False
                    self.error = "wayland"
                    return False
                else:
                    self.ok = False
                    self.error = "unsupported"
                    return False
            except Exception as exc:  # noqa: BLE001
                self.ok = False
                self.error = f"api indisponível: {exc}"
                return False
        try:
            self._mods, self._vk = parse_hotkey(self.spec)
        except ValueError as exc:
            self.ok = False
            self.error = str(exc)
            return False

        self._ready.clear()
        self._reg_ok = False
        self.error = ""
        self._thread = threading.Thread(target=self._run, name="engrama-hotkey", daemon=True)
        self._thread.start()
        if not self._ready.wait(1.0):
            self.ok = False
            self.error = "timeout ao registrar a hotkey"
            return False
        self.ok = self._reg_ok
        return self.ok

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        if thread.is_alive() and self._thread_id is not None:
            try:
                self._api.post_quit(self._thread_id)
            except Exception:  # noqa: BLE001
                pass
            thread.join(0.5)
        self.ok = False
        self._thread = None

    def _run(self) -> None:
        # Em Windows, threading.get_native_id() é o mesmo valor de GetCurrentThreadId().
        self._thread_id = threading.get_native_id()
        try:
            self._reg_ok = bool(self._api.register(HOTKEY_ID, self._mods, self._vk))
            if not self._reg_ok:
                self.error = "não foi possível registrar a hotkey (talvez já em uso)"
        except Exception as exc:  # noqa: BLE001
            self._reg_ok = False
            self.error = f"falha ao registrar a hotkey: {exc}"
        self._ready.set()
        if not self._reg_ok:
            return
        try:
            while True:
                hid = self._api.get_message()
                if hid is None:
                    break
                if hid == HOTKEY_ID:
                    try:
                        self._on_press()
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                self._api.unregister(HOTKEY_ID)
            except Exception:  # noqa: BLE001
                pass
