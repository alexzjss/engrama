"""M10 acceptance: one test per criterion of the spec (docs/superpowers/specs/2026-11-08-engrama-m10-experimentos-design.md, §7).

Criterion 1 (default untouched) re-runs the guard checks of tests/test_m10_guard.py; the mechanism checks of
criterion 5 run the module tests' short scenarios against the real modules (the per-module tests stay the
detailed evidence). Budget tests that spawn a process or run for wall seconds are `slow`.
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pygame
import pytest

from engrama import balance as B
from engrama.app.host import Host
from engrama.clock import SimClock
from engrama.config import Config
from engrama.lab.cli import main as lab_main
from engrama.lab.suite import RunSpec, run_one, run_suite
from engrama.mind import registry
from engrama.mind.recipe import ModuleSpec
from engrama.vocab import EVENT_KINDS, FOOD_IDS, NEED_KEYS, TRAIT_KEYS
from tests import test_m10_guard as G
from tests.modules import contract_kit as K
from tests.modules import test_aif as TA
from tests.modules import test_ctrnn as TCT
from tests.modules import test_curious as TCU
from tests.modules import test_thompson as TT
from tests.modules import test_world_model as TW

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "recipes"
REPORT = ROOT / "docs" / "superpowers" / "reports" / "2026-11-08-m10-experimentos"
NEW = ["ctrnn-v1", "shadow-ctrnn-v1", "curious-v1", "curious-lp-v1", "thompson-v1", "aif-v1", "aif-solo-v1",
       "lab-shadow-all-v1"]
NEW_TYPES = {"temporal.ctrnn", "world.model", "policy.curious", "policy.thompson", "policy.aif"}
SHADOWS = ["shadow-ctrnn-v1", "lab-shadow-all-v1"]
APP_ENV = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONPATH=str(ROOT))


def _app(tmp_path, *args, frames=120):
    return subprocess.run([sys.executable, "-m", "engrama", "--frames", str(frames), "--no-llm",
                           "--data-dir", str(tmp_path), *args],
                          cwd=ROOT, env=APP_ENV, capture_output=True, text=True, timeout=180)


def _bench(*args, seconds=30):
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "bench.py"), *args, "--seconds", str(seconds)],
                         capture_output=True, text=True, cwd=ROOT, timeout=seconds + 120, check=True).stdout
    return json.loads(out)


# 1 -- default untouched -------------------------------------------------------------------------------

def test_default_untouched(capsys):
    G.test_default_lab_matches_m6_fixture(capsys)
    G.test_default_and_minimal_recipes_unchanged()
    G.test_old_registry_entries_unchanged()
    G.test_channels_are_m9_plus_world_error()
    G.test_config_recipe_default()


@pytest.mark.slow
def test_default_untouched_multilife(capsys):
    G.test_default_multilife_matches_m9_fixture(capsys)


# 2 -- every new recipe runs ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("name", NEW)
def test_every_new_recipe_runs_clean(name):
    K.run_clean(K.recipe(name), 3, "attentive")


@pytest.mark.slow
@pytest.mark.parametrize("name", NEW)
def test_every_new_recipe_runs_clean_neglectful(name):
    K.run_clean(K.recipe(name), 5, "neglectful")


# 3 -- determinism -------------------------------------------------------------------------------------

def _strip(runs):
    return [{k: v for k, v in r.items() if k != "module_ms"} for r in runs]


@pytest.mark.slow
def test_suite_deterministic_and_jobs_invariant():
    specs = [RunSpec(RECIPES / f"{n}.toml", p, 1, 0.25) for n in ("default-v1", "thompson-v1")
             for p in ("attentive", "routine")]
    a, b, par = run_suite(specs, 1), run_suite(specs, 1), run_suite(specs, 2)
    assert json.dumps(_strip(a)) == json.dumps(_strip(b)) == json.dumps(_strip(par))


@pytest.mark.parametrize("name", NEW)
def test_every_new_recipe_save_load_identical(name, tmp_path):
    K.assert_save_load_identical(K.recipe(name), tmp_path, 2 * 3600.0, 2 * 3600.0)


# 4 -- shadows -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", SHADOWS)
def test_shadows_keep_live_identical(name):
    K.assert_same_live_actions(K.recipe(name), K.recipe("default-v1"), days=2.0)


def test_shadow_ctrnn_reports_own_brier():
    m = run_one(RunSpec(RECIPES / "shadow-ctrnn-v1.toml", "attentive", 1, 0.5))["metrics"]
    own = [k for k in m["pred_brier"] if k != "temporal.expectation"]
    assert own and all(np.isfinite(m["pred_brier"][k]) for k in own), m["pred_brier"]


# 5 -- each mechanism does what it says ----------------------------------------------------------------

def test_mechanisms():
    TW.test_error_drops_in_stationary_world()                 # world model: the error falls
    TCU.test_bonus_credited_to_transition_action()            # curiosity: bonus goes to the right action
    TCU.test_progress_bonus_returns_to_zero_when_error_flat()
    TT.test_sd_shrinks_with_visits_and_regrows_with_forgetting()   # Thompson
    TT.test_two_armed_bandit_prefers_best()
    TT.test_zero_sd_equals_mean()
    TA.test_preferred_outcome_action_has_lowest_G()           # active inference: preferred outcome has lowest G
    TA.test_novelty_prefers_unvisited()
    TA.test_no_pref_no_novelty_equal_G()
    TCT.test_rare_event_more_surprising()                     # CTRNN
    TCT.test_dt_invariant()


def test_aif_uses_no_rng():
    TA.test_no_rng_use()


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ctrnn_routine_no_worse(seed):
    TCT.test_no_worse_than_bias_only_on_routine(seed)


# 6 -- budget ------------------------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("name", NEW)
def test_budget_headless_each_recipe(name):
    r = _bench("--recipe", name)
    tol = 1.5 if os.getloadavg()[0] > (os.cpu_count() or 1) * 0.7 else 1.0   # same loaded-machine tolerance
    assert not r["disabled"]
    assert r["peak_rss_mb"] <= 150 * tol
    assert r["mean_cpu_percent"] <= 2.0 * tol


@pytest.mark.slow
def test_budget_app_shadow_all(tmp_path):
    r = _bench("--app", "--recipe", "lab-shadow-all-v1", "--data-dir", str(tmp_path / "bench"))
    assert r["alive"], "the app exited during the bench"
    tol = 1.5 if r["loaded"] else 1.0   # as test_core_budget
    print("shadow-all app budget:", r, "tolerance", tol)
    assert r["peak_rss_mb"] <= 150 * tol
    assert r["mean_cpu_percent"] <= 2.0 * tol


@pytest.mark.perf
@pytest.mark.parametrize("name", NEW)
def test_new_modules_mean_ms(name):
    rt = K.run_clean(K.recipe(name), 0.25)
    checked = [m for m in rt.scheduler.modules() if m in NEW_TYPES]
    assert checked or name == "shadow-ctrnn-v1"
    for m in checked:
        if m == "temporal.ctrnn":
            assert K.mean_ms(rt, m) <= B.CTRNN_BUDGET_MS, m
        else:
            assert K.mean_ms(rt, m) <= B.EXP_BUDGET_MS, m


# 7 -- suite -------------------------------------------------------------------------------------------

def test_suite_cli_small(tmp_path, capsys):
    out, md = tmp_path / "s.json", tmp_path / "s.md"
    assert lab_main(["suite", "--recipes", "default-v1", "thompson-v1", "--profiles", "attentive", "--seeds", "1",
                     "--days", "0.5", "--out", str(out), "--md", str(md)]) == 0
    d = json.loads(out.read_text())
    assert [r["recipe"] for r in d["runs"]] == ["default-v1", "thompson-v1"]
    assert "thompson-v1" in d["summary"]["vs_baseline"] and "### attentive" in md.read_text()
    assert capsys.readouterr().out == ""
    # the baseline row matches `sim`
    assert lab_main(["sim", "--recipe", str(RECIPES / "default-v1.toml"), "--days", "0.5", "--seed", "1",
                     "--profile", "attentive"]) == 0
    sim = json.loads(capsys.readouterr().out)
    base = d["runs"][0]["metrics"]
    assert {k: json.loads(json.dumps(base[k])) for k in ("wellbeing", "ask_count", "action_share", "pad_mean")} == \
           {k: sim[k] for k in ("wellbeing", "ask_count", "action_share", "pad_mean")}


# 8 -- saves -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("typ", ["temporal.ctrnn", "world.model", "policy.curious", "policy.thompson",
                                 "policy.aif"])
def test_state_versions(typ, tmp_path):
    m = registry.build(ModuleSpec(typ, typ, {}), np.random.default_rng(0))
    K.assert_state_roundtrip(m, tmp_path)


# 9 -- app ---------------------------------------------------------------------------------------------

def test_app_new_creature_with_recipe_name(tmp_path):
    r = _app(tmp_path, "--recipe", "thompson-v1")
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "save" / "meta.json").read_text())["recipe"]["name"] == "thompson-v1"


def test_app_existing_save_keeps_recipe(tmp_path):
    assert _app(tmp_path, "--recipe", "thompson-v1").returncode == 0
    r = _app(tmp_path, "--recipe", "default-v1", frames=30)
    assert r.returncode == 0, r.stderr
    assert "thompson-v1" in r.stderr and "default-v1" in r.stderr   # the logged warning
    assert json.loads((tmp_path / "save" / "meta.json").read_text())["recipe"]["name"] == "thompson-v1"
    r = _app(tmp_path, frames=30)   # no --recipe: the save wins quietly
    assert r.returncode == 0 and "somente" not in r.stderr and "only applies" not in r.stderr


def test_host_logs_recipe_mismatch(tmp_path, caplog):
    h = Host(Config(data_dir=tmp_path), tmp_path, RECIPES / "thompson-v1.toml", seed=1)
    h.stop()
    with caplog.at_level(logging.WARNING, logger="engrama.app"):
        h2 = Host(Config(data_dir=tmp_path), tmp_path, RECIPES / "default-v1.toml", seed=1)
        h2.stop()
    assert any("thompson-v1" in r.getMessage() and "default-v1" in r.getMessage() for r in caplog.records)


def test_unknown_recipe_name_exits_2(tmp_path):
    r = _app(tmp_path, "--recipe", "no-such-recipe", frames=5)
    assert r.returncode == 2
    assert "no-such-recipe" in r.stderr
    assert not (tmp_path / "save").exists()


@pytest.mark.parametrize("name", ["lab-shadow-all-v1"] + [n for n in NEW if n != "lab-shadow-all-v1"])
def test_mind_view_collects_new_viz(name, tmp_path):
    """A real Host with want_viz: every new module's viz() is collected, and the real Mind View (F2) draws it."""
    from engrama.app.ui.mind_view import MindView
    from engrama.app.ui.viz_draw import VizState, draw_viz
    pygame.init()
    t = [1_000_000.0]
    h = Host(Config(data_dir=tmp_path), tmp_path, RECIPES / f"{name}.toml", seed=3,
             clock=SimClock(1.0, now_fn=lambda: t[0]), ram_free_mb_fn=lambda: 8000.0)
    try:
        h.want_viz = True
        for i in range(60):
            if i % 7 == 0:
                h.post("pet")
            t[0] += 5.0
            h.pump(1)
        snap = h.snapshot()
        new_names = [s.name for s in h._rt.recipe.modules if s.type in NEW_TYPES]
    finally:
        h.stop()
    assert new_names
    for mod in new_names:
        assert snap.viz.get(mod), (name, mod, sorted(snap.viz))
    state = VizState()
    for vizs in snap.viz.values():
        for v in vizs:
            draw_viz(pygame.Surface((260, 150)), pygame.Rect(0, 0, 260, 150), v, state)   # must not raise
    MindView().draw(pygame.Surface((480, 700)), snap)


