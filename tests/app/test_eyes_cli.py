import json
import os
import subprocess
import sys
import time

import pytest

ENV = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}


def test_eyes_toggle_without_instance_exits_1(tmp_path):
    r = subprocess.run([sys.executable, "-m", "engrama", "--eyes", "toggle", "--data-dir", str(tmp_path)],
                       env=ENV, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1
    assert not (tmp_path / "engrama.lock").exists() or (tmp_path / "engrama.lock").read_bytes() == b""


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="SIGUSR1")
def test_sigusr1_toggles_eyes_in_main_loop(tmp_path):
    d = tmp_path / "d"
    app = subprocess.Popen([sys.executable, "-m", "engrama", "--no-llm", "--seconds", "6",
                            "--data-dir", str(d)], env=ENV)
    try:
        from engrama.app.instance import InstanceLock
        t0 = time.monotonic()
        while InstanceLock.holder_pid(d) is None and time.monotonic() - t0 < 30:
            time.sleep(0.1)
        time.sleep(1.5)   # handler is installed after the lock; let the window come up
        r = subprocess.run([sys.executable, "-m", "engrama", "--eyes", "toggle", "--data-dir", str(d)],
                           env=ENV, timeout=60)
        assert r.returncode == 0
        app.wait(timeout=60)
    finally:
        if app.poll() is None:
            app.kill()
    assert json.loads((d / "config.json").read_text())["eyes_closed"] is True
