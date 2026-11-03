"""Original 10x10 icons and ~2 s joke effects for the digital maintenance items (M7). Nothing here draws
exactly COLORKEY (255, 0, 255)."""
from __future__ import annotations
import math
import pygame

COLORKEY = (255, 0, 255)
DURATION = 2.0

_PAL = {"g": (90, 220, 130), "G": (40, 130, 80), "y": (240, 210, 90), "w": (240, 240, 250),
        "b": (90, 150, 240), "r": (235, 100, 100), "k": (50, 50, 70), "o": (240, 160, 70)}

_ICONS = {
    "ram": ("..........", ".GGGGGGGG.", ".GggggggG.", ".GkkGkkGG.", ".GkkGkkGG.",
            ".GggggggG.", ".GGGGGGGG.", "..y.y.y.y.", "..y.y.y.y.", ".........."),
    "defrag": ("..........", ".bb.rr.bb.", ".bb.rr.bb.", "..........", ".rr.bb.rr.",
               ".rr.bb.rr.", "..........", ".bb.rr.bb.", ".bb.rr.bb.", ".........."),
    "update": ("..........", "..wwwwww..", ".w......w.", ".w.bbbb.w.", ".w.bbbb.w.",
               ".w......w.", ".wwwwwwww.", "....ww....", "...wwww...", ".........."),
    "cache": ("...kkkk...", "..kwwwwk..", "..kwwwwk..", "...kkkk...", "..k.kk.k..",
              ".k..kk..k.", ".k.rrrr.k.", "..krrrrk..", "...rrrr...", ".........."),
    "cooler": ("...wwww...", "..wbwwbw..", ".wwbwwbww.", ".wbbwwbbw.", "wwwwooowww",
               ".wbbwwbbw.", ".wwbwwbww.", "..wbwwbw..", "...wwww...", ".........."),
}

_cache: dict[str, pygame.Surface] = {}


def icon(id: str) -> pygame.Surface:
    s = _cache.get(id)
    if s is None:
        rows = _ICONS.get(id, _ICONS["ram"])
        s = pygame.Surface((10, 10), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row[:10]):
                c = _PAL.get(ch)
                if c is not None:
                    s.set_at((x, y), (*c, 255))
        _cache[id] = s
    return s.copy()


def _star(surface, x, y, r, col) -> None:
    pygame.draw.line(surface, col, (x - r, y), (x + r, y), 2)
    pygame.draw.line(surface, col, (x, y - r), (x, y + r), 2)


def draw_effect(surface: pygame.Surface, id: str, age: float, rect: pygame.Rect) -> bool:
    """Draws one frame of the effect over the creature rect (screen pixels). False when finished/unknown."""
    if age >= DURATION or age < 0 or id not in _ICONS:
        return False
    p = age / DURATION
    cx, cy = rect.center
    if id == "ram":
        x = int(rect.left - 60 + (rect.w // 2 + 60) * min(1.0, p / 0.6))
        r = pygame.Rect(0, 0, 48, 14)
        r.midleft = (x, cy)
        pygame.draw.rect(surface, (90, 220, 130), r, border_radius=2)
        pygame.draw.rect(surface, (40, 130, 80), r, 2, border_radius=2)
        for i in range(4):
            pygame.draw.rect(surface, (50, 50, 70), (r.x + 6 + i * 10, r.y + 3, 6, 5))
        if p > 0.6 and int(age * 10) % 2 == 0:
            _star(surface, r.right, r.top, 5, (255, 250, 200))
    elif id == "defrag":
        n, cell = 4, 14
        ox, oy = cx - n * cell // 2, cy - n * cell // 2
        k = min(1.0, p / 0.8)
        for i in range(n * n):
            col, row = i % n, i // n
            jx = int(math.sin(i * 12.9) * 30 * (1 - k))
            jy = int(math.cos(i * 7.3) * 30 * (1 - k))
            pygame.draw.rect(surface, (90, 150, 240) if (col + row) % 2 == 0 else (235, 100, 100),
                             (ox + col * cell + jx, oy + row * cell + jy, cell - 2, cell - 2))
    elif id == "update":
        bar = pygame.Rect(0, 0, 90, 14)
        bar.midtop = (cx, rect.bottom + 6)
        pygame.draw.rect(surface, (30, 30, 50), bar, border_radius=4)
        fill = bar.inflate(-4, -4)
        fill.w = int(fill.w * min(1.0, p / 0.85))
        if fill.w > 0:
            pygame.draw.rect(surface, (90, 150, 240), fill, border_radius=3)
        pygame.draw.rect(surface, (240, 240, 250), bar, 2, border_radius=4)
    elif id == "cache":
        x = rect.left - 10 + int((rect.w + 20) * p)
        pygame.draw.line(surface, (240, 240, 250), (x, rect.top), (x, rect.bottom), 2)
        for i in range(6):
            _star(surface, x - i * 5, rect.top + 6 + (i * 37) % max(1, rect.h - 12), 3 + (i % 2), (255, 250, 200))
    elif id == "cooler":
        for i in range(5):
            y = rect.top + 8 + i * max(1, (rect.h - 16) // 4)
            ph = (p * 2.5 + i * 0.2) % 1.0
            x0 = rect.left - 70 + int(ph * (rect.w + 100))
            pygame.draw.line(surface, (200, 225, 255), (x0, y), (x0 + 28, y), 2)
            pygame.draw.line(surface, (200, 225, 255), (x0 + 28, y), (x0 + 36, y - 4), 2)
    return True
