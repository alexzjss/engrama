"""Single-instance guard: an OS-level exclusive lock on <data_dir>/engrama.lock.

The lock dies with the process, so a stale file from a crash never blocks.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


class InstanceLock:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "engrama.lock"
        self._fh = None

    def acquire(self) -> bool:
        if self._fh is not None:
            return True
        fh = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(self.path, "a+b")
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if fh is not None:
                fh.close()
            return False
        try:   # informational only
            fh.seek(0)
            fh.truncate()
            fh.write(str(os.getpid()).encode())
            fh.flush()
        except OSError:
            pass
        self._fh = fh
        return True

    @staticmethod
    def holder_pid(data_dir: Path) -> int | None:
        """PID gravado no lock se ele estiver preso por outro processo; senão None (só POSIX)."""
        if sys.platform == "win32":
            return None
        path = Path(data_dir) / "engrama.lock"
        try:
            fh = open(path, "rb")
        except OSError:
            return None
        try:
            import fcntl
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError:
                pass   # preso por outro: segue para ler o PID
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return None
            try:
                return int(fh.read().strip() or 0) or None
            except ValueError:
                return None
        finally:
            fh.close()

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            fh.close()

    def __enter__(self) -> "InstanceLock":
        if not self.acquire():
            raise OSError("engrama is already running for this data dir")
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def _is_engrama(pid: int) -> bool:
    try:
        import psutil
        return any("engrama" in part.lower() for part in psutil.Process(pid).cmdline())
    except Exception:
        return False


def send_eyes_toggle(data_dir: Path, kill=os.kill, is_engrama=None) -> int:
    """`engrama --eyes toggle`: sinaliza (SIGUSR1) a instância aberta. 0 ok, 1 sem instância, 2 Windows."""
    from engrama.app import i18n
    if sys.platform == "win32":
        print(i18n.t("cli.eyes.windows"))
        return 2
    pid = InstanceLock.holder_pid(Path(data_dir))
    check = is_engrama or _is_engrama
    if pid is None or not check(pid):
        print(i18n.t("cli.eyes.not_running"), file=sys.stderr)
        return 1
    import signal
    try:
        kill(pid, signal.SIGUSR1)
    except OSError:
        print(i18n.t("cli.eyes.not_running"), file=sys.stderr)
        return 1
    print(i18n.t("cli.eyes.toggled"))
    return 0
