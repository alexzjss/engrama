import dataclasses
import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from engrama import balance as B
from engrama.app.host import Host, to_viz
from engrama.app.snapshot import ModuleView, ProposalView, Snapshot, Viz
from engrama.clock import SimClock
from engrama.config import Config
from engrama.kernel.kernel import Kernel
from engrama.lab.runtime import Runtime
from engrama.mind.contracts import VizSpec

RECIPES = Path(__file__).resolve().parents[2] / "recipes"
MINIMAL, DEFAULT = RECIPES / "minimal-v1.toml", RECIPES / "default-v1.toml"


class FakeTime:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


@pytest.fixture
def hosts():
    made = []

    def make(tmp, ft, recipe=MINIMAL, seed=7, scale=1.0, **kw):
        h = Host(Config(data_dir=tmp), tmp, recipe, seed=seed, clock=SimClock(scale, now_fn=ft),
                 ram_free_mb_fn=lambda: 8000.0, **kw)
        made.append(h)
        return h

    yield make
    for h in made:
        h.stop()


def run(h, ft, n, step=1.0):
    for _ in range(n):
        ft.tick(step)
        h.pump(1)


def test_post_reaches_kernel_once(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    seen = []
    orig = h.runtime.tick
    h.runtime.tick = lambda dt, evs: (seen.append([(e.kind, e.t) for e in evs]), orig(dt, evs))[1]
    h.post("pet")
    run(h, ft, 3)
    assert [len(x) for x in seen] == [1, 0, 0]
    assert seen[0][0][0] == "pet"


def test_unknown_post_is_dropped(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    h.post("nonsense", {"x": 1})
    run(h, ft, 2)


def test_snapshot_is_immutable_copy(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft, recipe=DEFAULT)
    h.want_viz = True
    run(h, ft, 3)
    s = h.snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.stage = "x"
    before = h.runtime.kernel.needs.values["fome"]
    s.needs["fome"] = -123.0
    s.look["body"] = "zzz"
    assert h.runtime.kernel.needs.values["fome"] == before
    run(h, ft, 1)
    s2 = h.snapshot()
    assert s2.needs["fome"] != -123.0 and s2.look.get("body") != "zzz"
    assert s2 is not s and s2.needs is not s.needs
    assert isinstance(s2.proposals, tuple) and all(isinstance(p, ProposalView) for p in s2.proposals)
    assert all(isinstance(m, ModuleView) for m in s2.modules) and s2.recipe_name == "default-v1"

    def no_arrays(x):
        assert not isinstance(x, (np.ndarray, np.generic))
        if isinstance(x, dict):
            [no_arrays(v) for v in x.values()]
        elif isinstance(x, (list, tuple)):
            [no_arrays(v) for v in x]
        elif dataclasses.is_dataclass(x):
            [no_arrays(getattr(x, f.name)) for f in dataclasses.fields(x)]
    no_arrays(s2)
    assert s2.viz and all(isinstance(v, Viz) for vs in s2.viz.values() for v in vs)
    # mutating a viz payload does not leak into the next snapshot
    snn = next(vs for vs in s2.viz.values() if vs)
    snn[0].data.clear() if isinstance(snn[0].data, (dict, list)) else None
    ft.tick(2.0); h.pump(1)


def test_viz_only_when_wanted_and_throttled(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft, recipe=DEFAULT)
    run(h, ft, 2)
    assert h.snapshot().viz == {}
    h.want_viz = True
    run(h, ft, 1)
    assert h.snapshot().viz
    calls = []
    for m in h.runtime.scheduler.modules().values():
        orig = m.viz
        m.viz = lambda o=orig: (calls.append(1), o())[1]
    for _ in range(10):
        ft.tick(0.1); h.pump(1)
    assert len(calls) <= len(h.runtime.scheduler.modules())   # one collection at most in 1 s


def test_surprise_zero_without_snn(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    run(h, ft, 3)
    s = h.snapshot()
    assert s.surprise == 0.0 and s.familiarity == 0.0


def test_egg_hatches_after_clicks(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    got = []
    h.on_event = lambda kind, data: got.append((kind, data))
    assert h.snapshot().stage == "egg"
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 2)
    s = h.snapshot()
    assert s.stage == "baby"
    assert ("hatch", {"stage": "baby"}) in got and not [g for g in got if g[0] == "evolve"]


def test_evolve_and_action_change_events(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft, scale=60.0)
    got = []
    h.on_event = lambda kind, data: got.append((kind, data))
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 600, step=5.0)
    kinds = {g[0] for g in got}
    assert "action_change" in kinds and "hatch" in kinds
    ac = next(d for k, d in got if k == "action_change")
    assert set(ac) == {"from", "to"} and ac["from"] != ac["to"]


def test_callback_exception_does_not_stop_sim(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)

    def boom(*a):
        raise RuntimeError("ui bug")
    h.on_event = boom
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 3)
    assert h.snapshot().stage == "baby"


def test_autosave_and_resume(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 2)
    assert not (tmp_path / "save" / "meta.json").exists()
    ft.tick(B.AUTOSAVE_S)
    h.pump(1)
    assert (tmp_path / "save" / "meta.json").exists()
    assert json.loads((tmp_path / "host.json").read_text())["seed"] == 7
    h.stop()
    h2 = hosts(tmp_path, ft, seed=999)
    assert h2.snapshot().stage == "baby" and h2.runtime.seed == 7
    assert h2.runtime.kernel.t == pytest.approx(h.runtime.kernel.t)


def test_offline_catchup_once(tmp_path, hosts, monkeypatch):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    run(h, ft, 3)
    h.stop()
    t_saved = h.runtime.kernel.t
    calls = []
    orig = Kernel.offline_catchup
    monkeypatch.setattr(Kernel, "offline_catchup", lambda self, s: (calls.append(s), orig(self, s))[1])
    ft.tick(7200.0)
    h2 = hosts(tmp_path, ft)
    assert calls == [pytest.approx(7200.0)]
    assert h2.runtime.kernel.t == pytest.approx(t_saved + 7200.0)
    run(h2, ft, 3)
    assert len(calls) == 1


def test_fresh_creature_has_no_catchup(tmp_path, hosts, monkeypatch):
    calls = []
    monkeypatch.setattr(Kernel, "offline_catchup", lambda self, s: calls.append(s))
    hosts(tmp_path, FakeTime())
    assert calls == []


def test_wall_jump_is_capped(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    h.pump(1)
    t0 = h.runtime.kernel.t
    ft.tick(3600.0)
    h.pump(1)
    assert 0 < h.runtime.kernel.t - t0 <= 5.0 + 1e-9
    # and a jump under time_scale 10 is capped at 5 s x 10
    h.set_time_scale(10.0)
    t1 = h.runtime.kernel.t
    ft.tick(3600.0)
    h.pump(1)
    assert h.runtime.kernel.t - t1 <= 50.0 + 1e-9


def test_stop_saves_and_joins_within_3s(tmp_path):
    h = Host(Config(data_dir=tmp_path), tmp_path, MINIMAL, seed=3, ram_free_mb_fn=lambda: 8000.0)
    h.start()
    stop_posting = threading.Event()

    def spam():
        while not stop_posting.is_set():
            h.post("pet")
            time.sleep(0.001)   # a busy-spin starves the GIL-released file I/O of the save
    th = threading.Thread(target=spam, daemon=True)
    th.start()
    time.sleep(0.3)
    t0 = time.time()
    h.stop(timeout=3.0)
    assert time.time() - t0 < 3.0
    stop_posting.set(); th.join()
    assert h._thread is not None and not h._thread.is_alive()
    rt = Runtime.load(tmp_path / "save")     # intact and loadable
    assert rt.seed == 3
    assert (tmp_path / "explog.sqlite").exists()


def test_thread_runs_and_publishes(tmp_path):
    h = Host(Config(data_dir=tmp_path), tmp_path, MINIMAL, seed=3, ram_free_mb_fn=lambda: 8000.0)
    h.start()
    try:
        deadline = time.time() + 5
        while h.snapshot().t <= 0 and time.time() < deadline:
            time.sleep(0.05)
        assert h.snapshot().t > 0
    finally:
        h.stop()


def test_new_creature_gets_random_seed_saved(tmp_path, hosts):
    a, b = tmp_path / "a", tmp_path / "b"
    ha = hosts(a, FakeTime(), seed=None)
    hb = hosts(b, FakeTime(), seed=None)
    sa = json.loads((a / "host.json").read_text())["seed"]
    sb = json.loads((b / "host.json").read_text())["seed"]
    assert isinstance(sa, int) and ha.runtime.seed == sa and hb.runtime.seed == sb
    assert sa != sb
    h2 = hosts(a, FakeTime(), seed=None)
    assert h2.runtime.seed == sa


def test_to_viz_copies_and_plain():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    v = to_viz(VizSpec("heatmap", "h", {"m": arr, "n": np.float64(2.0), "t": (1, 2)}))
    assert v == Viz("heatmap", "h", {"m": [[1.0, 2.0], [3.0, 4.0]], "n": 2.0, "t": [1, 2]})
    arr[0, 0] = 99
    assert v.data["m"][0][0] == 1.0


# ---- rest mode in the host -------------------------------------------------------------------------

def test_manual_rest(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    changes = []
    h.on_rest_change = lambda on, why: changes.append((on, why))
    run(h, ft, 1)
    h.set_rest(True)
    run(h, ft, 1)
    s = h.snapshot()
    assert s.resting and s.rest_reason == "manual" and h.runtime.scheduler.resting
    h.set_rest(False)
    run(h, ft, 1)
    assert not h.snapshot().resting and not h.runtime.scheduler.resting
    assert changes == [(True, "manual"), (False, "")]


def test_fullscreen_rest_and_exit(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    h.post("fullscreen_on")
    run(h, ft, 2)
    s = h.snapshot()
    assert s.resting and s.rest_reason == "fullscreen"
    h.post("fullscreen_off")
    run(h, ft, 2)
    assert not h.snapshot().resting


def test_low_ram_rest(tmp_path):
    ft = FakeTime(); ram = {"v": 8000.0}
    h = Host(Config(data_dir=tmp_path), tmp_path, MINIMAL, seed=1, clock=SimClock(1.0, now_fn=ft),
             ram_free_mb_fn=lambda: ram["v"])
    try:
        ram["v"] = B.REST_RAM_FREE_MB - 1
        run(h, ft, 1)
        assert h.snapshot().rest_reason == "low_ram"
        ram["v"] = 8000.0
        run(h, ft, 1)
        assert not h.snapshot().resting
    finally:
        h.stop()


def test_idle_rest_and_input_wakes(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    run(h, ft, 1)
    ft.tick(B.REST_IDLE_S)
    h.pump(1)
    assert h.snapshot().rest_reason == "idle"
    h.post("pet")
    run(h, ft, 1)
    assert not h.snapshot().resting


def test_rest_survives_save(tmp_path, hosts):
    ft = FakeTime(); h = hosts(tmp_path, ft)
    h.set_rest(True)
    run(h, ft, 2)
    h.stop()
    h2 = hosts(tmp_path, ft)
    assert h2.runtime.scheduler.resting
