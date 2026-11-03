"""O kit de contrato (tests/modules/contract_kit.py) exercitado com módulos que já existem e um falso."""
from pathlib import Path

import numpy as np
import pytest

from engrama import balance as B
from engrama.mind import registry
from engrama.mind.contracts import Module
from engrama.mind.recipe import ModuleSpec, Recipe
from engrama.vocab import ACTIONS
from tests.modules import contract_kit as K

DAY = 86400.0


class VersionedFake(Module):
    reads = ()
    writes = ()

    def __init__(self, params, rng):
        super().__init__(params, rng)
        self.w = np.zeros(3)

    def state_dict(self):
        return {"version": B.M10_STATE_VERSION, "w": self.w.copy()}

    def load_state_dict(self, d):
        if not d:
            return
        v = int(d.get("version", B.M10_STATE_VERSION))
        if v > B.M10_STATE_VERSION:
            raise ValueError(f"versão {v} mais nova que {B.M10_STATE_VERSION}")
        self.w = np.asarray(d["w"], dtype=float).copy()


class GlobalRng(Module):
    reads = ()
    writes = ()

    def step(self, bb, dt):
        np.random.random()


def test_run_clean_default_recipe():
    rt = K.run_clean(K.recipe("default-v1"), 0.5)
    assert rt.kernel.t > 0 and rt.last_choice in ACTIONS


def test_save_load_identical_minimal(tmp_path):
    K.assert_save_load_identical(K.recipe("minimal-v1"), tmp_path, 0.5 * DAY, 0.25 * DAY)


def test_shadow_does_not_shift_live_actions(tmp_path):
    text = (K.RECIPES / "minimal-v1.toml").read_text(encoding="utf-8")
    shadowed = tmp_path / "minimal-shadow.toml"
    shadowed.write_text(text + '\n[[shadow]]\ntype = "policy.qlearning"\n', encoding="utf-8")
    K.assert_same_live_actions(K.recipe("minimal-v1"), K.recipe(shadowed), days=0.5)


def test_state_roundtrip_with_versioned_module(tmp_path):
    m = VersionedFake({}, np.random.default_rng(0))
    m.w = np.array([0.1, 0.2, 0.3])
    K.assert_state_roundtrip(m, tmp_path)


def test_no_global_rng_minimal(monkeypatch):
    K.assert_no_global_rng(monkeypatch, K.recipe("minimal-v1"), seconds=3600.0)


def test_kit_detects_global_rng(monkeypatch):
    registry.register("test.globalrng", f"{__name__}:GlobalRng")
    try:
        base = K.recipe("minimal-v1")
        rec = Recipe("g", 1, (ModuleSpec("test.globalrng", "g", {}),) + base.modules, base.arbiter)
        with pytest.raises(AssertionError):
            K.assert_no_global_rng(monkeypatch, rec, seconds=3600.0)
    finally:
        registry.REGISTRY.pop("test.globalrng", None)


def test_new_types_registered_lazily():
    from engrama.mind.registry import ModuleUnavailable, build
    names = ("temporal.ctrnn", "world.model", "policy.curious", "policy.thompson", "policy.aif")
    for name in names:
        assert name in registry.REGISTRY
    rng = np.random.default_rng(0)
    for name in names:   # importing the registry never fails; a missing module is only reported at build time
        try:
            build(ModuleSpec(name, name, {}), rng)
        except ModuleUnavailable:
            pass
