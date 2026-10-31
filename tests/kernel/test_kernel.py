import json

import numpy as np

from engrama.kernel.kernel import Kernel
from engrama.kernel.sensors import Obs


def hatched(seed=1, now=0.0) -> Kernel:
    k = Kernel(seed, now)
    k.ingest([Obs(now, "click") for _ in range(5)])
    k.step(1.0)
    assert k.stage == "baby"
    return k


def test_dt_invariance():
    a, b = hatched(3), hatched(3)
    for k, dt in ((a, 1.0), (b, 60.0)):
        for _ in range(int(6 * 3600 / dt)):
            k.step(dt)
            k.execute("idle")
    assert a.stage == b.stage
    va, vb = a.channels()["body.needs"], b.channels()["body.needs"]
    assert np.allclose(va, vb, rtol=0.01, atol=0.005)


def test_egg_only_idle_and_hatch_after_clicks():
    k = Kernel(1)
    assert k.available_actions() == ("idle",)
    assert k.execute("wander") == ("idle", True)
    for i in range(4):
        k.ingest([Obs(float(i), "click")])
        k.step(1.0)
    assert k.stage == "egg"
    k.ingest([Obs(5.0, "click")])
    k.step(1.0)
    assert k.stage == "baby"


def test_fullscreen_forces_hide():
    k = hatched()
    k.ingest([Obs(k.t, "fullscreen_on")])
    k.step(1.0)
    assert k.available_actions() == ("hide",)
    assert k.execute("wander") == ("hide", True)
    k.ingest([Obs(k.t, "fullscreen_off")])
    k.step(1.0)
    assert "hide" not in k.available_actions()


def test_unavailable_proposal_uses_fallback():
    k = hatched()
    assert k.execute("show_something") == ("idle", True)
    k2 = hatched()
    assert k2.execute(None) == ("idle", True)
    assert k2.execute("idle") == ("idle", False)
    assert k2.execute("wander") == ("idle", True)


def test_food_relieves_fome():
    k = hatched()
    k.needs.values["fome"] = 80.0
    k.ingest([Obs(k.t, "food", {"food": "carne"})])
    k.step(0.001)
    assert abs(k.needs.values["fome"] - 40.0) < 0.1


def test_egg_ignores_food():
    k = Kernel(1)
    k.needs.values["fome"] = 80.0
    k.ingest([Obs(0.0, "food", {"food": "carne"})])
    k.step(0.001)
    assert k.needs.values["fome"] > 79.0


def test_need_relief_reward_on_food():
    k = hatched()
    k.needs.values["fome"] = 80.0
    k.ingest([Obs(k.t, "food", {"food": "carne"})])
    _, rew = k.step(1.0)
    assert rew["need_relief"] > 0.3


def test_pet_reduces_carinho_and_pays():
    k = hatched()
    k.needs.values["carinho"] = 50.0
    k.ingest([Obs(k.t, "pet")])
    _, rew = k.step(0.001)
    assert abs(k.needs.values["carinho"] - 42.0) < 0.1 and rew["petting"] == 1.0


def test_ask_answered_within_window_gives_user_response():
    k = hatched()
    assert k.execute("ask_attention") == ("ask_attention", False)
    k.step(30.0)
    k.ingest([Obs(k.t, "pet")])
    _, rew = k.step(10.0)
    assert rew["user_response"] == 1.0 and rew["ignored"] == 0.0


def test_ask_unanswered_gives_ignored_once():
    k = hatched()
    k.execute("ask_attention")
    seen = [k.step(30.0)[1]["ignored"] for _ in range(10)]
    assert sum(seen) == 1.0 and seen[4] == 1.0


def test_new_app_category_is_novel():
    k = hatched()
    k.ingest([Obs(k.t, "app_focus", {"category": "browser"})])
    assert k.step(1.0)[1]["novelty"] == 1.0
    k.ingest([Obs(k.t, "app_focus", {"category": "browser"})])
    assert k.step(1.0)[1]["novelty"] == 0.0
    k.ingest([Obs(k.t, "app_focus", {"category": "editor"})])
    assert k.step(1.0)[1]["novelty"] == 1.0


def test_sleep_runs_until_rested_and_wakes_on_event():
    k = hatched()
    k.needs.values["sono"] = 90.0
    assert k.execute(None) == ("sleep", True)
    assert k.asleep and k.available_actions() == ("sleep",)
    assert k.execute("wander") == ("sleep", True)
    k.step(3600.0)
    assert k.asleep
    k.ingest([Obs(k.t, "pet")])
    k.step(1.0)
    assert not k.asleep
    k.needs.values["sono"] = 90.0
    k.execute(None)
    for _ in range(40):
        k.step(300.0)
        if not k.asleep:
            break
    assert not k.asleep and 19.0 < k.needs.values["sono"] < 20.0


def test_offline_catchup_caps_needs():
    k = hatched()
    k.offline_catchup(10 * 24 * 3600.0)
    assert all(v <= 70.0 + 1e-9 for v in k.needs.values.values())
    assert k.needs.values["tedio"] == 70.0
    assert k.stage in ("baby", "child")
    assert k.t > 10 * 24 * 3600.0


def test_world_hour_from_start():
    k = Kernel(1, now=6 * 3600.0)
    s, c = k.channels()["world.hour"]
    assert abs(s - 1.0) < 1e-9 and abs(c) < 1e-9


