"""The terrarium backdrop: sky by the hour (sun, moon, stars, clouds), two rows of hills and a grass floor.

Procedural like the sprites: a pure function of (size, hour, seed), drawn at the low scene resolution in flat
bands so it upscales as pixel art. The scene caches one backdrop per quarter of an hour."""
from __future__ import annotations
import math
import random
import pygame

HORIZON = 0.62       # fraction of the height where the grass starts
BANDS = 12

# hour -> (sky top, sky at the horizon, light on the land)
_KEYS = ((0.0, (12, 14, 36), (28, 32, 66), 0.45), (5.0, (26, 28, 66), (84, 62, 104), 0.5),
         (6.5, (86, 112, 184), (248, 176, 136), 0.82), (9.0, (74, 146, 228), (176, 218, 246), 1.0),
         (16.0, (74, 146, 228), (176, 218, 246), 1.0), (18.5, (70, 78, 158), (250, 152, 104), 0.8),
         (20.0, (24, 24, 62), (72, 52, 102), 0.55), (24.0, (12, 14, 36), (28, 32, 66), 0.45))
GRASS = ((112, 174, 98), (98, 162, 90), (86, 148, 84))   # far to near
NIGHT_TINT = (40, 50, 110)


def mix(a, b, k: float) -> tuple[int, int, int]:
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))


def sky_at(hour: float) -> tuple[tuple, tuple, float]:
    """(top colour, horizon colour, land light 0..1) at a local hour."""
    hour = hour % 24.0
    for (h0, t0, b0, l0), (h1, t1, b1, l1) in zip(_KEYS, _KEYS[1:]):
        if h0 <= hour <= h1:
            k = (hour - h0) / (h1 - h0)
            return mix(t0, t1, k), mix(b0, b1, k), l0 + (l1 - l0) * k
    return _KEYS[0][1], _KEYS[0][2], _KEYS[0][3]


def lit(col, light: float) -> tuple[int, int, int]:
    """A land colour under `light`: darker and bluer as the night comes."""
    return mix(NIGHT_TINT, col, 0.25 + 0.75 * light) if light < 1.0 else tuple(col)


def is_night(hour: float) -> bool:
    return not 6.0 <= hour % 24.0 < 19.0


