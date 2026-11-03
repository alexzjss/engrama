import subprocess
import sys

from engrama.app.host import main
from engrama.app.instance import InstanceLock

SNIPPET = ("import sys; from pathlib import Path; from engrama.app.instance import InstanceLock; "
           "l = InstanceLock(Path(sys.argv[1])); sys.exit(0 if l.acquire() else 1)")


def _other(d):
    return subprocess.run([sys.executable, "-c", SNIPPET, str(d)]).returncode


def test_second_fails_then_succeeds_after_release(tmp_path):
    a, b = InstanceLock(tmp_path), InstanceLock(tmp_path)
    assert a.acquire()
    assert not b.acquire()
    a.release()
    assert b.acquire()
    b.release()


def test_context_manager(tmp_path):
    with InstanceLock(tmp_path):
        assert not InstanceLock(tmp_path).acquire()
    other = InstanceLock(tmp_path)
    assert other.acquire()
    other.release()


def test_different_dirs(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    a, b = InstanceLock(tmp_path / "x"), InstanceLock(tmp_path / "y")
    assert a.acquire() and b.acquire()
    a.release()
    b.release()


def test_stale_file_does_not_block(tmp_path):
    (tmp_path / "engrama.lock").write_text("99999")
    lk = InstanceLock(tmp_path)
    assert lk.acquire()
    lk.release()


def test_other_process(tmp_path):
    lk = InstanceLock(tmp_path)
    assert lk.acquire()
    assert _other(tmp_path) == 1
    lk.release()
    assert _other(tmp_path) == 0


def test_main_refuses_when_held(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    d = tmp_path / "fresh"
    d.mkdir()
    with InstanceLock(d):
        assert main(["--data-dir", str(d), "--no-llm", "--frames", "1"]) == 1
    assert "already running" in capsys.readouterr().err
    assert not (d / "config.json").exists()
