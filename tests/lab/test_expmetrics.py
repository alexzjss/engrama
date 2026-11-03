from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from engrama.lab.explog import TickRow
from engrama.lab.expmetrics import Probe, experiment_metrics
from engrama.lab.runtime import Runtime
from engrama.mind import registry
from engrama.mind.contracts import Blackboard, Observation
from engrama.mind.recipe import load_recipe
from engrama.vocab import EVENT_KINDS

DAY = 86400.0
MIN = Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml"


def _rt(mods=None):
    return SimpleNamespace(bb=Blackboard(), scheduler=SimpleNamespace(modules=lambda: mods or {}))


def _step(rt, t, exp=None, kinds=(), needs=None, extra=None):
    rt.bb.t = t
    rt.bb.events = tuple(Observation(t, k) for k in kinds)
    if exp is not None:
        rt.bb.write("temporal.expectation", exp)
    if needs is not None:
        rt.bb.write("body.needs", needs)
    for k, v in (extra or {}).items():
        rt.bb.write(k, v)


def _vec(i, v):
    a = np.zeros(len(EVENT_KINDS)); a[i] = v
    return a


def test_brier_known_sequence():
    rt, p = _rt(), Probe(0.0, 0.0)
    k0 = EVENT_KINDS[0]
    _step(rt, 1.0, _vec(0, 0.5)); p.after_tick(rt, False)            # no previous: nothing
    _step(rt, 2.0, _vec(0, 1.0), kinds=[k0]); p.after_tick(rt, False)   # (0.5-1)^2/n
    _step(rt, 3.0, _vec(0, 0.0)); p.after_tick(rt, False)            # (1-0)^2/n
    n = len(EVENT_KINDS)
    assert p.result(rt)["pred_brier"]["temporal.expectation"] == pytest.approx((0.25 / n + 1.0 / n) / 2)


def test_brier_skips_rebirth_tick_and_first_half():
    rt, p = _rt(), Probe(0.0, 1.0)   # counts only t >= 0.5 day
    _step(rt, 100.0, _vec(0, 1.0)); p.after_tick(rt, False)
    _step(rt, 200.0, _vec(0, 1.0)); p.after_tick(rt, False)          # first half: skipped
    assert p.result(rt)["pred_brier"] == {}
    _step(rt, DAY * 0.6, _vec(0, 1.0)); p.after_tick(rt, False)      # compares with previous (counted)
    _step(rt, DAY * 0.6 + 1, _vec(0, 1.0)); p.after_tick(rt, True)   # rebirth tick: skipped
    _step(rt, DAY * 0.6 + 2, _vec(0, 0.0)); p.after_tick(rt, False)  # prev was set on the rebirth tick: (1-0)^2
    n = len(EVENT_KINDS)
    assert p.result(rt)["pred_brier"]["temporal.expectation"] == pytest.approx((1.0 / n + 1.0 / n) / 2)


def test_brier_includes_shadow_channels(tmp_path):
    rec = tmp_path / "s.toml"
    rec.write_text(MIN.read_text() + '\n[[shadow]]\ntype = "temporal.snn"\nname = "snn_s"\n')
    rt = Runtime(load_recipe(rec), 1)
    p = Probe(rt.kernel.t, 0.0)
    for _ in range(400):
        rt.tick(60.0, [])
        p.after_tick(rt, False)
    b = p.result(rt)["pred_brier"]
    assert "shadow/snn_s/temporal.expectation" in b and all(v >= 0 for v in b.values())
    assert "temporal.expectation" not in b   # minimal has no live temporal module


def test_need_satisfaction_and_world_error():
    rt, p = _rt(), Probe(0.0, 1.0)
    _step(rt, 10.0, needs=[0.2] * 6, extra={"world.error": [0.5], "shadow/w/world.error": [0.1]})
    p.after_tick(rt, False)
    _step(rt, 30.0, needs=[0.6] * 6, extra={"world.error": [0.1], "shadow/w/world.error": [0.1]})
    p.after_tick(rt, False)
    r = p.result(rt)
    assert r["need_satisfaction"] == pytest.approx((0.8 * 10 + 0.4 * 20) / 30)   # time-weighted
    assert r["world_error_mean"] == {"shadow/w/world.error": pytest.approx(0.1), "world.error": pytest.approx(0.3)}


