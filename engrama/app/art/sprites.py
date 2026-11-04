"""Procedural pixel sprites: the original V-Pet style creatures and eggs of engrama.app.art.vpet (M11).

Each creature belongs to one of 8 families with 3 body plans, fixed for life by the seed; stages grow the same body,
branches add accessories that accumulate. Animations are whole-sprite transforms plus face stamps. All drawing is
cached (bounded LRU), never per frame.
"""
import colorsys
import random
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import pygame

from engrama.app.art import vpet
from engrama.app.art.vpet import anim as vpet_anim
from engrama.app.art.vpet import core as vpet_core


@dataclass(frozen=True)
class Look:
    """Visual traits of a creature. Built from the kernel genome dict, tolerant of missing/extra keys."""
    seed: int = 0
    body: int = 0
    eyes: int = 0
    ears: int = 0
    tail: int = 0
    pattern: int = 0
    palette: tuple = ((40, 30, 60), (240, 140, 120), (190, 90, 100), (250, 220, 120))
    voice_pitch: float = 300.0
    branch: str = "base"
    lineage: tuple = ()

    @classmethod
    def from_dict(cls, d: dict | None) -> "Look":
        d = d or {}
        base = cls()

        def num(key, default, cast):
            try:
                return cast(d.get(key, default))
            except (TypeError, ValueError):
                return default

        pal = list(base.palette)
        try:
            for i, c in enumerate(list(d.get("palette") or [])[:4]):
                pal[i] = tuple(max(0, min(255, int(x))) for x in list(c)[:3])
                if len(pal[i]) != 3:
                    pal[i] = base.palette[i]
        except (TypeError, ValueError):
            pal = list(base.palette)
        br = d.get("branch")
        lin = d.get("lineage")
        try:
            lineage = tuple(str(x) for x in lin) if isinstance(lin, (list, tuple)) else ()
        except (TypeError, ValueError):
            lineage = ()
        return cls(branch=br if isinstance(br, str) and br else "base", lineage=lineage,
                   seed=num("seed", 0, int), body=num("body", 0, int), eyes=num("eyes", 0, int),
                   ears=num("ears", 0, int), tail=num("tail", 0, int), pattern=num("pattern", 0, int),
                   palette=tuple(pal), voice_pitch=num("voice_pitch", 300.0, float))

_look_cache: tuple[dict | None, "Look"] | None = None


def look_of(d: dict | None) -> Look:
    """`Look.from_dict` with a one-entry cache keyed by the identity of `d` (snapshots reuse the same dict every frame)."""
    global _look_cache
    c = _look_cache
    if c is not None and c[0] is d:
        return c[1]
    look = Look.from_dict(d)
    _look_cache = (d, look)
    return look


ANIMS = ("idle", "walk", "eat", "sleep", "happy", "sad", "sick", "evolve", "old", "dead")

SIZES = {"egg": 16, "baby": 24, "child": 32, "adult": 40, "perfect": 44, "final": 48}

# egg-only effects for the evolve/dead anims (creatures use vpet.anim)
EGG_FX = {
    "evolve": [{"bright": b} for b in (0.2, 0.45, 0.7, 0.92)],
    "dead": [{"gray": 0.3, "fade": 0.85}, {"gray": 0.4, "fade": 0.5}],
}

_CACHE_MAX = 400
_cache: "OrderedDict[tuple, list[pygame.Surface]]" = OrderedDict()


# --- egg ----------------------------------------------------------------------------------------------------
CRACKS = [[(7, 3), (8, 4), (7, 5)],
          [(6, 6), (7, 7), (6, 8), (7, 9)],
          [(9, 5), (10, 6), (9, 7), (10, 8), (5, 9), (4, 10), (5, 11)]]


def _egg_array(genome, dx: int = 0, crack: int = 0, fx: dict | None = None) -> np.ndarray:
    a = vpet.egg_array(genome, dx).copy()
    for lv in range(crack):
        for x, y in CRACKS[lv]:
            x += dx
            if 0 <= x < 16 and a[y, x, 3]:
                a[y, x] = (*vpet_core.OUT, 255)
    if crack >= 3:  # shell chipped open at the top
        for x in (7, 8):
            a[2, x + dx] = (250, 250, 250, 255)
    if fx:
        a = vpet_anim._color(a, fx)
    return a


def make_egg_crack(genome, level: int) -> pygame.Surface:
    level = max(0, min(3, int(level)))
    return _surface(_egg_array(genome, 0, level))


def _surface(arr: np.ndarray) -> pygame.Surface:
    n = arr.shape[0]
    return pygame.image.frombuffer(np.ascontiguousarray(arr).tobytes(), (n, n), "RGBA")


def _key(look, stage: str, anim: str, lineage: tuple) -> tuple:
    return (look.seed, tuple(look.palette[1]), stage, anim, lineage)


