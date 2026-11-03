import json

import numpy as np

from engrama import balance as B
from engrama.kernel.kernel import Kernel
from engrama.kernel.sensors import Obs
from engrama.vocab import BRANCHES, NEED_KEYS, STAGES

H = B.HOUR


def at_stage(stage: str, seed: int = 1) -> Kernel:
    k = Kernel(seed)
    k.lifecycle.stage = stage
    return k


def hold(k: Kernel, level: float = 10.0) -> None:
    for n in NEED_KEYS:
        k.needs.values[n] = level


def run(k: Kernel, seconds: float, dt: float = 600.0, level: float = 10.0) -> None:
    for _ in range(int(seconds / dt)):
        hold(k, level)
        k.step(dt)
        if k.dead:
            return


def test_old_age_after_final_lifespan_and_3_online_days():
    k = at_stage("final")
    run(k, B.FINAL_LIFESPAN_S - H)
    assert not k.lifecycle.old and not k.dead
    run(k, 2 * H)
    assert k.lifecycle.old
    run(k, B.OLD_AGE_WARN_S - 4 * H)
    assert not k.dead
    run(k, 6 * H)
    assert k.dead and k.death_cause == "old_age"

    off = at_stage("final")
    off.offline_catchup(B.FINAL_LIFESPAN_S + 10 * 24 * H)
    assert off.lifecycle.old and off.lifecycle.old_online_s == 0.0 and not off.dead
    run(off, 2 * 24 * H)
    assert not off.dead
    run(off, 2 * 24 * H)
    assert off.dead and off.death_cause == "old_age"


def test_old_age_waits_calm_moment():
    k = at_stage("final")
    k.lifecycle.final_age = B.FINAL_LIFESPAN_S
    k.lifecycle.old = True
    k.lifecycle.old_online_s = B.OLD_AGE_WARN_S + 1
    k.ingest([Obs(0.0, "fullscreen_on")])
    hold(k)
    k.step(60.0)
    assert not k.dead
    k.ingest([Obs(k.t, "fullscreen_off"), Obs(k.t, "message", {"valence": 0.5})])
    hold(k)
    k.step(60.0)
    assert not k.dead
    hold(k)
    k.step(200.0)
    assert not k.dead
    hold(k)
    k.step(200.0)
    assert k.dead and k.death_cause == "old_age"

    s = at_stage("final")
    s.lifecycle.old = True
    s.lifecycle.final_age = B.FINAL_LIFESPAN_S
    s.lifecycle.old_online_s = B.OLD_AGE_WARN_S + 1
    s._action = "sleep"
    hold(s, 60.0)
    s.step(60.0)
    assert not s.dead


def test_branch_on_each_evolution():
    k = Kernel(5)
    k.observe_traits([0.9, 0.9, 0.5, 0.3, 0.5])
    k.ingest([Obs(0.0, "click") for _ in range(5)])
    k.step(1.0)
    assert k.stage == "baby" and k.lineage == () and k.genome.branch == "base"
    seen = []
    for _ in range(10000):
        hold(k, 10.0)
        k.step(3600.0)
        if len(k.lineage) > len(seen):
            seen.append(k.stage)
            assert k.genome.branch == k.lineage[-1]
            assert k.lineage[-1] in BRANCHES[k.stage]
        if k.stage == "final":
            break
    assert seen == ["child", "adult", "perfect", "final"]
    assert len(k.lineage) == 4 and k.stage == "final"


def test_interest_from_app_focus():
    k = Kernel(1)
    k.lifecycle.hatch_now()
    assert all(v == 0.0 for v in k.interests().values())
    k.ingest([Obs(0.0, "app_focus", {"category": "game"})])
    k.step(100.0)
    k.step(100.0)
    assert k.interest_s["jogos"] == 200.0
    assert k.interests()["jogos"] == 1.0
    k.ingest([Obs(k.t, "app_focus", {"category": "privado"})])
    k.step(100.0)
    assert k.interest_s["jogos"] == 200.0


def test_dead_kernel_is_inert():
    k = at_stage("adult")
    hold(k, 30.0)
    k._die("neglect")
    vec = k.needs.as_vector().copy()
    t0 = k.t
    k.ingest([Obs(t0, "food", {"food": "carne"}), Obs(t0, "pet")])
    k.step(120.0)
    assert k.available_actions() == ()
    assert k.execute("wander") == ("idle", True)
    assert np.array_equal(k.needs.as_vector(), vec)
    assert k.t == t0 + 120.0
    k.offline_catchup(H)
    assert np.array_equal(k.needs.as_vector(), vec)
    assert Kernel.from_state_dict(json.loads(json.dumps(k.state_dict()))).dead


def test_m5_save_loads():
    k = at_stage("child")
    hold(k, 30.0)
    run(k, 2 * H)
    d = json.loads(json.dumps(k.state_dict()))
    for key in ("generation", "lineage", "dead", "death_cause", "interest_s", "traits", "last_message_t"):
        d.pop(key)
    d["health"] = {"sick": False}
    for key in ("stage_care_sum", "stage_care_t", "life_care_sum", "life_care_t",
                "finished_care_mean", "final_age", "old", "old_online_s"):
        d["lifecycle"].pop(key)
    r = Kernel.from_state_dict(d)
    assert r.generation == 1 and r.lineage == () and not r.dead and r.genome.branch == "base"
    assert not r.health.sick and r.stage == "child"
    r.step(60.0)
    r.execute("idle")
    assert STAGES.index(r.stage) >= 2


def test_deterministic_life():
    def life():
        k = Kernel(7)
        k.ingest([Obs(0.0, "click") for _ in range(5)])
        k.step(1.0)
        for i in range(10 * 24 * 6):
            if i % 7 == 0:
                k.ingest([Obs(k.t, "app_focus", {"category": "editor" if i % 2 else "game"})])
            if i % 13 == 0:
                k.ingest([Obs(k.t, "pet"), Obs(k.t, "food", {"food": "carne"})])
            k.step(600.0)
            k.execute("wander")
        return json.dumps(k.state_dict(), sort_keys=True, default=str)

    assert life() == life()
