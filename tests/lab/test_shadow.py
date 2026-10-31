from pathlib import Path
import numpy as np
from engrama.lab.runtime import Runtime, run_days
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind.recipe import load_recipe

BASE = Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml"
DAY = 86400.0


def _actions(recipe, seed=1, days=2):
    rt = Runtime(recipe, seed)
    user = SimUser(PROFILES["attentive"], np.random.default_rng([seed, 1]))
    out = []
    rt.user = user
    while rt.kernel.t < 8 * 3600 + days * DAY - 1e-9:
        out.append(rt.tick(60.0, user.events(rt.kernel.t, 60.0, rt.creature())))
    return out


def _with_shadow(tmp_path):
    p = tmp_path / "shadow.toml"
    p.write_text(BASE.read_text() + '\n[[shadow]]\ntype = "policy.utility"\nname = "u2"\nweight = 2.0\nvariant = 7\n')
    return p


def test_shadow_does_not_change_actions(tmp_path):
    p = _with_shadow(tmp_path)
    assert _actions(load_recipe(BASE)) == _actions(load_recipe(p))
    m = run_days(p, 2, "attentive", 1, 60.0, None)
    assert "u2" in m["shadow_agreement"]
    assert 0.0 <= m["shadow_agreement"]["u2"] <= 1.0
    base = run_days(BASE, 2, "attentive", 1, 60.0, None)
    assert base["action_share"] == m["action_share"] and base["wellbeing"] == m["wellbeing"]