def _row(action, rewards=None, decided=True, t=0.0):
    return TickRow(t, 60.0, action, 1.0, rewards or {}, [], [], [], {}, decided)


def test_return_per_day_uses_credit_rows():
    rows = [_row("ask_attention"), _row("idle", {"user_response": 1.0}),
            _row("idle", {"novelty": 1.0})]
    from engrama.mind.contracts import credit_rows
    m = experiment_metrics(rows, 2.0)
    assert m["return_per_day"] == pytest.approx(sum(credit_rows((r.action, r.rewards) for r in rows)) / 2.0)
    assert m["novelty_per_day"] == pytest.approx(0.5)


def test_decision_entropy_and_switch_rate():
    rows = [_row("a"), _row("a", decided=False), _row("b"), _row("b"), _row("a"), _row("b", decided=False)]
    m = experiment_metrics(rows, 1.0)      # decided: a b b a -> p = .5/.5 ; switches 2 of 3
    assert m["decision_entropy"] == pytest.approx(1.0)
    assert m["switch_rate"] == pytest.approx(2 / 3)
    z = experiment_metrics([], 1.0)
    assert z["decision_entropy"] == 0.0 and z["switch_rate"] == 0.0


class _Fake:
    def __init__(self, v):
        self.v = v

    def lab_metrics(self):
        return {"x": self.v, "nested": {"y": self.v * 2}, "text": "no", "flag": True, "bad": float("nan")}


class _Boom:
    def lab_metrics(self):
        raise RuntimeError("tolerated")


def test_lab_metrics_weighted_over_lives():
    mods = {"fake": _Fake(1.0), "boom": _Boom(), "plain": object()}
    rt, p = _rt(mods), Probe(0.0, 1.0)
    for t in (1.0, 2.0, 3.0):
        _step(rt, t); p.after_tick(rt, False)
    p.before_rebirth(rt)                    # life 1: 3 ticks, x = 1
    mods["fake"].v = 5.0
    _step(rt, 4.0); p.after_tick(rt, True)  # life 2: 1 tick, x = 5
    lm = p.result(rt)["lab_metrics"]
    assert lm == {"fake": {"nested/y": pytest.approx((2 * 3 + 10) / 4), "x": pytest.approx((3 + 5) / 4)}}


def test_unknown_module_metrics_tolerated_in_real_runtime():
    class Odd:
        def __new__(cls, *a, **k):
            return object.__new__(cls)
    # a registered real module type exposing lab_metrics through the Runtime scheduler
    from engrama.modules.policy.utility import UtilityPolicy

    class WithMetrics(UtilityPolicy):
        def lab_metrics(self):
            return {"answer": 42, "unknown_shape": [1, 2, 3], "name": "str"}
    import sys, types
    mod = types.ModuleType("_t5_fake_mod"); mod.WithMetrics = WithMetrics
    sys.modules["_t5_fake_mod"] = mod
    registry.register("policy.t5fake", "_t5_fake_mod:WithMetrics")
    try:
        import dataclasses
        rec = load_recipe(MIN)
        spec = dataclasses.replace(rec.modules[-1], type="policy.t5fake", name="fk")
        rt = Runtime(dataclasses.replace(rec, modules=rec.modules[:-1] + (spec,)), 1)
        p = Probe(rt.kernel.t, 1.0)
        for _ in range(5):
            rt.tick(60.0, []); p.after_tick(rt, False)
        assert p.result(rt)["lab_metrics"] == {"fk": {"answer": 42.0}}
    finally:
        registry.REGISTRY.pop("policy.t5fake", None)
