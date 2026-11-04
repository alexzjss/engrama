"""Original V-Pet style procedural creatures (M11): 8 families x 3 body plans, fixed for life by the seed.

Public entries: creature_frames() (RGBA arrays per anim), build_sprite() (cached eyeless body + face data),
egg_array() (the 16 px family egg). Everything is a pure function of (look.seed, look.palette[1], stage, lineage);
no Genome fields are needed beyond the M1 ones, so old saves render.
"""
from collections import OrderedDict

import numpy as np

from engrama.vocab import BRANCHES

from .anim import ANIM_FRAMES, POSES, frame_arrays, poses_for
from .gen import MAX_ACC, SIZES, STAGES, Sprite, branch_at, egg, sprite
from .genes import FAMILIES, FAMILY_PT, family_of, genes

__all__ = ["ANIM_FRAMES", "FAMILIES", "FAMILY_PT", "MAX_ACC", "POSES", "PX", "STAGES", "Sprite", "branch_at", "build_sprite",
           "creature_frames", "egg_array", "family_of", "full_lineage", "genes", "known_lineage", "plan_of"]

PX = tuple(SIZES[s] for s in STAGES)
_KNOWN = frozenset(b for bs in BRANCHES.values() for b in bs)
_SPRITES: "OrderedDict[tuple, Sprite]" = OrderedDict()
_SPRITES_MAX = 24


def known_lineage(lineage) -> tuple:
    return tuple(b for b in (lineage or ()) if isinstance(b, str) and b in _KNOWN)


def full_lineage(branch: str, lineage) -> tuple:
    """The saved lineage plus the current branch (if known and not already its last entry)."""
    lin = known_lineage(lineage)
    if branch in _KNOWN and (not lin or lin[-1] != branch):
        lin = lin + (branch,)
    return lin


def plan_of(seed: int) -> int:
    return genes(seed)["plan"]


def _hue(look):
    try:
        c = tuple(int(x) for x in look.palette[1][:3])
        return c if len(c) == 3 else None
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def build_sprite(look, stage: str, branch: str = "base", lineage=()) -> Sprite:
    """Eyeless body + face data for (look, stage); cached (small LRU, the animations share it)."""
    lin = full_lineage(branch, lineage)
    hue = _hue(look)
    key = (int(look.seed), hue, stage, lin)
    hit = _SPRITES.get(key)
    if hit is not None:
        _SPRITES.move_to_end(key)
        return hit
    sp = sprite(int(look.seed), stage, lineage=lin, hue_rgb=hue)
    _SPRITES[key] = sp
    while len(_SPRITES) > _SPRITES_MAX:
        _SPRITES.popitem(last=False)
    return sp


def creature_frames(look, stage: str, anim: str, branch: str = "base", lineage=()) -> list:
    """RGBA uint8 arrays (N, N, 4), 2-4 per anim."""
    sp = build_sprite(look, stage, branch, lineage)
    return frame_arrays(sp, anim, poses_for(sp, anim))


def egg_array(look, dx: int = 0):
    """16x16 RGBA egg in the family colour with its motif, shifted `dx` px (idle wobble)."""
    a = egg(int(look.seed), _hue(look))
    if dx:
        a = np.roll(a, dx, axis=1)
        if dx > 0:
            a[:, :dx] = 0
        else:
            a[:, dx:] = 0
    return a
