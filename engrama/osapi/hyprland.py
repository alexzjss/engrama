"""IPC do Hyprland pelo socket de controle (.socket.sock): janela ativa."""
import json
import os
import socket
import time

from engrama.osapi import IPC_TIMEOUT_S, ActiveWindow

_MAX_REPLY = 1 << 20


def socket_path(env) -> str | None:
    sig = env.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    candidates = []
    runtime = env.get("XDG_RUNTIME_DIR")
    if runtime:
        candidates.append(os.path.join(runtime, "hypr", sig, ".socket.sock"))
    candidates.append(os.path.join("/tmp", "hypr", sig, ".socket.sock"))   # caminho antigo
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def _connect(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(IPC_TIMEOUT_S)
    s.connect(path)
    return s


def request(cmd: str, env=None, connect=None, timeout: float = IPC_TIMEOUT_S) -> bytes | None:
    """Escreve `cmd` e lê até EOF; qualquer falha ou tempo estourado devolve None."""
    path = socket_path(os.environ if env is None else env)
    if path is None:
        return None
    sock = None
    try:
        sock = (connect or _connect)(path)
        sock.settimeout(timeout)
        deadline = time.monotonic() + timeout
        sock.sendall(cmd.encode())
        chunks, size = [], 0
        while True:
            if time.monotonic() > deadline:
                return None
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
            size += len(data)
            if size > _MAX_REPLY:
                return None
        return b"".join(chunks)
    except (OSError, ValueError):
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def active_window(env=None, connect=None) -> ActiveWindow | None:
    raw = request("j/activewindow", env, connect)
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(d, dict) or not d:
        return None
    try:
        pid = d.get("pid")
        pid = int(pid) if pid is not None and int(pid) > 0 else None
        fs = d.get("fullscreen")
        fullscreen = (int(fs) >= 2) if fs is not None else None   # 1 = maximizada, 2/3 = tela cheia
        rect = None
        at, size = d.get("at"), d.get("size")
        if at and size and len(at) == 2 and len(size) == 2:
            rect = (int(at[0]), int(at[1]), int(size[0]), int(size[1]))
        return ActiveWindow(pid=pid, cls=str(d.get("class") or "").lower(),
                            title=str(d.get("title") or ""), fullscreen=fullscreen, rect=rect)
    except (TypeError, ValueError):
        return None
