import psutil

from engrama.services.perception import HEAVY_FOR_S
from engrama.services.perception.service import PerceptionService
from engrama.services.perception.sources import NullSources, make_sources


class FakeCfg:
    def __init__(self, asked=True, interval=30.0, blocklist=None, **perms):
        self.perception_asked = asked
        self.perception_interval_s = interval
        self.perception_blocklist = blocklist or []
        self.permissions = {"time": False, "idle": False, "active_window": False,
                            "process": False, "system_load": False, **perms}


class FakeSources:
    def __init__(self):
        self.fg = ("code.exe", "main.py - engrama")
        self.idle = 0.0
        self.full = False
        self.cpu = 10.0
        self.calls = {"foreground": 0, "idle": 0, "full": 0, "cpu": 0}
        self.raise_exc = None

    def _maybe(self):
        if self.raise_exc:
            raise self.raise_exc

    def foreground(self):
        self.calls["foreground"] += 1
        self._maybe()
        return self.fg

    def idle_seconds(self):
        self.calls["idle"] += 1
        self._maybe()
        return self.idle

    def is_fullscreen(self):
        self.calls["full"] += 1
        self._maybe()
        return self.full

    def cpu_percent(self):
        self.calls["cpu"] += 1
        self._maybe()
        return self.cpu


def make(cfg, src=None, eyes=False, **kw):
    posts, src = [], src or FakeSources()
    state = {"eyes": eyes}
    svc = PerceptionService(lambda k, d: posts.append((k, d)), src, lambda: cfg,
                            lambda: state["eyes"], **kw)
    return svc, posts, src, state


def run(svc, start=0.0, secs=600, step=5.0):
    t = start
    while t <= start + secs:
        svc.tick(t)
        t += step
    return t


def test_nothing_read_before_first_use():
    svc, posts, src, _ = make(FakeCfg(asked=False, idle=True, process=True, system_load=True))
    run(svc)
    assert sum(src.calls.values()) == 0 and posts == []


def test_only_permitted_sources_read():
    cfg = FakeCfg(idle=True)
    svc, posts, src, _ = make(cfg)
    src.idle = 200.0
    run(svc, secs=200)
    assert src.calls["foreground"] == 0 and src.calls["full"] == 0 and src.calls["cpu"] == 0
    assert ("user_idle", {"source": "system"}) in posts


def test_eyes_closed_reads_nothing():
    cfg = FakeCfg(idle=True, process=True, active_window=True, system_load=True)
    svc, posts, src, _ = make(cfg, eyes=True)
    run(svc)
    assert sum(src.calls.values()) == 0 and posts == []


def test_permission_change_mid_cycle():
    cfg = FakeCfg(idle=True, process=True)
    svc, posts, src, _ = make(cfg)
    svc.tick(0.0)
    assert src.calls["foreground"] == 1
    cfg.permissions["process"] = False
    svc.tick(30.0)
    assert src.calls["foreground"] == 1


def test_eyes_closed_mid_cycle():
    cfg = FakeCfg(idle=True, process=True)
    svc, posts, src, state = make(cfg)
    svc.tick(0.0)
    state["eyes"] = True
    svc.tick(30.0)
    assert src.calls["idle"] == 1 and src.calls["foreground"] == 1


def test_blocked_app_is_private():
    themes = []
    cfg = FakeCfg(process=True, active_window=True)
    src = FakeSources()
    src.fg = ("bradesco.exe", "Internet Banking")
    svc, posts, _, _ = make(cfg, src, on_theme=lambda *a: themes.append(a))
    run(svc, secs=100)
    assert posts == [("app_focus", {"category": "privado"})]
    assert themes == []
    blob = repr(posts) + repr(svc.__dict__)
    assert "bradesco" not in blob and "Banking" not in blob


def test_user_blocklist_entry_applies_live():
    cfg = FakeCfg(process=True)
    src = FakeSources()
    src.fg = ("novelapp.exe", "x")
    svc, posts, _, _ = make(cfg, src)
    svc.tick(0.0)
    cfg.perception_blocklist = ["novelapp"]
    svc.tick(30.0)
    assert posts[-1] == ("app_focus", {"category": "privado"})


def test_app_focus_only_on_category_change():
    cfg = FakeCfg(process=True)
    svc, posts, src, _ = make(cfg)
    run(svc, secs=120)
    assert posts == [("app_focus", {"category": "programacao"})]
    src.fg = ("spotify.exe", "x")
    run(svc, start=130, secs=60)
    assert posts[-1] == ("app_focus", {"category": "musica"}) and len(posts) == 2
    assert all("code.exe" not in repr(p) for p in posts)


def test_theme_needs_active_window_and_sees_unblocked_only():
    themes = []
    svc, _, _, _ = make(FakeCfg(process=True), on_theme=lambda *a: themes.append(a))
    run(svc, secs=60)
    assert themes == []
    svc, _, _, _ = make(FakeCfg(process=True, active_window=True), on_theme=lambda *a: themes.append(a))
    svc.tick(0.0)
    assert themes == [("code.exe", "main.py - engrama", "programacao")]


def test_fullscreen_fast_poll():
    cfg = FakeCfg(system_load=True, interval=60.0)
    svc, posts, src, _ = make(cfg)
    svc.tick(0.0)
    src.full = True
    svc.tick(5.0)
    assert ("fullscreen_on", {}) in posts
    src.full = False
    svc.tick(10.0)
    assert posts[-1] == ("fullscreen_off", {})


def test_heavy_pc_after_two_minutes():
    seen = []
    cfg = FakeCfg(system_load=True)
    svc, _, src, _ = make(cfg, on_heavy=seen.append)
    src.cpu = 95.0
    run(svc, secs=HEAVY_FOR_S - 10)
    assert seen == []
    run(svc, start=HEAVY_FOR_S - 5, secs=20)
    assert seen == [True]
    src.cpu = 10.0
    svc.tick(500.0)
    assert seen == [True, False]


def test_heavy_needs_permission():
    seen = []
    svc, _, src, _ = make(FakeCfg(idle=True), on_heavy=seen.append)
    src.cpu = 99.0
    run(svc, secs=300)
    assert seen == [] and src.calls["cpu"] == 0


def test_source_errors_are_quiet():
    cfg = FakeCfg(idle=True, process=True, active_window=True, system_load=True)
    svc, posts, src, _ = make(cfg)
    src.raise_exc = psutil.NoSuchProcess(1)
    run(svc, secs=120)
    assert posts == []
    src.raise_exc = RuntimeError("boom")
    run(svc, start=130, secs=60)
    assert posts == []


def test_failing_callbacks_contained():
    def bad(*a):
        raise RuntimeError("x")
    cfg = FakeCfg(process=True, active_window=True)
    svc, posts, _, _ = make(cfg, on_theme=bad, categorize=lambda p: 1 / 0)
    svc.tick(0.0)
    assert posts == [("app_focus", {"category": "programa"})]


def test_null_sources_off_windows():
    src = make_sources(env={}, platform="linux")
    assert isinstance(src, NullSources)
    assert (src.foreground(), src.idle_seconds(), src.is_fullscreen(), src.cpu_percent()) == (None,) * 4
    svc, posts, _, _ = make(FakeCfg(idle=True, process=True, system_load=True), src)
    run(svc, secs=100)
    assert posts == []


def test_thread_start_stop_fast():
    import time
    svc, _, _, _ = make(FakeCfg(), now_fn=time.time)
    svc.start()
    t0 = time.time()
    svc.stop()
    assert time.time() - t0 < 0.6
