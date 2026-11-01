"""Module type registry; classes are imported lazily from dotted strings."""
from __future__ import annotations
import importlib
import numpy as np
from engrama.mind.contracts import Module
from engrama.mind.recipe import ModuleSpec

class ModuleUnavailable(Exception):
    """A module's optional dependency could not be imported."""

REGISTRY: dict[str, str] = {
    "drives.needs": "engrama.modules.drives.needs:NeedDrives",
    "affect.pad": "engrama.modules.affect.pad:PadAffect",
    "policy.utility": "engrama.modules.policy.utility:UtilityPolicy",
    "policy.qlearning": "engrama.modules.policy.qlearning:QLearningPolicy",
    "prefs.food": "engrama.modules.prefs.food:FoodPrefs",
    "traits.drift": "engrama.modules.traits.drift:TraitDrift",
    "temporal.snn": "engrama.modules.temporal.snn:TemporalSNN",
}

def register(type_name: str, dotted: str) -> None:
    REGISTRY[type_name] = dotted

def build(spec: ModuleSpec, rng: np.random.Generator) -> Module:
    if spec.type not in REGISTRY:
        raise KeyError(f"unknown module type {spec.type!r}; known: {', '.join(sorted(REGISTRY))}")
    mod_path, _, cls_name = REGISTRY[spec.type].partition(":")
    try:
        cls = getattr(importlib.import_module(mod_path), cls_name)
    except ImportError as e:
        raise ModuleUnavailable(f"{spec.type}: {e}") from e
    inst = cls(dict(spec.params), rng)
    inst.name = spec.name
    return inst
