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
