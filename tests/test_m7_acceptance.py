"""M7 acceptance: host wiring for digital requests and the overlay, M6 saves, lab regression and the overlay budget."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from engrama.app.desktop import FakeDesktop, NullDesktop
from engrama.app.host import Host, open_in_display_mode
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window
from engrama.clock import SimClock
from engrama.config import Config
from engrama.lab.cli import main as lab_main
from engrama.vocab import DIGITAL_IDS

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "recipes" / "minimal-v1.toml"
FIXTURE = ROOT / "tests" / "fixtures" / "m6_sim_1d_seed1_attentive.json"


class FakeTime:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


@pytest.fixture
def make_host():
    made = []

    def make(tmp, ft=None, seed=7):
        ft = ft or FakeTime()
        h = Host(Config(data_dir=tmp), tmp, MINIMAL, seed=seed, clock=SimClock(1.0, now_fn=ft),
                 ram_free_mb_fn=lambda: 8000.0)
        made.append(h)
        return h, ft

    yield make
    for h in made:
        h.stop()


def run(h, ft, n, step=1.0):
    for _ in range(n):
        ft.tick(step)
        h.pump(1)


def test_m6_save_loads_without_digital_or_display_mode(tmp_path, make_host):
    h, ft = make_host(tmp_path)
    run(h, ft, 3)
    h._save()
    meta = json.loads((tmp_path / "host.json").read_text(encoding="utf-8"))
    assert "digital" in meta
    meta.pop("digital")                                    # what an M6 host.json looks like
    (tmp_path / "host.json").write_text(json.dumps(meta), encoding="utf-8")
    cfg = Config(data_dir=tmp_path)
    cfg.save(tmp_path / "config.json")
    raw = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    raw.pop("display_mode", None)                          # and an M6 config.json
    (tmp_path / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    assert Config.load(tmp_path / "config.json").display_mode == "terrarium"
    h2, ft2 = make_host(tmp_path, FakeTime(ft.t + 5))
    run(h2, ft2, 3)
    snap = h2.snapshot()
    assert snap.digital_request == "" and snap.fullscreen is False and snap.theme == ""


def test_open_request_in_snapshot_and_cleared_when_fulfilled(tmp_path, make_host):
    h, ft = make_host(tmp_path)
    run(h, ft, 2)
    thanks = []
    h.on_digital_thanks = thanks.append
    d, k = h._digital, h.runtime.kernel
    d.open, d.opened_t = "cache", float(k.t)
    run(h, ft, 1)
    assert h.snapshot().digital_request == "cache"
    assert h.fulfill_digital("ram") is False               # a different item keeps it open
    assert h.snapshot().digital_request == "cache" and thanks == []
    assert h.fulfill_digital("cache") is True
    assert h.snapshot().digital_request == "" and thanks == ["cache"]
    assert h.fulfill_digital("cache") is False


def test_request_opens_on_ask_attention_and_says_a_line(tmp_path, make_host, monkeypatch):
    from engrama import balance
    monkeypatch.setattr(balance, "DIGITAL_REQUEST_P", 1.0)
    h, ft = make_host(tmp_path)
    run(h, ft, 2)
    asked = []
    h.on_digital_ask = asked.append
    h._prev_action = "idle"
    h.runtime.kernel._action = "ask_attention"
    h._emit_changes(ft.t)
    assert len(asked) == 1 and asked[0] in DIGITAL_IDS and h._digital.open == asked[0]


def test_digital_state_persists_in_host_json(tmp_path, make_host):
    h, ft = make_host(tmp_path)
    run(h, ft, 2)
    d, k = h._digital, h.runtime.kernel
    d.open, d.opened_t = "update", float(k.t)
    h._save()
    h2, ft2 = make_host(tmp_path, FakeTime(ft.t + 1))
    assert h2._digital.open == "update"


def test_config_overlay_reopens_in_overlay_with_fake_desktop():
    cfg = Config()
    cfg.display_mode = "overlay"
    cfg.perception_asked = True
    w = Window(lambda: Snapshot(look={"seed": 3}, stage="adult"), lambda k, d=None: None)
    w.desktop, w.config, w.save_config = FakeDesktop(work=(0, 0, 1280, 680)), cfg, lambda: None
    assert open_in_display_mode(w, cfg) is True and w.mode == "overlay"
    w.frame(1.0)


def test_config_overlay_without_desktop_stays_in_terrarium():
    cfg = Config()
    cfg.display_mode = "overlay"
    cfg.perception_asked = True
    w = Window(lambda: Snapshot(look={"seed": 3}, stage="adult"), lambda k, d=None: None)
    w.desktop, w.config, w.save_config = NullDesktop(), cfg, lambda: None
    assert open_in_display_mode(w, cfg) is False and w.mode == "terrarium"


def test_terrarium_config_does_not_touch_the_mode():
    cfg = Config()
    w = Window(lambda: Snapshot(look={"seed": 3}, stage="adult"), lambda k, d=None: None)
    assert open_in_display_mode(w, cfg) is False and w.mode == "terrarium"


@pytest.mark.slow
def test_lab_metrics_identical_to_m6(capsys):
    assert FIXTURE.exists()
    assert lab_main(["sim", "--recipe", str(ROOT / "recipes" / "default-v1.toml"), "--days", "1", "--seed", "1",
                     "--profile", "attentive"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got == json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_overlay_bench_within_budget(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "bench.py"), "--overlay", "--seconds", "20",
                          "--data-dir", str(tmp_path / "bench_app")],
                         cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[-500:]
    res = json.loads(out.stdout[out.stdout.index("{"):])
    assert res["overlay_active"] is True
    assert res["peak_rss_mb"] <= 150.0
    assert res["mean_cpu_percent"] <= 2.0
