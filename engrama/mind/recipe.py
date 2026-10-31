"""TOML recipes: which modules make up a mind."""
from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ModuleSpec:
    type: str
    name: str
    params: dict
    weight: float = 1.0
    shadow: bool = False

@dataclass(frozen=True)
class Recipe:
    name: str
    version: int
    modules: tuple[ModuleSpec, ...]
    arbiter: dict

_RECIPE_KEYS = {"name", "version"}
_ARBITER_KEYS = {"temperature", "trait_temperature"}
_RESERVED = {"type", "name", "weight"}

def _spec(d: dict, shadow: bool) -> ModuleSpec:
    if "type" not in d:
        raise ValueError("module entry missing key 'type'")
    params = {k: v for k, v in d.items() if k not in _RESERVED}
    return ModuleSpec(type=d["type"], name=d.get("name", d["type"]), params=params,
                      weight=float(d.get("weight", 1.0)), shadow=shadow)

def load_recipe(path: Path) -> Recipe:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    head = raw.get("recipe")
    if not isinstance(head, dict):
        raise ValueError("missing [recipe] table")
    for k in head:
        if k not in _RECIPE_KEYS:
            raise ValueError(f"unknown key in [recipe]: {k}")
    if "name" not in head:
        raise ValueError("missing key in [recipe]: name")
    arb = dict(raw.get("arbiter", {}))
    for k in arb:
        if k not in _ARBITER_KEYS:
            raise ValueError(f"unknown key in [arbiter]: {k}")
    arb.setdefault("temperature", 1.0)
    arb.setdefault("trait_temperature", True)
    specs = [_spec(d, False) for d in raw.get("module", [])] + [_spec(d, True) for d in raw.get("shadow", [])]
    seen: set[str] = set()
    for s in specs:
        if s.name in seen:
            raise ValueError(f"duplicate module name: {s.name}")
        seen.add(s.name)
    return Recipe(name=head["name"], version=int(head.get("version", 1)), modules=tuple(specs), arbiter=arb)
