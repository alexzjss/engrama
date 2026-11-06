import math
import numpy as np
import pytest
from engrama import balance as B
from engrama.mind.contracts import ASK_ACTION, Blackboard, Experience
from engrama.modules.policy.aif import (ActiveInferencePolicy, efe, log_pref, outcome_vector)
from engrama.modules.policy.qlearning import state_index
from engrama.vocab import ACTIONS, REWARD_KEYS
from tests.modules import contract_kit as kit


def chans(hour=3, active=1, pad=(0.5, 0.5, 0.0)):
    a = 2 * math.pi * hour / 24
    return {"world.hour": np.array([math.sin(a), math.cos(a)]),
            "world.user_active": np.array([float(active)]), "affect.pad": np.array(pad, dtype=float)}


X = chans()
K = {k: i for i, k in enumerate(REWARD_KEYS)}


def exp(action, rewards, dt=1.0, ch=X):
    return Experience(0.0, dt, (), ch, action, 1.0, rewards, ch)


def bbox(ch=X, traits=None):
    bb = Blackboard()
    for k, v in ch.items():
        bb.write(k, v)
    if traits is not None:
        bb.write("traits", np.array(traits, dtype=float))
    return bb


def new(**p):
    return ActiveInferencePolicy(p, np.random.default_rng(0))


def traits(soc):
    return {"curiosidade": 0.5, "sociabilidade": soc, "paciencia": 0.5, "independencia": 0.5, "criatividade": 0.5}


def test_outcome_vector():
    o = outcome_vector({"need_pain": 0.3, "msg_valence": -0.5})
    assert o.shape == (7,) and o.dtype == bool
    assert o[K["need_pain"]] and not o[K["msg_valence"]] and not o[K["need_relief"]]


def test_log_pref_normalized_and_signed():
    lp = log_pref(traits(0.5))
    assert lp.shape == (7, 2)
    assert np.allclose(np.exp(lp).sum(-1), 1.0)
    assert lp[K["need_relief"], 1] > lp[K["need_relief"], 0]
    for k in ("need_pain", "ignored"):
        assert lp[K[k], 0] > lp[K[k], 1]
    lo, hi = log_pref(traits(0.0)), log_pref(traits(1.0))
    assert hi[K["user_response"], 1] > lo[K["user_response"], 1]
    assert np.allclose(lo[K["need_relief"]], hi[K["need_relief"]])


def test_efe_matches_hand_computed():
    counts = np.array([[[1.0, 3.0]] * 7, [[2.0, 2.0]] * 7])      # (A=2, 7, 2)
    lnp = np.log(np.array([[0.25, 0.75]] * 7))
    G, prag, nov = efe(counts, lnp, 2.0)
    q = np.array([0.25, 0.75])
    p0 = 7 * -(q * np.log([0.25, 0.75])).sum()
    n0 = 7 * (q * 0.5 * (1 / np.array([1.0, 3.0]) - 1 / 4.0)).sum()
    p1 = 7 * -(0.5 * np.log(0.25) + 0.5 * np.log(0.75))
    n1 = 7 * (0.5 * 0.5 * (1 / 2 - 1 / 4) * 2)
    assert np.allclose(prag, [p0, p1]) and np.allclose(nov, [n0, n1])
    assert np.allclose(G, prag - 2.0 * nov)


def test_preferred_outcome_action_has_lowest_G():
    m = new()
    s = state_index(X)
    a = ACTIONS.index("pet_me") if "pet_me" in ACTIONS else 1
    m.counts[s, a, K["need_relief"], 1] += 50
    G, _, _ = efe(m.counts[s], log_pref(traits(0.5)), 0.0)
    assert int(np.argmin(G)) == a
    props = {p.action: p.score for p in m.propose(bbox(traits=[0.5] * 5))}
    assert max(props, key=props.get) == ACTIONS[a]


def test_novelty_prefers_unvisited():
    m = new(pref_scale=0.0)
    s = state_index(X)
    m.counts[s] += 5.0
    m.counts[s, 3] = B.AIF_PRIOR
    G, _, _ = efe(m.counts[s], log_pref(traits(0.5), 0.0), 1.0)
    assert int(np.argmin(G)) == 3


def test_no_pref_no_novelty_equal_G():
    m = new(pref_scale=0.0, novelty_weight=0.0)
    s = state_index(X)
    m.counts[s, 2] += np.arange(14).reshape(7, 2)
    props = m.propose(bbox(traits=[0.5] * 5))
    assert len({round(p.score, 9) for p in props}) == 1
    G, _, _ = efe(m.counts[s], log_pref(traits(0.5), 0.0), 0.0)
    assert np.allclose(G, G[0])


