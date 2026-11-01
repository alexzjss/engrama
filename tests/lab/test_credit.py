"""R24: ask-window rewards are credited to the ask that opened the window, for the learner and for OPE."""
from pathlib import Path
import numpy as np
from engrama import balance as B
from engrama.lab.explog import ExperienceLog, read_log
from engrama.lab.ope import ips_estimate
from engrama.lab.runtime import Runtime
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind.contracts import AskCredit, credit_rows, reward_combine
from engrama.mind.recipe import load_recipe

DEFAULT = Path(__file__).resolve().parents[2] / "recipes" / "default-v1.toml"
R = lambda **k: {"need_relief": 0.0, "user_response": 0.0, "ignored": 0.0, **k}


def test_credit_rows_moves_answer_to_opening_ask():
    rows = [("idle", R()), ("ask_attention", R()), ("explore", R(user_response=1.0, need_relief=0.5)),
            ("sleep", R())]
    c = credit_rows(rows)
    assert c[1] == reward_combine({"user_response": 1.0})
    assert c[2] == reward_combine({"need_relief": 0.5})
    assert c[0] == c[3] == 0.0
    assert sum(c) == sum(reward_combine(r) for _, r in rows)         # nothing created or lost


def test_credit_rows_chain_credits_first_ask_and_ignored_too():
    rows = [("ask_attention", R()), ("ask_attention", R()), ("idle", R(ignored=1.0))]
    c = credit_rows(rows)
    assert c[0] == reward_combine({"ignored": 1.0}) and c[1] == 0.0 and c[2] == 0.0


def test_credit_same_row_and_orphan_stay_put():
    t = AskCredit()
    own, moved, tgt = t.push("ask_attention", R(user_response=1.0), "tok")
    assert not moved and own["user_response"] == 1.0
    own, moved, tgt = AskCredit().push("idle", R(user_response=1.0), "x")     # no open window
    assert not moved and own["user_response"] == 1.0


def test_answered_ask_is_credited_to_the_ask_in_learner_and_ope(tmp_path):
    rec = load_recipe(DEFAULT)
    log = ExperienceLog(tmp_path / "l.db", "r", rec.name, 1)
    rt = Runtime(rec, 1, log)
    rt.user = SimUser(PROFILES["attentive"], np.random.default_rng([1, 1]))
    seen = []
    real = rt.scheduler.learn
    rt.scheduler.learn = lambda exp: (seen.append(exp), real(exp))[1]
    rt.run(2 * 24 * B.HOUR, 60.0)
    log.close()
    # learner: every user_response reward reaches an experience whose action is ask_attention
    answered = [e for e in seen if e.rewards.get("user_response", 0.0) > 0]
    assert answered and all(e.action == "ask_attention" for e in answered)
    rows = list(read_log(tmp_path / "l.db"))
    raw_rows = [r for r in rows if r.rewards.get("user_response", 0.0) > 0]
    assert len(answered) == len(raw_rows)
    assert any(r.action != "ask_attention" for r in raw_rows)        # in the raw log it sits on a later row
    # OPE: the credited reward of the ask row includes the answer
    credited = credit_rows((r.action, r.rewards) for r in rows)
    ask_rows = [i for i, r in enumerate(rows) if r.action == "ask_attention"]
    assert sum(credited[i] for i in ask_rows) > sum(reward_combine(rows[i].rewards) for i in ask_rows)
    out = ips_estimate(rows, lambda r: {r.action: r.prob})
    decided = [c for c, r in zip(credited, rows) if r.decided]
    assert out["logged_value"] == np.float64(sum(decided) / len(decided)) or abs(
        out["logged_value"] - sum(decided) / len(decided)) < 1e-12
