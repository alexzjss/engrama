"""Cliente Wayland mínimo (Python puro): ociosidade via ext_idle_notifier_v1.

Só stdlib. Sem thread própria: o socket só é lido em start() e idle_seconds().
"""
import os
import select
import socket
import struct
import time

from engrama.osapi import IPC_TIMEOUT_S

_MAX_MSG = 4096
_START_TOTAL_S = 1.0

_DISPLAY = 1
_REGISTRY = 2
_CALLBACK = 3


def encode(obj: int, opcode: int, payload: bytes = b"") -> bytes:
    return struct.pack("<II", obj, ((8 + len(payload)) << 16) | opcode) + payload


def wl_string(s: str) -> bytes:
    raw = s.encode() + b"\x00"
    return struct.pack("<I", len(raw)) + raw + b"\x00" * (-len(raw) % 4)


def decode(buf: bytes) -> tuple[list[tuple[int, int, bytes]], bytes]:
    """Mensagens completas e o resto. ValueError se o tamanho for inválido."""
    msgs = []
    pos = 0
    while len(buf) - pos >= 8:
        obj, word = struct.unpack_from("<II", buf, pos)
        size, op = word >> 16, word & 0xFFFF
        if size < 8 or size > _MAX_MSG:
            raise ValueError("bad message size")
        if len(buf) - pos < size:
            break
        msgs.append((obj, op, bytes(buf[pos + 8:pos + size])))
        pos += size
    return msgs, bytes(buf[pos:])


def socket_path(env) -> str | None:
    name = env.get("WAYLAND_DISPLAY")
    if not name:
        return None
    if os.path.isabs(name):
        return name
    rt = env.get("XDG_RUNTIME_DIR")
    return os.path.join(rt, name) if rt else None


def _default_connect(path: str) -> socket.socket:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(IPC_TIMEOUT_S)
    try:
        s.connect(path)
    except BaseException:
        s.close()
        raise
    return s


def _parse_global(pl: bytes):
    name, slen = struct.unpack_from("<II", pl, 0)
    iface = pl[8:8 + slen].rstrip(b"\x00").decode("utf-8", "replace")
    off = 8 + slen + (-slen % 4)
    (ver,) = struct.unpack_from("<I", pl, off)
    return name, iface, ver


class IdleWatcher:
    def __init__(self, timeout_s: float, env=None, connect=None, now=time.monotonic) -> None:
        self.timeout_s = float(timeout_s)
        self._env = os.environ if env is None else env
        self._connect = connect or _default_connect
        self._now = now
        self._sock = None
        self._buf = b""
        self._broken = False
        self._idled_at = None
        self._notif_id = 0
        self._next_id = 2

    def _alloc(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    def _fail(self) -> bool:
        self._broken = True
        self.close()
        return False

    def start(self) -> bool:
        try:
            path = socket_path(self._env)
            if not path:
                return False
            self._sock = self._connect(path)
            if self._sock is None:
                return False
            reg, cb = self._alloc(), self._alloc()
            self._sock.sendall(encode(_DISPLAY, 1, struct.pack("<I", reg))
                               + encode(_DISPLAY, 0, struct.pack("<I", cb)))
            globals_ = {}
            deadline = time.monotonic() + _START_TOTAL_S
            done = False
            while not done:
                left = deadline - time.monotonic()
                if left <= 0:
                    return self._fail()
                r, _, _ = select.select([self._sock], [], [], min(IPC_TIMEOUT_S, left))
                if not r:
                    continue
                data = self._sock.recv(4096)
                if not data:
                    return self._fail()
                msgs, self._buf = decode(self._buf + data)
                for obj, op, pl in msgs:
                    if obj == _DISPLAY and op == 0:
                        return self._fail()
                    if obj == reg and op == 0:
                        name, iface, ver = _parse_global(pl)
                        globals_.setdefault(iface, (name, ver))
                    elif obj == cb and op == 0:
                        done = True
            if "wl_seat" not in globals_ or "ext_idle_notifier_v1" not in globals_:
                return self._fail()
            seat = self._alloc()
            notifier = self._alloc()
            self._notif_id = self._alloc()
            sn, sv = globals_["wl_seat"]
            nn, nv = globals_["ext_idle_notifier_v1"]
            for gname, iface, ver, nid in ((sn, "wl_seat", min(sv, 1), seat),
                                           (nn, "ext_idle_notifier_v1", min(nv, 1), notifier)):
                self._sock.sendall(encode(reg, 0, struct.pack("<I", gname) + wl_string(iface)
                                          + struct.pack("<II", ver, nid)))
            ms = max(1, int(self.timeout_s * 1000))
            self._sock.sendall(encode(notifier, 1, struct.pack("<III", self._notif_id, ms, seat)))
            self._sock.setblocking(False)
            self._dispatch_pending()
            return not self._broken
        except (OSError, ValueError, struct.error):
            return self._fail()

    def _dispatch_pending(self) -> None:
        msgs, self._buf = decode(self._buf)
        for obj, op, _pl in msgs:
            if obj == _DISPLAY and op == 0:
                self._broken = True
            elif obj == self._notif_id and op == 0:
                self._idled_at = self._now()
            elif obj == self._notif_id and op == 1:
                self._idled_at = None

    def idle_seconds(self) -> float | None:
        if self._broken or self._sock is None:
            return None
        try:
            while True:
                try:
                    data = self._sock.recv(4096)
                except (BlockingIOError, socket.timeout):
                    break
                if not data:
                    self._broken = True
                    break
                self._buf += data
                self._dispatch_pending()
                if self._broken:
                    break
            if not self._broken:
                self._dispatch_pending()
        except (OSError, ValueError, struct.error):
            self._broken = True
        if self._broken:
            self.close()
            return None
        if self._idled_at is None:
            return 0.0
        return self.timeout_s + max(0.0, self._now() - self._idled_at)

    def close(self) -> None:
        s, self._sock = self._sock, None
        if s is not None:
            try:
                s.close()
            except OSError:
                pass