def test_ask_window_counted_once():
    m = new()
    s, a = state_index(X), ACTIONS.index(ASK_ACTION)
    base = m.counts.copy()
    m.learn(exp(ASK_ACTION, {"need_relief": 0.0}))
    d = m.counts - base
    assert d[s, a, K["user_response"]].sum() == 0 and d[s, a, K["ignored"]].sum() == 0
    assert d[s, a, K["need_relief"], 0] == 1 and d[s, a, K["petting"], 0] == 1
    before = m.counts.copy()
    m.learn(exp(ASK_ACTION, {"user_response": 1.0}, dt=0.0))
    d = m.counts - before
    assert d[s, a, K["user_response"], 1] == 1 and d[s, a, K["user_response"], 0] == 0
    assert d.sum() == 1
    before = m.counts.copy()
    m.learn(exp(ASK_ACTION, {"ignored": 1.0}, dt=0.0))
    d = m.counts - before
    assert d[s, a, K["ignored"], 1] == 1 and d.sum() == 1


def test_ask_window_closed_in_row_and_other_actions():
    m = new()
    s, a = state_index(X), ACTIONS.index(ASK_ACTION)
    base = m.counts.copy()
    m.learn(exp(ASK_ACTION, {"user_response": 1.0}))
    d = m.counts - base
    assert d[s, a, K["user_response"], 1] == 1 and d[s, a, K["ignored"]].sum() == 0
    other = next(x for x in ACTIONS if x != ASK_ACTION)
    base = m.counts.copy()
    m.learn(exp(other, {}))
    d = m.counts - base
    assert d[s, ACTIONS.index(other)].sum() == 7


def test_counts_decay_toward_prior():
    m = new()
    s, a = state_index(X), 0
    m.counts[s, a] = 9.0
    m.learn(exp(ACTIONS[a], {}, dt=7 * 86400.0))
    assert np.allclose(m.counts[s, a, 0, 0], B.AIF_PRIOR + 8.0 * 0.5 + 1)   # +1 from the update
    m.learn(exp("nope", {}, dt=1e9))
    assert np.allclose(m.counts[s, a, 1, 1], B.AIF_PRIOR + 4.0)


def test_no_rng_use():
    outs = []
    for seed in (1, 2):
        m = ActiveInferencePolicy({}, np.random.default_rng(seed))
        m.learn(exp("idle", {"need_relief": 1.0}))
        outs.append([(p.action, p.score, p.reason) for p in m.propose(bbox())])
    assert outs[0] == outs[1]


def test_proposals_available_only_and_reasons():
    m = new()
    bb = bbox()
    bb.available_actions = ["idle", ASK_ACTION]
    ps = m.propose(bb)
    assert {p.action for p in ps} == {"idle", ASK_ACTION} and all(p.reason for p in ps)
    assert all(np.isfinite(p.score) for p in ps)


def test_state_dict_version_and_viz():
    m = new()
    m.propose(bbox())
    assert m.state_dict()["version"] == B.M10_STATE_VERSION
    assert {v.kind for v in m.viz()} == {"bars", "table"}
    assert set(m.lab_metrics()) == {"novelty_share", "g_spread_mean", "pragmatic_mean"}


@pytest.mark.slow
def test_recipe_runs_clean():
    rec = kit.recipe("aif-v1")
    assert [m.type for m in rec.modules].count("policy.aif") == 1
    kit.run_clean(rec, 3, "attentive")
    kit.run_clean(rec, 5, "neglectful")


@pytest.mark.perf
def test_recipe_mean_ms_within_budget():
    rt = kit.run_clean(kit.recipe("aif-v1"), 5, "neglectful")
    assert kit.mean_ms(rt, "policy.aif") <= B.EXP_BUDGET_MS


def test_recipe_save_load_identical(tmp_path):
    kit.assert_save_load_identical(kit.recipe("aif-v1"), tmp_path, 6 * 3600.0, 6 * 3600.0)


def test_recipe_roundtrip_and_rng(tmp_path, monkeypatch):
    rec = kit.recipe("aif-v1")
    rt = kit.run_clean(rec, 0.25)
    kit.assert_state_roundtrip(rt.scheduler._mods["policy.aif"], tmp_path)
    kit.assert_no_global_rng(monkeypatch, rec)
