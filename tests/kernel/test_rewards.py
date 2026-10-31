import numpy as np

from engrama.kernel.rewards import RewardTracker
from engrama.kernel.sensors import Obs
from engrama.vocab import REWARD_KEYS


def test_collect_has_all_keys_and_resets():
    r = RewardTracker()
    r.on_novel()
    out = r.collect(1.0)
    assert set(out) == set(REWARD_KEYS) and out["novelty"] == 1.0
    assert r.collect(2.0)["novelty"] == 0.0


def test_relief_only_for_needs_above_half():
    r = RewardTracker()
    before = np.array([0.9, 0.3, 0, 0, 0, 0])
    after = np.array([0.5, 0.1, 0, 0, 0, 0])
    r.on_needs(before, after, 1.0)
    assert abs(r.collect(1.0)["need_relief"] - 0.4) < 1e-9


def test_pain_on_crossing_08():
    r = RewardTracker()
    r.on_needs(np.array([0.75, 0.85, 0, 0, 0, 0]), np.array([0.82, 0.9, 0, 0, 0, 0]), 1.0)
    assert abs(r.collect(1.0)["need_pain"] - 0.07) < 1e-9


def test_answer_after_window_does_not_count():
    r = RewardTracker()
    r.on_action_started("ask_attention", 0.0)
    r.on_events([Obs(500.0, "click")], 500.0)
    out = r.collect(500.0)
    assert out["user_response"] == 0.0 and out["ignored"] == 1.0