# 10 -- architecture and vocabulary --------------------------------------------------------------------

def test_architecture_and_vocab_frozen():
    from tests.test_architecture import check
    assert not check(ROOT)
    assert len(NEED_KEYS) and len(TRAIT_KEYS) and len(EVENT_KINDS) and len(FOOD_IDS)
    G.test_channels_are_m9_plus_world_error()


# 11 -- report -----------------------------------------------------------------------------------------

def test_report_present():
    md, js = REPORT.with_suffix(".md"), REPORT.with_suffix(".json")
    assert md.exists() and js.exists()
    d = json.loads(js.read_text(encoding="utf-8"))
    recipes = {r["recipe"] for r in d["runs"]}
    assert recipes == {"default-v1", "ctrnn-v1", "shadow-ctrnn-v1", "curious-v1", "curious-lp-v1", "thompson-v1",
                       "aif-v1", "aif-solo-v1"}
    assert {r["profile"] for r in d["runs"]} == set(B.SUITE_PROFILES)
    assert "python -m engrama.lab suite" in md.read_text(encoding="utf-8")


# smoke ------------------------------------------------------------------------------------------------

def test_smoke_frames(tmp_path):
    r = _app(tmp_path)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "save" / "meta.json").read_text())["recipe"]["name"] == "default-v1"
