import os
import subprocess
import time
import urllib.request
from pathlib import Path

from engrama.config import Config

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _default_ping(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/version", timeout=timeout):
            return True
    except Exception:
        return False


class OllamaServer:
    """Starts/stops `ollama serve` with everything pointed at the drive set in Config (never C:)."""

    def __init__(self, cfg: Config, popen=subprocess.Popen, ping=None, start_timeout: float = 20.0):
        self.cfg = cfg
        self._popen = popen
        self._ping = ping or _default_ping
        self._start_timeout = start_timeout
        self._proc = None

    @property
    def started_by_us(self) -> bool:
        return self._proc is not None

    def running(self) -> bool:
        return bool(self._ping(self.cfg.ollama_url, 1))

    def available(self) -> bool:
        return Path(self.cfg.ollama_exe).exists() or self.running()

    def start(self) -> bool:
        if self.running():
            return True
        if not Path(self.cfg.ollama_exe).exists():
            return False
        env = dict(os.environ)
        env.update(USERPROFILE=str(self.cfg.ollama_home), HOME=str(self.cfg.ollama_home),
                   OLLAMA_MODELS=str(self.cfg.ollama_models))
        try:
            self._proc = self._popen([str(self.cfg.ollama_exe), "serve"], env=env,
                                     creationflags=CREATE_NO_WINDOW,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self._proc = None
            return False
        deadline = time.monotonic() + self._start_timeout
        while time.monotonic() < deadline:
            if self.running():
                return True
            time.sleep(0.25)
        return False

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass

