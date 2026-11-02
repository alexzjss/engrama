from engrama import balance as B
from engrama.app.rest import RestPolicy


def make(ram=4000.0):
    st = {"now": 10_000.0, "ram": ram}
    return RestPolicy(lambda: st["now"], lambda: st["ram"]), st


def test_nothing_triggers():
    p, st = make()
    assert p.update(False, st["now"]) is None


def test_fullscreen_triggers_rest():
    p, st = make()
    assert p.update(True, st["now"]) == "fullscreen"


def test_low_ram_triggers_rest():
    p, st = make(ram=B.REST_RAM_FREE_MB - 1)
    assert p.update(False, st["now"]) == "low_ram"


def test_long_idle_triggers_rest():
    p, st = make()
    last = st["now"]
    st["now"] += B.REST_IDLE_S - 1
    assert p.update(False, last) is None
    st["now"] += 1
    assert p.update(False, last) == "idle"


def test_manual_overrides():
    p, st = make()
    p.manual = True
    assert p.update(False, st["now"]) == "manual"
    p.manual = False
    assert p.update(False, st["now"]) is None


def test_rest_exit_when_trigger_clears():
    p, st = make()
    assert p.update(True, st["now"]) == "fullscreen"
    assert p.update(False, st["now"]) is None
    st["ram"] = 10.0
    assert p.update(False, st["now"]) == "low_ram"
    st["ram"] = 4000.0
    assert p.update(False, st["now"]) is None


def test_heavy_pc_triggers_rest_after_fullscreen_before_ram():
    p, st = make(ram=B.REST_RAM_FREE_MB - 1)
    assert p.update(False, st["now"], heavy_pc=True) == "heavy_pc"
    assert p.update(True, st["now"], heavy_pc=True) == "fullscreen"
    assert p.update(False, st["now"], heavy_pc=False) == "low_ram"


def test_broken_ram_probe_is_ignored():
    def boom():
        raise OSError("x")
    p = RestPolicy(lambda: 0.0, boom)
    assert p.update(False, 0.0) is None
