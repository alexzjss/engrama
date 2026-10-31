import json
import threading

from engrama.core.bus import Event, EventBus
from engrama.core.clock import SimClock
from engrama.core.config import Config


def test_config_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config.load(p)
    assert p.exists()
    assert cfg.model == "qwen3:1.7b" and cfg.permissions["time"] is True
    cfg.model = "other:1b"
    cfg.save(p)
    assert Config.load(p) == cfg
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["bogus"] = 1
    p.write_text(json.dumps(raw), encoding="utf-8")
    assert Config.load(p) == cfg


def test_clock_scale_and_clamp():
    t = iter([0.0, 1.0, 1000.0, 999.0])
    clock = SimClock(time_scale=60, now_fn=lambda: next(t))
    assert clock.advance() == 60
    assert clock.advance() == 5 * 60
    assert clock.advance() == 0
    assert clock.sim_time == 360


def test_bus_threadsafe():
    bus = EventBus()

    def work():
        for i in range(250):
            bus.post(Event("x", {"i": i}))

    threads = [threading.Thread(target=work) for _ in range(4)]
    [th.start() for th in threads]
    [th.join() for th in threads]
    assert len(bus.drain()) == 1000
    assert bus.drain() == []
