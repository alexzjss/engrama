import dataclasses
import numpy as np
import pytest
from engrama import balance as B
from engrama.lab.runtime import Runtime
from engrama.mind.contracts import Blackboard, Observation
from engrama.modules.temporal.ctrnn import TemporalCTRNN
from engrama.vocab import EVENT_KINDS
from tests.modules import contract_kit as K

DAY = 86400.0


def make(n=32, seed=0, **p):
    return TemporalCTRNN({"n_hidden": n, **p}, np.random.default_rng(seed))


def run(m, kinds_per_bin, bb=None):
    bb = bb or Blackboard()
    out = []
    bs = B.SNN_BIN_S
    for ks in kinds_per_bin:
        i = round(bb.t / bs)
        ks = () if ks is None else ((ks,) if isinstance(ks, str) else ks)
        bb.events = tuple(Observation(i * bs, k) for k in ks)
        bb.t = (i + 1) * bs
        m.step(bb, bs)
        out.append((float(bb.read("temporal.surprise")[0]), m.raw_surprise, bb.read("temporal.expectation")))
    return out


def test_writes_temporal_channels_in_range():
    m = make()
    bb = Blackboard()
    run(m, ["pet", None, "message"] * 20, bb)
    assert bb.read("temporal.expectation").shape == (len(EVENT_KINDS),)
    assert np.all((bb.read("temporal.expectation") >= 0) & (bb.read("temporal.expectation") <= 1))
    assert 0 <= bb.read("temporal.surprise")[0] <= 1
    assert 0 <= bb.read("temporal.familiarity")[0] <= 1
    assert {v.kind for v in m.viz()} == {"series", "bars", "heatmap"}
    assert set(m.lab_metrics()) == {"ctrnn_h_abs_mean", "ctrnn_surprise_mean"}


def _run_dt(dt, seed=0, minutes=240):
    m = make(32, seed)
    bb = Blackboard()
    surprise, expect = [], []
    t, end = 0.0, minutes * 60.0
    while t < end - 1e-9:
        evs = []
        for k in range(int(round(dt))):
            ts = t + k
            if ts % 180 == 0:
                evs.append(Observation(ts, "pet"))
            if ts % 420 == 0 and ts > 0:
                evs.append(Observation(ts, "message"))
        bb.events, bb.t = tuple(evs), t + dt
        m.step(bb, dt)
        t += dt
        if abs(t % B.SNN_BIN_S) < 1e-9:
            surprise.append(float(bb.read("temporal.surprise")[0]))
            expect.append(bb.read("temporal.expectation"))
    return np.array(surprise), np.array(expect)


def test_dt_invariant():
    s1, e1 = _run_dt(1.0)
    s60, e60 = _run_dt(60.0)
    assert len(s1) == len(s60) == 240
    assert np.allclose(s1, s60, atol=1e-9) and np.allclose(e1, e60, atol=1e-9)


def test_rare_event_more_surprising():
    m = make()
    bb = Blackboard()
    run(m, ["pet"] * 300, bb)
    common = run(m, ["pet"], bb)[0][1]
    rare = run(m, ["fullscreen_on"], bb)[0][1]
    assert rare > 2 * common


def test_readout_hidden_false_is_bias_only():
    m = make(readout_hidden=False)
    run(m, ["pet" if i % 3 == 0 else None for i in range(100)])
    assert np.all(m.w_pred == 0.0)
    assert np.all(m.feat == 0.0)
    assert np.abs(m.bias).sum() > 0


@pytest.mark.parametrize("n", [32, 64])
def test_spectral_radius_at_creation(n):
    m = make(n)
    assert abs(np.max(np.abs(np.linalg.eigvals(m.W))) - B.CTRNN_SPECTRAL_RADIUS) < 1e-6
    assert np.all(np.diag(m.W) == 0)
    assert np.isclose(m.tau[0], B.CTRNN_TAU_MIN_BINS) and np.isclose(m.tau[-1], B.CTRNN_TAU_MAX_BINS)


@pytest.mark.slow
def test_stable_thirty_days():
    rt = Runtime(K.recipe("ctrnn-v1"), 1)
    rt.user = K._user("attentive", 1)
    end = 30 * DAY
    peak = 0.0
    while rt.kernel.t < end - 1e-9:
        rt.tick(60.0, rt.user.events(rt.kernel.t, 60.0, rt.creature()))
        if rt.kernel.dead:
            rt.lives.append(rt.rebirth())
        if int(rt.kernel.t) % 3600 == 0:
            m = _ctrnn(rt)
            assert np.all(np.isfinite(m.h)) and np.all(np.isfinite(m.w_pred))
            peak = max(peak, float(np.abs(m.h).max()))
    assert peak <= 10.0
    K._check_modules(rt)


def _ctrnn(rt):
    return rt.scheduler._mods["temporal.ctrnn"]


def _brier(rec, seed, days=4, dt=60.0, readout_hidden=True):
    from engrama.vocab import EVENT_KINDS as EK
    from tests.test_m2_acceptance import _RoutineUser
    mods = tuple(dataclasses.replace(s, params={**s.params, "readout_hidden": readout_hidden})
                 if s.type == "temporal.ctrnn" else s for s in rec.modules)
    rt = Runtime(dataclasses.replace(rec, modules=mods), seed)
    rt.user = _RoutineUser(dt)
    prev, errs = None, []
    while rt.kernel.t < days * DAY:
        rt.run(dt, dt)
        kinds = {o.kind for o in rt.bb.events}
        if prev is not None and rt.kernel.t > days * DAY / 2:
            y = np.array([1.0 if k in kinds else 0.0 for k in EK])
            errs.append(float(np.mean((prev - y) ** 2)))
        prev = np.asarray(rt.bb.read("temporal.expectation"), dtype=float).copy()
    return float(np.mean(errs))


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_no_worse_than_bias_only_on_routine(seed):
    rec = K.recipe("ctrnn-v1")
    full, abl = _brier(rec, seed), _brier(rec, seed, readout_hidden=False)
    gain = (abl - full) / abl
    print("CTRNN_BRIER", seed, full, abl, gain)
    assert gain >= 0.0, (seed, full, abl, gain)


@pytest.mark.slow
def test_run_clean_attentive():
    K.run_clean(K.recipe("ctrnn-v1"), 3, "attentive")


@pytest.mark.slow
def test_run_clean_neglectful():
    K.run_clean(K.recipe("ctrnn-v1"), 5, "neglectful")


def test_save_load_identical(tmp_path):
    K.assert_save_load_identical(K.recipe("ctrnn-v1"), tmp_path, 4 * 3600.0, 4 * 3600.0)


def test_state_roundtrip(tmp_path):
    m = make()
    run(m, ["pet" if i % 2 == 0 else None for i in range(50)])
    K.assert_state_roundtrip(m, tmp_path)


def test_no_global_rng(monkeypatch):
    K.assert_no_global_rng(monkeypatch, K.recipe("ctrnn-v1"))


@pytest.mark.perf
def test_step_within_budget():
    rt = K.run_clean(K.recipe("ctrnn-v1"), 0.25)
    ms = K.mean_ms(rt, "temporal.ctrnn")
    print("CTRNN_MS", ms)
    assert ms <= B.EXP_BUDGET_MS


def test_shadow_ctrnn_live_identical_to_default():
    K.assert_same_live_actions(K.recipe("shadow-ctrnn-v1"), K.recipe("default-v1"))