def frames(look, stage: str, anim: str) -> list[pygame.Surface]:
    """2-4 transparent frames for (look, stage, anim). Cached (bounded LRU); callers must not mutate the surfaces.

    Only the look's seed, main colour (palette[1]), branch and lineage matter; unknown branch ids are ignored."""
    if anim not in ANIMS:
        raise ValueError(f"unknown anim {anim!r}")
    if stage not in SIZES:
        raise ValueError(f"unknown stage {stage!r}")
    branch = getattr(look, "branch", "base") or "base"
    lin = vpet.full_lineage(branch, getattr(look, "lineage", ()) or ())
    if stage != "egg":   # only the branches up to this stage can change the drawing
        upto = vpet.STAGES.index(stage)
        lin = tuple(b for b in lin if vpet.gen.BRANCH_STAGE[b] <= upto)
    else:
        lin = ()
    key = _key(look, stage, anim, lin)
    hit = _cache.get(key)
    if hit is not None:
        _cache.move_to_end(key)
        return hit
    if stage == "egg":
        if anim in EGG_FX:
            out = [_surface(_egg_array(look, 0, fx=p)) for p in EGG_FX[anim]]
        else:
            wobble = [0, 1, 0, -1] if anim == "idle" else [0, 1]
            out = [_surface(_egg_array(look, dx)) for dx in wobble]
    else:
        out = [_surface(a) for a in vpet.creature_frames(look, stage, anim, "base", lin)]
    _cache[key] = out
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return out


make_frames = frames  # v1 name


# --- food icons (8x8) -------------------------------------------------------------------------------------
_PAL = {"r": (200, 60, 60), "R": (140, 30, 40), "o": (230, 150, 60), "y": (240, 220, 90), "g": (90, 190, 90),
        "G": (40, 120, 70), "b": (90, 150, 240), "B": (40, 70, 160), "w": (245, 245, 245), "k": (40, 36, 50),
        "n": (150, 100, 60), "N": (95, 60, 40), "p": (230, 140, 190), "s": (170, 175, 195), "S": (110, 115, 140),
        "c": (120, 230, 240), "0": (40, 120, 90), "1": (90, 220, 120)}

_ICONS = {
    "carne": ["........", "..NNNN..", ".NrrrrN.", ".NrRrrN.", ".NrrrRN.", "..NrrN..", "...ww...", "...w...."],
    "fruta": ["....g...", "...gG...", "..rrrr..", ".rrwrrr.", ".rrrrrr.", ".rrrrRr.", "..rrrR..", "........"],
    "peixe": ["........", "..bbb..b", ".bwkbbbb", "bbbbbbbB", ".bbbbbbb", "..bbb..b", "........", "........"],
    "bolinho": ["........", "...pp...", "..pppp..", ".pwpwpp.", "..oooo..", ".oooooo.", ".oyoyoo.", "..oooo.."],
    "pacote": ["..cccc..", ".cbbbbc.", "cb0101bc", "cb1010bc", "cb0101bc", "cbbbbbbc", ".cbbbbc.", "..cccc.."],
    "cookie": ["........", "..nnnn..", ".nNnnNn.", "nnnNnnnn", "nNnnnnNn", "nnnNnnnn", ".nnnNnn.", "..nnnn.."],
    "bug": ["g..kk..g", ".g.kk.g.", "..kooK..", "gkoookKg", "..kooK..", ".gkoKg..", "g..kk..g", "........"],
    "cache": ["..r..r..", "...r.r..", "........", ".ssssss.", "sooooooS", "soyyyyoS", "sooooooS", ".SSSSSS."],
    "byte": ["........", ".yyyyyy.", "yykkykky", "yykyykky", "yykkykky", "yyykkyyy", ".yyyyyy.", "........"],
    "ram": ["GGGGGGGG", "GkkGkkkG", "GkkGkkkG", "GGGGGGGG", "GkkGkkkG", "GkkGkkkG", "GGGGGGGG", "y.y.y.y."],
    "remedio": ["........", "..wwww..", ".wwrrww.", "wwwrrwww", "wrrrrrrw", "wwwrrwww", ".wwrrww.", "..wwww.."],
}
_icon_cache: dict[str, pygame.Surface] = {}


def food_icon(food_id: str) -> pygame.Surface:
    if food_id not in _icon_cache:
        s = pygame.Surface((8, 8), pygame.SRCALPHA)
        for y, row in enumerate(_ICONS[food_id]):
            for x, ch in enumerate(row[:8]):
                if ch in _PAL:
                    s.set_at((x, y), _PAL[ch])
        _icon_cache[food_id] = s
    return _icon_cache[food_id]



# --- contact sheet ----------------------------------------------------------------------------------------
def _demo_look(seed: int) -> Look:
    r = random.Random(seed)
    h = r.random()

    def hsv(hh, sat, v):
        return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hh % 1.0, sat, v))
    pal = (hsv(h, 0.6, 0.22), hsv(h, 0.5, 0.92), hsv(h, 0.65, 0.68), hsv(h + 0.45, 0.6, 1.0))
    return Look(seed=seed, body=r.randrange(6), eyes=r.randrange(4), ears=r.randrange(5),
                tail=r.randrange(4), pattern=r.randrange(4), palette=pal, voice_pitch=r.uniform(180, 520))


def contact_sheet(path: str = "data/contact_sheet.png", seeds: int = 12, scale: int = 3) -> None:
    import os
    stages = ("egg", "baby", "child", "adult", "perfect", "final")
    cell = 48 * scale + 8
    sheet = pygame.Surface((cell * len(stages), cell * seeds), pygame.SRCALPHA)
    sheet.fill((46, 44, 62))
    for row in range(seeds):
        g = _demo_look(row + 1)
        for col, stage in enumerate(stages):
            f = frames(g, stage, "idle")[0]
            big = pygame.transform.scale(f, (f.get_width() * scale, f.get_height() * scale))
            sheet.blit(big, (col * cell + (cell - big.get_width()) // 2, row * cell + cell - 4 - big.get_height()))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pygame.image.save(sheet, path)


if __name__ == "__main__":
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    contact_sheet()
    print("wrote data/contact_sheet.png")
