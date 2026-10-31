import copy
import os
import time
import numpy as np
import pytest
from engrama.mind.contracts import Blackboard, Observation
from engrama.modules.temporal.snn import TemporalSNN
from engrama.vocab import EVENT_KINDS, STAGES


def make(n=32, seed=0):
    return TemporalSNN({"n_hidden": n}, np.random.default_rng(seed))


def run(m, kinds_per_bin, bb=None):
    """Step once per entry (a kind, a tuple of kinds, or None); returns per-bin (surprise, raw, expectation)."""
    bb = bb or Blackboard()
    out = []
    for i, ks in enumerate(kinds_per_bin):
        if ks is None:
            ks = ()
        elif isinstance(ks, str):
            ks = (ks,)
        bb.events = tuple(Observation(float(i), k) for k in ks)
        bb.t = float(i)
        m.step(bb, 1.0)
        out.append((float(bb.read("temporal.surprise")[0]), m.raw_surprise,
                    bb.read("temporal.expectation")))
    return out


@pytest.mark.parametrize("n", [32, 64, 96, 128, 160])
@pytest.mark.parametrize("seed", range(5))
def test_bounded_rates_all_sizes_and_seeds(n, seed):
    m = make(n, seed)
    rs = np.random.default_rng(100 + seed)
    bb = Blackboard()
    counts = np.zeros(n)
    for i in range(300):
        ks = tuple(k for k in EVENT_KINDS if rs.random() < 0.15)
        bb.events = tuple(Observation(float(i), k) for k in ks)
        m.step(bb, 1.0)
        if i >= 200:
            counts += m.last_spikes.sum(axis=0)
    rates = counts / 100 * 50.0          # spikes per 20 ms bin -> Hz
    assert 2.0 <= rates.mean() <= 40.0
    assert rates.max() <= 200.0


def test_habituation():
    m = make()
    s = [o[0] for o in run(m, ["pet"] * 300)]
    assert np.mean(s[200:300]) < 0.5 * np.mean(s[0:20])


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_novelty_spike(seed):
    m = make(32, seed)
    bb = Blackboard()
    run(m, ["pet" if i % 2 == 0 else None for i in range(300)], bb)
    base = np.mean([o[0] for o in run(m, ["pet" if i % 2 == 0 else None for i in range(300, 350)], bb)])
    nov = run(m, ["fullscreen_on"], bb)[0][0]
    assert nov > 2 * base


def routine_gap(seed, **params):
    m = TemporalSNN({"n_hidden": 32, **params}, np.random.default_rng(seed))
    n = 400
    out = run(m, ["message" if i % 3 == 0 else None for i in range(n)])
    mi = EVENT_KINDS.index("message")
    # expectation after bin k predicts bin k+1
    due = [out[k][2][mi] for k in range(n - 60, n - 1) if (k + 1) % 3 == 0]
    other = [out[k][2][mi] for k in range(n - 60, n - 1) if (k + 1) % 3 != 0]
    return float(np.mean(due) - np.mean(other))


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_routine_expectation(seed):
    assert routine_gap(seed) >= 0.2


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_ablation_bias_only_has_no_routine_coding(seed):
    """Without hidden features the readout is a base rate: the SNN is what carries the temporal code."""
    assert abs(routine_gap(seed, readout_hidden=False)) < 0.05
    assert routine_gap(seed) >= 0.2


def test_stdp_strengthens_presented_kind():
    m = make(32)
    w0 = m.w_in.copy()
    run(m, ["pet"] * 300)
    pop = 4                                         # input units are populations of 4 neurons
    sl = slice(EVENT_KINDS.index("pet") * pop, (EVENT_KINDS.index("pet") + 1) * pop)
    unseen = slice(EVENT_KINDS.index("food") * pop, (EVENT_KINDS.index("food") + 1) * pop)
    d = m.w_in - w0
    gain = d[:, sl].sum() / m.m_in[:, sl].sum()
    assert gain > 0.05
    assert np.all(d[:, unseen] == 0)
    assert np.all(m.w_in[~m.m_in] == 0) and np.all(m.w_ee[~m.m_ee] == 0)


def test_stdp_weights_clipped_to_wmax(monkeypatch):
    import engrama.balance as B
    monkeypatch.setattr(B, "SNN_WMAX", 0.8)
    monkeypatch.setattr(B, "SNN_STDP_APLUS", 0.05)
    m = make(32)
    run(m, ["pet", "click"] * 100)
    for w in (m.w_in, m.w_ee):
        assert w.min() >= 0.0 and w.max() <= 0.8 + 1e-12
    assert np.isclose(m.w_in.max(), 0.8)           # the cap was actually reached


def test_grow_preserves_weights():
    m = make(32)
    run(m, ["pet"] * 30)
    w_in, w_ee, wp, th = m.w_in.copy(), m.w_ee.copy(), m.w_pred.copy(), m.theta.copy()
    m.grow(64)
    assert m.n == 64 and m.w_in.shape == (64, m.w_in.shape[1]) and m.w_pred.shape == (10, 64)
    assert np.array_equal(m.w_in[:32], w_in) and np.array_equal(m.w_ee[:32, :32], w_ee)
    assert np.array_equal(m.w_pred[:, :32], wp) and np.all(m.w_pred[:, 32:] == 0)
    assert np.array_equal(m.theta[:32], th)
    run(m, ["pet"] * 5)                        # still runs


def test_grow_on_stage_change():
    m = make(32)
    bb = Blackboard()
    bb.write("body.stage", [2])
    run(m, ["pet"] * 3, bb)
    assert m.n == 64 and STAGES[m.stage] == "child"


def test_state_roundtrip_identical_outputs():
    m = make(32)
    run(m, ["pet" if i % 2 == 0 else None for i in range(80)])
    sd = copy.deepcopy(m.state_dict())
    m2 = TemporalSNN({"n_hidden": 8}, np.random.default_rng(99))
    m2.load_state_dict(sd)
    m2.rng = copy.deepcopy(m.rng)
    seq = ["pet" if i % 2 == 0 else "click" for i in range(40)]
    a, b = run(m, seq), run(m2, seq)
    for (s1, _, e1), (s2, _, e2) in zip(a, b):
        assert s1 == s2 and np.array_equal(e1, e2)
    assert m2.raw_surprise == m.raw_surprise
    assert list(m2._series) == list(m._series)


def test_channels_and_viz():
    m = make()
    bb = Blackboard()
    run(m, ["pet"] * 3, bb)
    assert bb.read("temporal.expectation").shape == (10,)
    assert 0 <= bb.read("temporal.familiarity")[0] <= 1
    kinds = {v.kind for v in m.viz()}
    assert kinds == {"raster", "heatmap", "series"}


@pytest.mark.skipif(bool(os.environ.get("CI")), reason="timing-sensitive")
def test_step_cost():
    m = make(160)
    bb = Blackboard()
    run(m, ["pet"] * 10, bb)
    t0 = time.perf_counter()
    run(m, ["pet", None] * 50, bb)
    assert (time.perf_counter() - t0) / 100 * 1000 < 3.0
