import math

import numpy as np

from engrama import balance as B
from engrama.kernel.kernel import Kernel
from engrama.kernel.lifecycle import Health
from engrama.kernel.sensors import Obs
from engrama.vocab import MEDICINE_ID, NEED_KEYS

H = B.HOUR


def baby(seed=1) -> Kernel:
    k = Kernel(seed)
    k.lifecycle.hatch_now()
    return k


def hold(k: Kernel, level: float) -> None:
    for n in NEED_KEYS:
        k.needs.values[n] = level


def run(k: Kernel, seconds: float, level: float | None, dt: float = 60.0, stop=None) -> None:
    for _ in range(int(seconds / dt)):
        if level is not None:
            hold(k, level)
        k.step(dt)
        if stop and stop(k):
            return


def test_neglect_makes_sick_after_6h():
    k = baby()
    run(k, 5.9 * H, 90.0)
    assert not k.health.sick
    run(k, 0.3 * H, 90.0)
    assert k.health.sick and k.health.kind == "neglect"
    assert k.health.severity >= B.SICK_SEVERITY_START


def test_care_heals():
    k = baby()
    run(k, 7 * H, 90.0)
    assert k.health.sick
    run(k, 12 * H, 10.0)
    assert not k.health.sick and k.health.severity == 0.0


def test_grave_then_death_24h_online():
    k = baby()
    run(k, 40 * H, 95.0, stop=lambda k: k.health.grave)
    assert k.health.grave and not k.dead
    t_grave = k.t
    run(k, 23 * H, 95.0)
    assert not k.dead
    run(k, 2 * H, 95.0)
    assert k.dead and k.death_cause == "neglect"
    assert k.t - t_grave >= B.GRAVE_DEATH_AFTER_S


def count_colds(seed: int, days: int) -> int:
    k = baby(seed)
    run(k, days * 24 * H, 10.0, dt=600.0, stop=None)
    return k.health.cold_count


def test_cold_rate_about_monthly():
    for seed in (1, 2, 3):
        assert 1 <= count_colds(seed, 120) <= 8


def test_cold_never_grave_when_cared():
    k = baby(2)
    peak = 0.0
    for _ in range(120 * 24 * 6):
        hold(k, 10.0)
        k.step(600.0)
        peak = max(peak, k.health.severity)
        assert not k.health.grave
    assert peak <= B.COLD_MAX_SEVERITY and k.death_cause in ("", "old_age")


def test_medicine_cures_cold_and_cooldown():
    h = Health(sick=True, kind="cold", severity=0.3, cold_left_s=5 * H)
    assert h.give_medicine(100.0) is True
    assert not h.sick
    h2 = Health(sick=True, kind="cold", severity=0.3, cold_left_s=5 * H, last_medicine_t=0.0)
    assert h2.give_medicine(3 * H) is False and h2.sick
    assert h2.give_medicine(7 * H) is True and not h2.sick
    n = Health(sick=True, kind="neglect", severity=0.9)
    assert n.give_medicine(0.0) is True
    assert math.isclose(n.severity, 0.9 - B.MEDICINE_NEGLECT_RELIEF) and n.sick

    k = baby()
    k.health = Health(sick=True, kind="cold", severity=0.3, cold_left_s=5 * H)
    k.ingest([Obs(k.t, "food", {"food": MEDICINE_ID})])
    k.step(1.0)
    assert not k.health.sick


def test_medicine_egg_or_healthy_noop():
    egg = Kernel(1)
    egg.ingest([Obs(0.0, "food", {"food": MEDICINE_ID})])
    egg.step(1.0)
    assert egg.stage == "egg" and egg.health.last_medicine_t == -math.inf
    k = baby()
    k.ingest([Obs(0.0, "food", {"food": MEDICINE_ID})])
    k.step(1.0)
    assert not k.health.sick and k.health.last_medicine_t == -math.inf
    assert not np.any(k.needs.as_vector() < 0)


def test_offline_never_sick_or_dead():
    k = baby()
    before = k.health.to_dict()
    k.offline_catchup(90 * 24 * H)
    assert k.health.to_dict() == before
    assert not k.dead and not k.health.sick
    k2 = baby()
    run(k2, 7 * H, 90.0)
    assert k2.health.sick
    snap = k2.health.to_dict()
    k2.offline_catchup(90 * 24 * H)
    assert k2.health.to_dict() == snap and not k2.dead
