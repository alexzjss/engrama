"""Shared helpers for reading optional channels."""
from __future__ import annotations
from engrama.mind.contracts import Blackboard
from engrama.vocab import TRAIT_KEYS, INITIAL_TRAITS


def default_traits() -> dict[str, float]:
    return {k: INITIAL_TRAITS[k] / 100.0 for k in TRAIT_KEYS}


def read_traits(bb: Blackboard) -> dict[str, float]:
    """Traits 0..1 by name; INITIAL_TRAITS/100 when the channel is absent."""
    v = bb.get("traits")
    if v is None:
        return default_traits()
    return {k: float(x) for k, x in zip(TRAIT_KEYS, v)}
