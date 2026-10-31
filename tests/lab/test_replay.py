from pathlib import Path
import numpy as np
from engrama.lab.explog import read_log
from engrama.lab.replay import replay_module
from engrama.lab.runtime import run_days
from engrama.mind.recipe import ModuleSpec

RECIPE = Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml"


def test_replay_matches_live_for_deterministic_module(tmp_path):
    log = tmp_path / "l.db"
    run_days(RECIPE, 0.5, "attentive", 1, 60.0, log)
    out = replay_module(log, ModuleSpec("drives.needs", "drives.needs", {}))
    assert set(out) == {"t", "drives", "proposals_top"}
    replayed = dict(zip(out["t"], out["drives"]))
    checked = 0
    for r in list(read_log(log))[1:]:
        if r.channels:
            np.testing.assert_allclose(replayed[r.t], r.channels["drives"], atol=1e-6)
            checked += 1
    assert checked > 5
    assert len(out["t"]) == len(out["drives"]) == len(out["proposals_top"])


def test_replay_matches_live_for_event_driven_module(tmp_path):
    from engrama.lab.explog import ExperienceLog
    from engrama.lab.runtime import Runtime
    from engrama.lab.simuser import PROFILES, SimUser
    from engrama.mind.recipe import load_recipe
    log = tmp_path / "l.db"
    rec = load_recipe(RECIPE)
    el = ExperienceLog(log, "r", rec.name, 1, sample_s=0.0)
    rt = Runtime(rec, 1, el)
    rt.run(6 * 3600.0, 60.0, SimUser(PROFILES["attentive"], np.random.default_rng([1, 1])))
    el.close()
    rows = list(read_log(log))
    assert sum(1 for r in rows if r.events) > 3
    out = replay_module(log, ModuleSpec("affect.pad", "affect.pad", {}))
    replayed = dict(zip(out["t"], out["affect.pad"]))
    checked = 0
    for r in rows[1:]:
        if r.channels:
            np.testing.assert_allclose(replayed[r.t], r.channels["affect.pad"], atol=1e-6)
            checked += 1
    assert checked > 100
