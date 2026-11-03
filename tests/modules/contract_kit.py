"""Verificações comuns de módulo e receita experimental (M10).

Cada módulo novo (CTRNN, modelo de mundo, Q curioso, Thompson, inferência ativa) passa por estas funções
nos seus testes. Nada aqui edita o runtime: a corrida repete o corpo de Runtime.run tick a tick.
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from engrama import balance as B
from engrama.lab.runtime import Runtime
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind import registry
from engrama.mind.recipe import Recipe, load_recipe
from engrama.services.persistence import load_run, save_run
from engrama.vocab import ACTIONS

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ROOT / "recipes"
DAY = 86400.0

_NP_GLOBAL = ("random", "rand", "randn", "normal", "uniform", "choice", "integers", "standard_normal", "seed")
_PY_GLOBAL = ("random", "uniform", "choice", "randint", "randrange", "seed", "gauss", "shuffle")


def recipe(name_or_path) -> Recipe:
    """"ctrnn-v1" -> recipes/ctrnn-v1.toml; um caminho (com / ou .toml) é lido como está."""
    s = str(name_or_path)
    path = Path(s) if (s.endswith(".toml") or "/" in s or "\\" in s) else RECIPES / f"{s}.toml"
    return load_recipe(path)


def _user(profile: str = "attentive", seed: int = 1) -> SimUser:
    return SimUser(PROFILES[profile], np.random.default_rng([seed, 1]))


def actions(rt: Runtime, seconds: float, dt: float = 60.0) -> list[str]:
    """Mesmo laço de tests/lab/test_runtime.py: rt.user precisa estar definido."""
    out = []
    end = rt.kernel.t + seconds
    while rt.kernel.t < end - 1e-9:
        out.append(rt.tick(dt, rt.user.events(rt.kernel.t, dt, rt.creature())))
    return out


def mean_ms(rt: Runtime, name: str) -> float:
    return [s for s in rt.scheduler.status() if s.name == name][0].mean_ms


def _check_modules(rt: Runtime) -> None:
    for s in rt.scheduler.status():
        assert s.enabled and not s.error, f"módulo {s.name} desabilitado: {s.error}"


def _check_tick(rt: Runtime, act: str) -> None:
    assert act, "tick sem ação"
    assert act in ACTIONS, f"ação fora de ACTIONS: {act!r}"
    _check_modules(rt)
    for name, v in rt.bb.snapshot().items():
        assert np.all(np.isfinite(v)), f"canal não finito no quadro-negro: {name}"


def _run(rec: Recipe, days: float, profile: str, seed: int, dt: float = 60.0) -> tuple[Runtime, list[str]]:
    """Corpo de Runtime.run, tick a tick, com as checagens do kit; renasce se morrer."""
    rt = Runtime(rec, seed)
    rt.user = _user(profile, seed)
    acts: list[str] = []
    end = rt.kernel.t + days * DAY
    while rt.kernel.t < end - 1e-9:
        step = min(dt, end - rt.kernel.t)
        act = rt.tick(step, rt.user.events(rt.kernel.t, step, rt.creature()))
        _check_tick(rt, act)
        acts.append(act)
        if rt.kernel.dead:
            rt.lives.append(rt.rebirth())
    return rt, acts


def run_clean(rec: Recipe, days: float, profile: str = "attentive", seed: int = 1, dt: float = 60.0) -> Runtime:
    """Falha se: módulo desabilitado (status().error), ação fora de ACTIONS, canal não finito, tick sem ação."""
    rt, _ = _run(rec, days, profile, seed, dt)
    return rt


def _same(a, b) -> None:
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), (sorted(a), sorted(b) if isinstance(b, dict) else b)
        for k in a:
            _same(a[k], b[k])
    elif isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        assert np.array_equal(np.asarray(a), np.asarray(b))
    elif isinstance(a, (list, tuple)):
        assert isinstance(b, (list, tuple)) and len(a) == len(b)
        for x, y in zip(a, b):
            _same(x, y)
    else:
        assert a == b


def assert_save_load_identical(rec: Recipe, tmp_path: Path, before_s: float, after_s: float,
                               profile: str = "attentive", seed: int = 1) -> None:
    """Como test_save_load_continue_identical: ações e necessidades iguais depois de salvar e carregar."""
    ref = Runtime(rec, seed)
    ref.user = _user(profile, seed)
    full = actions(ref, before_s + after_s)
    rt = Runtime(rec, seed)
    rt.user = _user(profile, seed)
    first = actions(rt, before_s)
    rt.save(Path(tmp_path) / "save")
    rt2 = Runtime.load(Path(tmp_path) / "save")
    assert first + actions(rt2, after_s) == full
    assert rt2.kernel.state_dict()["needs"] == ref.kernel.state_dict()["needs"]


def assert_same_live_actions(rec_a: Recipe, rec_b: Recipe, days: float = 2.0, seed: int = 1,
                             profile: str = "attentive") -> None:
    """Dois mundos com as mesmas sementes têm as mesmas ações ao vivo (sombras não mexem no fluxo ao vivo)."""
    _, a = _run(rec_a, days, profile, seed)
    _, b = _run(rec_b, days, profile, seed)
    assert a == b


def assert_state_roundtrip(module, tmp_path: Path) -> None:
    """save_run/load_run reais com {"m": state}; estado igual; versão M10; {} mantém o inicial; versão nova falha."""
    cls, params = type(module), dict(module.params)
    state = module.state_dict()
    assert state.get("version") == B.M10_STATE_VERSION
    save_run(Path(tmp_path) / "s", {}, {"m": state}, {})
    _, mods, _ = load_run(Path(tmp_path) / "s")
    fresh = cls(params, np.random.default_rng(0))
    fresh.load_state_dict(mods["m"])
    _same(fresh.state_dict(), state)
    initial = cls(params, np.random.default_rng(0))
    blank = cls(params, np.random.default_rng(0))
    blank.load_state_dict({})
    _same(blank.state_dict(), initial.state_dict())
    with pytest.raises(ValueError):
        cls(params, np.random.default_rng(0)).load_state_dict({"version": B.M10_STATE_VERSION + 1})


def assert_no_global_rng(monkeypatch, rec: Recipe, seconds: float = 3600.0, profile: str = "attentive",
                         seed: int = 1) -> None:
    """Depois de construir o Runtime, qualquer sorteio pelo RNG global falha; o módulo que o usar é desabilitado
    pelo agendador, então o status é checado no fim."""
    rt = Runtime(rec, seed)
    rt.user = _user(profile, seed)

    def _boom(*a, **k):
        raise AssertionError("RNG global usado")

    for name in _NP_GLOBAL:
        monkeypatch.setattr(np.random, name, _boom, raising=False)
    for name in _PY_GLOBAL:
        monkeypatch.setattr(random, name, _boom, raising=False)
    actions(rt, seconds)
    _check_modules(rt)
