"""Emotes: small particles above the creature that show what the mind feels (PAD) without a single number.

Stateless: every position is a function of the clock, so a frame can be redrawn at any time and tests are exact."""
from __future__ import annotations
import math
import pygame

_ART = {
    "heart": ((236, 90, 130), (".##.##.", "#######", "#######", ".#####.", "..###..", "...#...")),
    "note": ((250, 236, 150), ("..###", "..#.#", "..#.#", "..#..", ".##..", "###..", ".#...")),
    "drop": ((120, 190, 250), ("..#..", "..#..", ".###.", ".###.", "#####", "#####", ".###.")),
    "bolt": ((250, 210, 80), ("...##", "..##.", ".###.", "####.", "..##.", ".##..", ".#...")),
    "z": ((236, 240, 255), ("#####", "...#.", "..#..", ".#...", "#####")),
    "zs": ((236, 240, 255), ("###", ".#.", "###")),
}
OUTLINE = (40, 32, 50)
AMBIENT_CYCLE = 9.0     # an ambient emote shows for AMBIENT_ON seconds out of every cycle
AMBIENT_ON = 2.6
BURST_SECONDS = 1.3
_cache: dict[str, pygame.Surface] = {}


def glyph(kind: str) -> pygame.Surface:
    """The emote bitmap with a 1 px dark outline, so it reads on the sky and on the grass alike."""
    s = _cache.get(kind)
    if s is None:
        col, rows = _ART[kind]
        w, h = len(rows[0]), len(rows)
        s = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        cells = [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "#"]
        for x, y in cells:
            for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
                s.set_at((x + dx, y + dy), OUTLINE)
        for x, y in cells:
            s.set_at((x + 1, y + 1), col)
        _cache[kind] = s
    return s


def ambient_kind(asleep: bool, pad, sick: bool = False) -> str:
    """Which emote the current state calls for ("" = none): sleep first, then the PAD quadrants."""
    if asleep:
        return "z"
    if sick or not pad:
        return ""
    v, a = float(pad[0]), float(pad[1]) if len(pad) > 1 else 0.0
    if v < -0.35:
        return "bolt" if a > 0.3 else "drop"
    if v > 0.45 and a > 0.2:
        return "note"
    return ""


def ambient_visible(kind: str, now: float) -> bool:
    return kind == "z" or (bool(kind) and now % AMBIENT_CYCLE < AMBIENT_ON)


def draw_ambient(surface: pygame.Surface, kind: str, r: pygame.Rect, now: float) -> None:
    """r is the creature rect on `surface`."""
    if not ambient_visible(kind, now):
        return
    if kind == "z":   # two Zs leave the head one after the other, growing as they rise
        for i in range(2):
            ph = (now / 2.4 + i * 0.5) % 1.0
            g = glyph("zs" if ph < 0.45 else "z")
            surface.blit(g, (r.right - 3 + int(ph * 9), r.y - 2 - int(ph * 13)))
        return
    g = glyph(kind)
    ph = (now % AMBIENT_CYCLE) / AMBIENT_ON
    x = r.right - 2 + (int(math.sin(now * 6) * 1.5) if kind == "note" else 0)
    y = r.y - 6 - int(ph * 5) + (int(ph * 9) if kind == "drop" else 0)
    surface.blit(g, (x, y))


def draw_burst(surface: pygame.Surface, kind: str, r: pygame.Rect, age: float) -> bool:
    """Three emotes fanning out above the creature; False once the burst is over."""
    if not 0.0 <= age < BURST_SECONDS:
        return False
    g = glyph(kind)
    k = age / BURST_SECONDS
    for i, dx in enumerate((-1, 0, 1)):
        ki = max(0.0, k - i * 0.12)
        if ki <= 0.0 and i:
            continue
        surface.blit(g, g.get_rect(center=(r.centerx + int(dx * (4 + 12 * ki)), r.y - 3 - int(16 * ki) + abs(dx) * 3)))
    return True
