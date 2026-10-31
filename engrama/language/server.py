import os
import subprocess
import time
import urllib.request

from engrama.core.config import Config

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _default_ping(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/version", timeout=timeout):
            return True
    except Exception:
        return False


class OllamaServer:
    def __init__(self, cfg: Config, popen=subprocess.Popen, ping=None):
        self.cfg = cfg
        self._popen = popen
        self._ping = ping or _default_ping
        self.owned = False
        self._proc = None

    def running(self) -> bool:
        return bool(self._ping(self.cfg.ollama_url, 1))

    def available(self) -> bool:
        return self.cfg.ollama_exe.exists() or self.running()

    def start(self) -> bool:
        if self.running():
            return True
        if not self.cfg.ollama_exe.exists():
            return False
        env = dict(os.environ)
        env.update(USERPROFILE=str(self.cfg.ollama_home), HOME=str(self.cfg.ollama_home),
                   OLLAMA_MODELS=str(self.cfg.ollama_models))
        self._proc = self._popen([str(self.cfg.ollama_exe), "serve"], env=env,
                                 creationflags=CREATE_NO_WINDOW,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.owned = True
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.running():
                return True
            time.sleep(0.25)
        return False

    def stop(self) -> None:
        if self.owned and self._proc is not None:
            self._proc.terminate()
            self._proc = None
            self.owned = False
