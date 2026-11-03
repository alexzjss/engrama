"""IPC do Sway (protocolo i3-ipc): janela ativa."""
import json
import os
import socket
import struct
import time

from engrama.osapi import IPC_TIMEOUT_S, ActiveWindow

_MAGIC = b"i3-ipc"
_GET_TREE = 4
_MAX_REPLY = 8 << 20


def socket_path(env) -> str | None:
    return env.get("SWAYSOCK") or None


def _connect(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(IPC_TIMEOUT_S)
    s.connect(path)
    return s


def _read_exact(sock, n: int, deadline: float) -> bytes | None:
    buf = b""
    while len(buf) < n:
        if time.monotonic() > deadline:
            return None
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def request(msg_type: int, payload: bytes = b"", env=None, connect=None,
            timeout: float = IPC_TIMEOUT_S) -> bytes | None:
    path = socket_path(os.environ if env is None else env)
    if path is None:
        return None
    sock = None
    try:
        sock = (connect or _connect)(path)
        sock.settimeout(timeout)
        deadline = time.monotonic() + timeout
        sock.sendall(_MAGIC + struct.pack("<II", len(payload), msg_type) + payload)
        head = _read_exact(sock, 14, deadline)
        if head is None or head[:6] != _MAGIC:
            return None
        length, _typ = struct.unpack("<II", head[6:])
        if length > _MAX_REPLY:
            return None
        return _read_exact(sock, length, deadline)
    except (OSError, ValueError, struct.error):
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _find_focused(node, depth=0):
    if not isinstance(node, dict) or depth > 64:
        return None
    if node.get("focused") is True:
        return node
    for key in ("nodes", "floating_nodes"):
        for child in node.get(key) or ():
            found = _find_focused(child, depth + 1)
            if found is not None:
                return found
    return None


def active_window(env=None, connect=None) -> ActiveWindow | None:
    raw = request(_GET_TREE, b"", env, connect)
    if not raw:
        return None
    try:
        node = _find_focused(json.loads(raw))
    except (ValueError, RecursionError):
        return None
    if node is None:
        return None
    try:
        pid = node.get("pid")
        pid = int(pid) if pid is not None and int(pid) > 0 else None
        cls = node.get("app_id") or (node.get("window_properties") or {}).get("class") or ""
        fs = node.get("fullscreen_mode")
        r = node.get("rect")
        rect = (int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])) if r else None
        return ActiveWindow(pid=pid, cls=str(cls).lower(), title=str(node.get("name") or ""),
                            fullscreen=(int(fs) > 0) if fs is not None else None, rect=rect)
    except (TypeError, ValueError, KeyError):
        return None
