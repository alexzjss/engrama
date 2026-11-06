import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import bench  # noqa: E402


@pytest.fixture(autouse=True)
def dummy_sdl(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")


@pytest.mark.slow
def test_bench_app_steady_state_config(tmp_path):
    d = tmp_path / "steady"
    d.mkdir()
    r = bench.bench_app(3.0, d)
    assert r["mean_cpu_percent"] >= 0.0
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
    assert cfg["perception_asked"] is True
    assert cfg["permissions"] and not any(cfg["permissions"].values())
    d2 = tmp_path / "first"
    d2.mkdir()
    bench.bench_app(3.0, d2, first_use=True)
    assert not (d2 / "config.json").exists() or not json.loads((d2 / "config.json").read_text(encoding="utf-8")).get("perception_asked")


@pytest.mark.slow
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc only")
def test_bench_threads_key_on_linux(tmp_path):
    d = tmp_path / "thr"
    d.mkdir()
    r = bench.bench_app(3.0, d, threads=True)
    assert isinstance(r["threads"], dict) and r["threads"]
    assert all(isinstance(v, float) for v in r["threads"].values())
    assert "threads" not in bench.bench_app(1.0, d)
