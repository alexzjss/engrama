"""Tempo ocioso da sessão por `gdbus` (Mutter IdleMonitor, org.freedesktop.ScreenSaver)."""
import re
import subprocess

from engrama.osapi import GDBUS_TIMEOUT_S

# (nome, args do gdbus, fator para ms)
# Mutter devolve milissegundos. org.freedesktop.ScreenSaver.GetSessionIdleTime, na
# implementação do KDE (kscreenlocker), devolve segundos; por isso o fator 1000.
_BACKENDS = (
    ("mutter", ["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor",
                "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
                "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"], 1),
    ("screensaver", ["gdbus", "call", "--session", "--dest", "org.freedesktop.ScreenSaver",
                     "--object-path", "/org/freedesktop/ScreenSaver",
                     "--method", "org.freedesktop.ScreenSaver.GetSessionIdleTime"], 1000),
)
_REPLY = re.compile(r"\(\s*u?int(?:32|64)\s+(\d+)\s*,?\s*\)")

_working: int | None = None


def _reset() -> None:
    global _working
    _working = None



def _try(index: int, run, timeout: float) -> int | None:
    _name, args, factor = _BACKENDS[index]
    try:
        proc = run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    m = _REPLY.search(proc.stdout or "")
    return int(m.group(1)) * factor if m else None


def idle_ms(run=None, timeout: float = GDBUS_TIMEOUT_S) -> int | None:
    """Milissegundos de ociosidade ou None. Lembra o backend que funcionou."""
    global _working
    run = run or subprocess.run
    order = [_working] if _working is not None else []
    order += [i for i in range(len(_BACKENDS)) if i != _working]
    for i in order:
        value = _try(i, run, timeout)
        if value is not None:
            _working = i
            return value
    _working = None
    return None