def _cloud(s: pygame.Surface, x: int, y: int, r: int, col, shade) -> None:
    for dx, dy, rr in ((0, 0, r), (r, -r // 2, r), (2 * r, 0, r - 1), (r, 1, r)):
        pygame.draw.circle(s, col, (x + dx, y + dy), rr)
    s.fill(shade, (x - r + 1, y + r - 1, 4 * r - 3, 1))


def backdrop(size: tuple[int, int], hour: float, seed: int = 0) -> tuple[pygame.Surface, tuple[int, int, int]]:
    """The backdrop surface and the colour of a shadow cast on its grass."""
    w, h = size
    hour = hour % 24.0
    top, low, light = sky_at(hour)
    rnd = random.Random(1009 + seed)
    s = pygame.Surface((w, h))
    horizon = int(h * HORIZON)
    # sky: flat bands, with a dithered row where two bands meet
    bh = max(1, math.ceil(horizon / BANDS))
    for i in range(BANDS):
        col = mix(top, low, i / (BANDS - 1))
        s.fill(col, (0, i * bh, w, bh))
        if i:
            for x in range(i % 2, w, 2):
                s.set_at((x, i * bh - 1), col)
    night = is_night(hour)
    if night:
        for _ in range(w * horizon // 260):
            x, y = rnd.randrange(w), rnd.randrange(max(1, horizon - 8))
            s.set_at((x, y), (250, 250, 230) if rnd.random() < 0.3 else (170, 176, 214))
        p = ((hour - 19.0) % 24.0) / 11.0
        mx, my = int(w * (0.12 + 0.76 * p)), int(horizon * (0.8 - 0.62 * math.sin(math.pi * p)))
        pygame.draw.circle(s, (236, 236, 214), (mx, my), 6)
        pygame.draw.circle(s, mix(top, low, my / max(1, horizon)), (mx + 3, my - 2), 5)   # the bite: a crescent
    else:
        p = (hour - 6.0) / 13.0
        sx, sy = int(w * (0.1 + 0.8 * p)), int(horizon * (0.86 - 0.7 * math.sin(math.pi * p)))
        pygame.draw.circle(s, mix(mix(top, low, sy / max(1, horizon)), (255, 244, 190), 0.35), (sx, sy), 9)
        pygame.draw.circle(s, (255, 240, 170), (sx, sy), 6)
        pygame.draw.circle(s, (255, 250, 220), (sx - 1, sy - 1), 3)
    cloud = mix(low, (255, 255, 255), 0.75 if not night else 0.12)
    shade = mix(cloud, low, 0.45)
    drift = int(hour * 5)
    for i in range(3):
        cx = (rnd.randrange(w) + drift * (i + 1)) % (w + 30) - 15
        _cloud(s, cx, int(horizon * (0.16 + 0.2 * i)) + rnd.randrange(5), 4 + rnd.randrange(3), cloud, shade)
    # hills: the far row takes more of the sky colour
    for k, amp, freq, base in ((0.55, 7, 0.043, 10), (0.25, 5, 0.071, 4)):
        col = mix(lit(GRASS[0], light), low, k)
        ph = rnd.random() * 6.28
        pts = [(x, horizon - base - int(amp * (math.sin(x * freq + ph) + 0.5 * math.sin(x * freq * 2.3 + 1.7))))
               for x in range(0, w + 2, 2)]
        pygame.draw.polygon(s, col, [(0, horizon), *pts, (w, horizon)])
        if k < 0.5:   # a few round trees on the near row
            for _ in range(3):
                tx = rnd.randrange(8, w - 8)
                ty = min(y for x, y in pts if abs(x - tx) <= 2)
                s.fill(mix(col, (60, 40, 30), 0.6), (tx, ty - 3, 1, 4))
                pygame.draw.circle(s, mix(col, (30, 70, 40), 0.45), (tx, ty - 5), 3)
                s.set_at((tx - 1, ty - 6), mix(col, (160, 220, 140), 0.3))
    # grass floor: three bands, tufts and a few flowers
    g = [lit(c, light) for c in GRASS]
    fh = h - horizon
    s.fill(g[0], (0, horizon, w, fh))
    s.fill(g[1], (0, horizon + fh // 4, w, fh))
    s.fill(g[2], (0, horizon + (fh * 2) // 3, w, fh))
    for y0, a, b in ((horizon + fh // 4, g[0], g[1]), (horizon + (fh * 2) // 3, g[1], g[2])):
        for x in range(0, w, 2):
            s.set_at((x + (y0 % 2), y0), a)
            s.set_at((x, y0 - 1), b)
    s.fill(mix(g[0], (255, 255, 255), 0.18), (0, horizon, w, 1))
    dark, bright = mix(g[2], (20, 50, 40), 0.35), mix(g[0], (220, 250, 170), 0.35)
    for _ in range(w * fh // 160):
        x, y = rnd.randrange(1, w - 2), horizon + 3 + rnd.randrange(max(1, fh - 5))
        col = dark if rnd.random() < 0.6 else bright
        s.set_at((x, y), col)
        s.set_at((x + 1, y - 1), col)
        s.set_at((x - 1, y - 1), col)
    for _ in range(max(3, w // 22)):
        x, y = rnd.randrange(2, w - 3), horizon + 4 + rnd.randrange(max(1, fh - 8))
        petal = lit(rnd.choice(((250, 240, 250), (250, 200, 90), (240, 140, 170), (170, 160, 250))), light)
        s.set_at((x, y), petal)
        s.set_at((x, y + 1), dark)
    return s, mix(g[1], (16, 30, 30), 0.38)
