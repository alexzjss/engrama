"""Immutable, deep-copied view of the creature and its mind, published by the Host for the UI.

Imports only stdlib and numpy: the UI must never reach into the kernel or the mind.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Any
import numpy as np


@dataclass(frozen=True)
class Viz:
    kind: str
    title: str
    data: Any


@dataclass(frozen=True)
class ProposalView:
    action: str
    score: float
    reason: str
    source: str = ""


@dataclass(frozen=True)
class ModuleView:
    name: str
    type: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    shadow: bool
    mean_ms: float
    rate_factor: float
    disabled: bool


@dataclass(frozen=True)
class Snapshot:
    t: float = 0.0
    wall: float = 0.0
    stage: str = "egg"
    action: str = "idle"
    asleep: bool = False
    egg_clicks: int = 0
    needs: dict[str, float] = field(default_factory=dict)
    pad: tuple[float, float, float] = (0.0, 0.0, 0.0)
    pad_label: str = "neutral"
    traits: dict[str, float] = field(default_factory=dict)
    food_liking: dict[str, float] = field(default_factory=dict)
    surprise: float = 0.0
    familiarity: float = 0.0
    look: dict = field(default_factory=dict)
    proposals: tuple[ProposalView, ...] = ()
    shadow_proposals: tuple[ProposalView, ...] = ()
    winner: str = ""
    modules: tuple[ModuleView, ...] = ()
    viz: dict[str, tuple[Viz, ...]] = field(default_factory=dict)
    recipe_name: str = ""
    recipe_version: int = 0
    resting: bool = False
    rest_reason: str = ""
    eyes_closed: bool = False
    branch: str = "base"
    branch_name: str = ""
    lineage: tuple = ()
    generation: int = 1
    sick: bool = False
    sick_kind: str = ""
    grave: bool = False
    old: bool = False
    dead: bool = False
    death_cause: str = ""
    evolved_at: float = float("-inf")   # host wall time of the last evolution


def plain(x: Any) -> Any:
    """Deep copy into plain Python: arrays -> lists, numpy scalars -> numbers, tuples -> lists."""
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return [plain(v) for v in sorted(x, key=str)]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return copy.deepcopy(x)


def to_viz(spec) -> Viz:
    """Convert a mind VizSpec (duck-typed: .kind, .title, .data) into a Viz that shares nothing live."""
    return Viz(str(spec.kind), str(spec.title), plain(spec.data))
