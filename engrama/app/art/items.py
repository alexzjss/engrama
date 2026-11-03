"""Tiny 8x8 pixel items the creature can bring (never uses the overlay colour key)."""
import pygame

_PAL = {"k": (40, 32, 36), "w": (240, 236, 220), "g": (200, 196, 180), "b": (60, 120, 200), "c": (110, 220, 180),
        "s": (150, 150, 160), "d": (100, 100, 110), "y": (245, 215, 90), "o": (210, 170, 110)}
_ART = {
    "osso": ["........", ".kk..kk.", "kwwkkwwk", ".kwwwwk.", "..kwwk..", ".kwwwwk.", "kwwkkwwk", ".kk..kk."],
    "chip": ["k.k.k.k.", "kkkkkkkk", "kccccccd", "kcbbbbcd", "kcbyybcd", "kcbbbbcd", "kkkkkkkk", "k.k.k.k."],
    "pedra": ["........", "........", "..kkkk..", ".kssssk.", "kssgsssk", "ksssssdk", ".kddddk.", "..kkkk.."],
    "arquivo": ["kkkkkk..", "kwwwwkk.", "kwbbwwkk", "kwwwwwwk", "kwbbbbwk", "kwwwwwwk", "kwbbbwwk", "kkkkkkkk"],
}
_cache: dict[str, pygame.Surface] = {}


def found_item(kind: str) -> pygame.Surface:
    """8x8 SRCALPHA surface for kind in osso/chip/pedra/arquivo (unknown kinds draw as pedra); cached."""
    if kind not in _ART:
        kind = "pedra"
    s = _cache.get(kind)
    if s is None:
        s = pygame.Surface((8, 8), pygame.SRCALPHA)
        for y, row in enumerate(_ART[kind]):
            for x, ch in enumerate(row):
                if ch in _PAL:
                    s.set_at((x, y), (*_PAL[ch], 255))
        _cache[kind] = s
    return s
