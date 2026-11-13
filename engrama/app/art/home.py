"""Home objects of the terrarium: a nest for the egg, then a bowl, a toy, a bed and a plant as the creature grows.

Tiny bitmaps coloured from the creature's own palette (body and accent), so each home matches who lives in it."""
from __future__ import annotations
import pygame

# what the home holds at each stage (it only ever gains things); the nest is the egg's alone
BY_STAGE = {"egg": ("nest",), "baby": ("bowl",), "child": ("bowl", "ball"), "adult": ("bowl", "ball", "bed"),
            "perfect": ("bowl", "ball", "bed", "plant"), "final": ("bowl", "ball", "bed", "plant")}
# where each one stands: fraction of the scene width (centre), and px above the creature's ground line
SPOTS = {"nest": (0.5, 0), "bed": (0.17, 3), "ball": (0.34, 1), "bowl": (0.72, 2), "plant": (0.9, 5)}

_ART = {
    "nest": ("......................", "..sS..............Ss..", ".sSssSsSssSssSsSssSsS.", "kSsSssSsSSsSssSsSSsSsk",
             ".kSsSsSSsSsSsSsSSsSsk.", "..kkSsSsSsSSsSsSsSkk..", "....kkkkkkkkkkkkkk...."),
    "bowl": ("...f.ff.f...", "..ffffffff..", "kkkkkkkkkkkk", "kaaaaaaaaaak", ".kaAaaaaAak.", ".kaaaaaaaak.",
             "..kkkkkkkk.."),
    "ball": ("..kkk..", ".kawak.", "kaawaak", "kwwwwwk", "kaawaak", ".kawak.", "..kkk.."),
    "bed": ("kkk.....................", "kbbk....................", "kbbkkkkkkkkkkkkkkkkkkkk.", "kbbwwwkaaaaaaaaaaaaaaaak",
            "kbbwwwkaaaaaaaaaaaaaaAak", "kbbkkkkaaaaaaaaaaaaaaaak", "kkkkkkkkkkkkkkkkkkkkkkkk", ".k....................k."),
    "plant": ("....g....", "...gGg...", ".g.gGg.g.", "gGg.G.gGg", ".gGgGgGg.", "..gGGGg..", "....G....", ".kkkkkkk.",
              ".kttttTk.", ".kttttTk.", "..ktttk..", "..ktTTk..", "..kkkkk.."),
}
_FIXED = {"k": (40, 32, 36), "w": (250, 246, 236), "s": (214, 180, 110), "S": (170, 130, 70), "g": (110, 190, 100),
          "G": (60, 130, 70), "t": (196, 116, 84), "T": (150, 80, 60), "f": (176, 120, 70)}
_cache: dict[tuple, pygame.Surface] = {}


def _dark(c) -> tuple[int, int, int]:
    return tuple(int(x * 0.7) for x in c)


def item(kind: str, palette) -> pygame.Surface:
    """SRCALPHA bitmap of a home object in the creature's colours (palette as in sprites.Look); cached."""
    body, accent = tuple(palette[1]), tuple(palette[3])
    key = (kind, body, accent)
    s = _cache.get(key)
    if s is None:
        rows = _ART[kind]
        cols = dict(_FIXED, a=accent, A=_dark(accent), b=body, B=_dark(body))
        s = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in cols:
                    s.set_at((x, y), (*cols[ch], 255))
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = s
    return s


def items_for(stage: str) -> tuple[str, ...]:
    return BY_STAGE.get(stage, ())
