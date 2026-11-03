"""M10 guardas: a criatura padrão não muda (gabaritos, hashes, registro, canais, constantes)."""
import hashlib
import json
from pathlib import Path

import pytest

from engrama import balance as B
from engrama.config import Config
from engrama.lab.cli import main as lab_main
from engrama.mind import registry
from engrama.mind.contracts import CHANNELS
from engrama.vocab import EVENT_KINDS, FOOD_IDS, NEED_KEYS, TRAIT_KEYS

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "recipes"
M6_FIXTURE = ROOT / "tests" / "fixtures" / "m6_sim_1d_seed1_attentive.json"
M9_FIXTURE = ROOT / "tests" / "fixtures" / "m9_sim_7d_seed1_neglectful.json"

SHA256 = {
    "default-v1": "a835f09d222dc06ac685e0e2476c7300087c4378c8138accc974bccc15146b4d",
    "minimal-v1": "99ad72a1952a32ad240e0b9f73b5583ffc2d592120a6418902a6915c60079cce",
}

M9_REGISTRY = {
    "drives.needs": "engrama.modules.drives.needs:NeedDrives",
    "affect.pad": "engrama.modules.affect.pad:PadAffect",
    "policy.utility": "engrama.modules.policy.utility:UtilityPolicy",
    "policy.qlearning": "engrama.modules.policy.qlearning:QLearningPolicy",
    "prefs.food": "engrama.modules.prefs.food:FoodPrefs",
    "traits.drift": "engrama.modules.traits.drift:TraitDrift",
    "temporal.snn": "engrama.modules.temporal.snn:TemporalSNN",
}

M10_REGISTRY = {
    "temporal.ctrnn": "engrama.modules.temporal.ctrnn:TemporalCTRNN",
    "world.model": "engrama.modules.world.model:WorldModel",
    "policy.curious": "engrama.modules.policy.curious:CuriousQPolicy",
    "policy.thompson": "engrama.modules.policy.thompson:ThompsonPolicy",
    "policy.aif": "engrama.modules.policy.aif:ActiveInferencePolicy",
}


def _lab_sim(capsys, *args) -> dict:
    assert lab_main(["sim", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_default_lab_matches_m6_fixture(capsys):
    got = _lab_sim(capsys, "--recipe", str(RECIPES / "default-v1.toml"), "--days", "1", "--seed", "1",
                   "--profile", "attentive")
    assert got == json.loads(M6_FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_default_multilife_matches_m9_fixture(capsys):
    fixture = json.loads(M9_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["lives"]["generations_finished"] >= 1
    got = _lab_sim(capsys, "--recipe", str(RECIPES / "default-v1.toml"), "--days", "7", "--seed", "1",
                   "--profile", "neglectful")
    assert got == fixture


def test_default_and_minimal_recipes_unchanged():
    for name, digest in SHA256.items():
        assert hashlib.sha256((RECIPES / f"{name}.toml").read_bytes()).hexdigest() == digest, name


def test_old_registry_entries_unchanged():
    assert {k: registry.REGISTRY[k] for k in M9_REGISTRY} == M9_REGISTRY


def test_new_registry_entries_present():
    assert {k: registry.REGISTRY[k] for k in M10_REGISTRY} == M10_REGISTRY


def test_channels_are_m9_plus_world_error():
    expect = [
        ("body.needs", len(NEED_KEYS), 0, 1),
        ("body.stage", 1, 0, 5),
        ("body.asleep", 1, 0, 1),
        ("body.health", 3, 0, 1),
        ("world.hour", 2, -1, 1),
        ("world.user_active", 1, 0, 1),
        ("world.fullscreen", 1, 0, 1),
        ("drives", len(NEED_KEYS), 0, 1),
        ("affect.pad", 3, -1, 1),
        ("traits", len(TRAIT_KEYS), 0, 1),
        ("temporal.surprise", 1, 0, 1),
        ("temporal.familiarity", 1, 0, 1),
        ("temporal.expectation", len(EVENT_KINDS), 0, 1),
        ("prefs.food", len(FOOD_IDS), -1, 1),
        ("world.error", 1, 0, 1),
    ]
    assert [(c.name, c.dim, c.lo, c.hi) for c in CHANNELS.values()] == expect


def test_config_recipe_default():
    assert Config().recipe == "default-v1"


def test_m10_constants():
    expect = {
        "M10_STATE_VERSION": 1,
        "EXP_BUDGET_MS": 2.0,
        "CTRNN_HIDDEN": 64,
        "CTRNN_TAU_MIN_BINS": 1.0,
        "CTRNN_TAU_MAX_BINS": 1440.0,
        "CTRNN_SUBSTEPS": 4,
        "CTRNN_SPECTRAL_RADIUS": 0.9,
        "CTRNN_P_REC": 0.2,
        "CTRNN_W_IN": 1.0,
        "CTRNN_BUDGET_MS": 5.0,
        "WM_LR": 0.05,
        "WM_ERR_EMA": 0.99,
        "CUR_BETA": 0.3,
        "CUR_BASELINE_EMA": 0.99,
        "CUR_LP_FAST": 0.9,
        "CUR_LP_SLOW": 0.99,
        "TS_SIGMA0": 0.5,
        "TS_NOISE_FLOOR": 0.05,
        "TS_TD_VAR_EMA": 0.99,
        "TS_N_HALF_LIFE_DAYS": 7.0,
        "AIF_PRIOR": 1.0,
        "AIF_PREF_SCALE": 2.0,
        "AIF_NOVELTY_WEIGHT": 1.0,
        "AIF_SOCIAL_GAIN": 1.0,
        "AIF_COUNT_HALF_LIFE_DAYS": 7.0,
        "SUITE_DAYS": 7.0,
        "SUITE_ROUTINE_DAYS": 4.0,
        "SUITE_SEEDS": (1, 2, 3),
        "SUITE_PROFILES": ("attentive", "absent", "neglectful", "routine"),
    }
    for name, value in expect.items():
        assert getattr(B, name) == value, name
