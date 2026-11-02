"""Original V-Pet style procedural creatures (14 archetypes x 4 poses). Public entry: creature_frames()."""
from collections import OrderedDict

import numpy as np

from engrama.vocab import BRANCHES

from .anim import ANIM_FRAMES, frame_arrays
from .archetypes import ARCHS, BABIES
from .core import PX, STAGES
from .plan import STYLE, archetype, branch_at, genes
from .render import Sprite, build

__all__ = ["ARCHS", "BABIES", "ANIM_FRAMES", "PX", "STAGES", "archetype", "branch_at", "creature_frames",
           "known_lineage", "build_sprite"]

_KNOWN = frozenset(b for bs in BRANCHES.values() for b in bs)
_SPRITES: "OrderedDict[tuple, Sprite]" = OrderedDict()
_SPRITES_MAX = 24


def known_lineage(lineage) -> tuple:
    return tuple(b for b in (lineage or ()) if isinstance(b, str) and b in _KNOWN)


def build_sprite(look, stage: str, branch: str = "base", lineage=()) -> Sprite:
    """Eyeless body render for (look, stage); cached (small LRU, animations share it)."""
    lin = known_lineage(lineage)
    bid = branch_at(stage, branch, lin)
    key = (look.seed, look.body, look.eyes, look.ears, look.tail, look.pattern, tuple(look.palette[1]), stage, bid, lin)
    hit = _SPRITES.get(key)
    if hit is not None:
        _SPRITES.move_to_end(key)
        return hit
    g = genes(look)
    arch = archetype(look.seed, stage, lin, bid if bid != "base" else "base")
    kind = archetype(look.seed, "baby")
    sp = build(g, stage, arch, STYLE.get(bid, "base"), bid, kind)
    _SPRITES[key] = sp
    while len(_SPRITES) > _SPRITES_MAX:
        _SPRITES.popitem(last=False)
    return sp


def creature_frames(look, stage: str, anim: str, branch: str = "base", lineage=()) -> list:
    """RGBA uint8 arrays (N, N, 4), 2-4 per anim."""
    return frame_arrays(build_sprite(look, stage, branch, lineage), anim)
