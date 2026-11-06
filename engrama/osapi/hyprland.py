"""IPC do Hyprland pelo socket de controle (.socket.sock): janela ativa."""
import json
import os
import socket
import time

from engrama.osapi import IPC_TIMEOUT_S, ActiveWindow, Rect

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


# --- M17: geometria do mundo, cursor e regras da janela do overlay --------------------------------------------

def _json(cmd: str, env=None, connect=None):
    raw = request(cmd, env, connect)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def monitors(env=None, connect=None) -> list[dict]:
    d = _json("j/monitors", env, connect)
    return [m for m in d if isinstance(m, dict)] if isinstance(d, list) else []


def clients(env=None, connect=None) -> list[dict]:
    d = _json("j/clients", env, connect)
    return [c for c in d if isinstance(c, dict)] if isinstance(d, list) else []


def _focused_monitor(mons: list[dict]) -> dict | None:
    for m in mons:
        if m.get("focused"):
            return m
    return mons[0] if mons else None


def parse_work_area(mons: list[dict]) -> Rect | None:
    """Área útil do monitor com foco, em pixels lógicos (já sem barras reservadas)."""
    m = _focused_monitor(mons)
    if m is None:
        return None
    try:
        scale = float(m.get("scale") or 1.0) or 1.0
        x, y = int(m["x"]), int(m["y"])
        w, h = int(round(int(m["width"]) / scale)), int(round(int(m["height"]) / scale))
        res = m.get("reserved") or [0, 0, 0, 0]
        left, top, right, bottom = (int(v) for v in res[:4])
        w, h = w - left - right, h - top - bottom
        return (x + left, y + top, w, h) if w > 0 and h > 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def parse_windows(client_list: list[dict], mons: list[dict], own_pid: int | None = None,
                  own_class: str = "") -> list[Rect]:
    """Retângulos (x, y, w, h) das janelas visíveis do monitor com foco, da mais próxima para a mais distante.

    Só geometria: nada de título, classe ou PID sai daqui. Filtra janelas não mapeadas, escondidas, de outro
    workspace, a própria janela e as sem área. A ordem aproxima o empilhamento pelo histórico de foco, com as
    flutuantes antes das lado a lado.
    """
    m = _focused_monitor(mons)
    if m is None:
        return []
    shown = set()
    try:
        shown.add(int((m.get("activeWorkspace") or {}).get("id")))
        sp = int((m.get("specialWorkspace") or {}).get("id") or 0)
        if sp:
            shown.add(sp)
        mid = m.get("id")
    except (TypeError, ValueError):
        return []
    keep = []
    for i, c in enumerate(client_list):
        try:
            if not c.get("mapped", True) or c.get("hidden", False):
                continue
            if own_pid and int(c.get("pid") or 0) == own_pid:
                continue
            if own_class and str(c.get("class") or "").lower() == own_class.lower():
                continue
            if c.get("monitor") is not None and mid is not None and int(c["monitor"]) != int(mid):
                continue
            if int((c.get("workspace") or {}).get("id")) not in shown:
                continue
            x, y = (int(v) for v in c["at"][:2])
            w, h = (int(v) for v in c["size"][:2])
            if w < 40 or h < 24:
                continue
            fh = int(c.get("focusHistoryID", 1 << 20))
            keep.append((0 if c.get("floating") else 1, fh if fh >= 0 else 1 << 20, i, (x, y, w, h)))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    keep.sort(key=lambda t: t[:3])
    return [t[3] for t in keep]


def cursor_pos(env=None, connect=None) -> tuple[int, int] | None:
    d = _json("j/cursorpos", env, connect)
    try:
        return (int(d["x"]), int(d["y"])) if isinstance(d, dict) else None
    except (KeyError, TypeError, ValueError):
        return None


def work_area(env=None, connect=None) -> Rect | None:
    return parse_work_area(monitors(env, connect))


def windows(env=None, connect=None, own_pid: int | None = None, own_class: str = "") -> list[Rect]:
    mons = monitors(env, connect)
    if not mons:
        return []
    return parse_windows(clients(env, connect), mons, own_pid, own_class)


def _ok(reply: bytes | None) -> bool:
    return bool(reply) and reply.strip() == b"ok"


# Regras da janela do overlay: o Hyprland 0.5x+ configura por Lua (`eval`), as versões antigas por `keyword`.
_LUA_RULE = ('hl.window_rule({{ match = {{ class = "^({cls})$" }}, float = true, pin = true, border_size = 0, '
             'no_shadow = true, no_blur = true, no_anim = true, rounding = 0, no_initial_focus = true }})')
_LEGACY_RULES = ("float", "pin", "noborder", "noshadow", "noblur", "noanim", "rounding 0", "noinitialfocus")


def apply_overlay_rules(cls: str, env=None, connect=None) -> bool:
    """Instala as regras da janela do overlay (flutuante, fixa, sem borda/sombra/desfoque/animação, sem foco inicial)."""
    if not cls or not all(ch.isalnum() or ch in "-_" for ch in cls):
        return False
    if _ok(request("eval " + _LUA_RULE.format(cls=cls), env, connect)):
        return True
    ok = False
    for rule in _LEGACY_RULES:
        ok = _ok(request(f"keyword windowrulev2 {rule},class:^({cls})$", env, connect)) or ok
    return ok


def move_window(cls: str, x: int, y: int, env=None, connect=None) -> bool:
    """Move a janela do overlay (selecionada pela classe) para (x, y); tenta a sintaxe Lua e depois a antiga.

    O tamanho não é tocado: no Wayland quem manda nele é o buffer do cliente."""
    if not cls or not all(ch.isalnum() or ch in "-_" for ch in cls):
        return False
    x, y = int(x), int(y)
    sel = f"class:{cls}"
    if _ok(request(f"dispatch hl.dsp.window.move({{ x = {x}, y = {y}, window = \"{sel}\" }})", env, connect)):
        return True
    return _ok(request(f"dispatch movewindowpixel exact {x} {y},{sel}", env, connect))