def _drive(k: Kernel, n: int) -> None:
    kinds = ("pet", "click", "user_active", "fullscreen_on", "fullscreen_off")
    for i in range(n):
        if i % 37 == 0:
            k.ingest([Obs(k.t, kinds[(i // 37) % len(kinds)])])
        if i % 53 == 0:
            k.ingest([Obs(k.t, "food", {"food": "fruta"})])
        k.step(20.0)
        k.execute("ask_attention" if i % 11 == 0 else None)


def test_state_roundtrip_continues_identically():
    k = hatched(7)
    _drive(k, 1000)
    loaded = Kernel.from_state_dict(json.loads(json.dumps(k.state_dict())))
    _drive(k, 500)
    _drive(loaded, 500)
    a, b = k.channels(), loaded.channels()
    assert a.keys() == b.keys()
    for name in a:
        assert np.array_equal(a[name], b[name]), name
    assert k.rng.bit_generator.state == loaded.rng.bit_generator.state
    assert k.stage == loaded.stage and k.t == loaded.t


def test_no_nan_long_dt():
    k = hatched()
    for _ in range(24):
        k.step(3600.0)
        k.execute(None)
    for v in k.channels().values():
        assert np.all(np.isfinite(v))
    assert all(np.isfinite(x) for x in k.needs.values.values())


def _run(dt, total, start_action=None, events=(), tedio=None):
    k = hatched(5)
    if tedio is not None:
        k.needs.values["tedio"] = tedio
    k.ingest(list(events))
    if start_action:
        k.execute(start_action)
    pain = 0.0
    for _ in range(int(total / dt)):
        pain += k.step(dt)[1]["need_pain"]
        k.execute("idle")
    return k, pain


def test_dt_invariance_with_effect_action():
    ref, _ = _run(1.0, 600.0, "play_alone", tedio=80.0)
    for dt in (60.0, 600.0):
        k, _ = _run(dt, 600.0, "play_alone", tedio=80.0)
        assert abs(k.needs.values["tedio"] - ref.needs.values["tedio"]) < 0.01 * 100
        assert abs(k.needs.values["tedio"] - ref.needs.values["tedio"]) < 0.01 * ref.needs.values["tedio"] + 0.05


def test_need_pain_is_dt_independent():
    pains = []
    for dt in (1.0, 3600.0):
        k = hatched(5)
        k.needs.values["fome"] = 79.9
        p = 0.0
        for _ in range(int(3600 / dt)):
            p += k.step(dt)[1]["need_pain"]
        pains.append(p)
    assert pains[0] == pains[1] == 1.0


def test_interaction_suppression_is_windowed():
    big, _ = _run(3600.0, 3600.0, events=[Obs(0.0, "click")])
    small = hatched(5)
    small.ingest([Obs(0.0, "click")])
    for _ in range(60):
        small.step(60.0)
    # the hatch step in hatched() is identical in both; compare only post-click growth
    for key in ("tedio", "carinho", "fome"):
        assert abs(big.needs.values[key] - small.needs.values[key]) < 0.01 * max(1.0, small.needs.values[key]) + 0.05


def test_interaction_window_spans_steps():
    res = []
    for dt in (1.0, 10.0, 60.0, 120.0):
        k = hatched(5)
        k.ingest([Obs(k.t, "click")])
        for _ in range(int(120 / dt)):
            k.step(dt)
        res.append(k.needs.values["tedio"])
    assert max(res) - min(res) < 0.01 * max(res) + 0.01


def test_interact_until_roundtrips():
    k = hatched(5)
    k.ingest([Obs(k.t, "click")])
    k.step(1.0)
    k2 = Kernel.from_state_dict(json.loads(json.dumps(k.state_dict())))
    assert (k2._interact_from, k2._interact_until) == (k._interact_from, k._interact_until)


def test_interaction_window_anchored_to_event_time():
    res = []
    for dt in (1.0, 10.0, 60.0, 180.0):
        k = Kernel(5)
        base = k.needs.values["tedio"]
        k.ingest([Obs(31.0, "click")])
        for _ in range(int(180 / dt)):
            k.step(dt)
        res.append(k.needs.values["tedio"] - base)
    expected = 66.7 * (180 - 60) / 3600
    for r in res:
        assert abs(r - expected) < 0.01 * expected + 0.005


def test_rechosen_asks_do_not_rearm_window_one_ignored():
    k = hatched()
    k.execute("ask_attention")
    ign = []
    for _ in range(6):
        ign.append(k.step(60.0)[1]["ignored"])
        k.execute("ask_attention") if "ask_attention" in k.available_actions() else k.execute("idle")
    assert sum(ign) == 1.0 and ign[2] == 1.0   # t0+180 > 120 s after the first ask only


def test_ask_unavailable_during_min_interval_after_close():
    from engrama import balance as B
    k = hatched()
    k.execute("ask_attention")
    while "ask_attention" in k.available_actions():
        k.step(30.0)
    assert k.tracker.last_close is not None
    k.step(30.0)
    assert "ask_attention" not in k.available_actions()
    k.step(B.ASK_MIN_INTERVAL)
    assert "ask_attention" in k.available_actions()


def test_ask_interval_roundtrip():
    k = hatched()
    k.execute("ask_attention")
    for _ in range(6):
        k.step(30.0)
    k2 = Kernel.from_state_dict(json.loads(json.dumps(k.state_dict())))
    assert k2.tracker.last_close == k.tracker.last_close
    assert k2.available_actions() == k.available_actions()
