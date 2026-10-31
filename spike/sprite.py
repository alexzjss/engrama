"""Procedural pixel sprites: egg and baby. Left half generated, then mirrored."""
import colorsys
import math
import random
import pygame


def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return (int(r * 255), int(g * 255), int(b * 255))


def palette(seed, traits):
    rng = random.Random(seed)
    h = rng.random() * 0.3 + traits["criatividade"] / 100 * 0.45 + traits["sociabilidade"] / 100 * 0.15
    s = 0.45 + 0.35 * traits["curiosidade"] / 100
    return {
        "body": _hsv(h, s, 0.92),
        "shade": _hsv(h, s + 0.15, 0.65),
        "line": _hsv(h, 0.6, 0.22),
        "accent": _hsv(h + 0.45, 0.65, 1.0),
        "eye": (250, 250, 250),
        "pupil": (20, 16, 30),
    }


W, H = 16, 14


def make_baby(seed, traits):
    """Return {'open': Surface, 'blink': Surface} 16x14."""
    rng = random.Random(seed * 7 + 3)
    pal = palette(seed, traits)
    cx, cy = 7.5, 7.6
    rx, ry = 6.6 + rng.random() * 0.8, 5.4 + rng.random() * 0.8
    g = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                g[y][x] = 1
    # ears / horn / antenna on the left half, mirrored
    style = rng.randrange(3)
    for x0 in ([3, 4] if style == 0 else [5] if style == 1 else [2, 3]):
        for y in range(0 if style == 1 else 1, 3):
            if g[y + 1][x0] or y < 2:
                g[y][x0] = 1
                g[y][W - 1 - x0] = 1
    # belly shade + accent spots
    for y in range(H):
        for x in range(W):
            if g[y][x] == 1 and y > cy + 2:
                g[y][x] = 4  # shade
    for _ in range(2 + traits["criatividade"] // 40):
        x, y = rng.randrange(2, 7), rng.randrange(3, 11)
        if g[y][x] == 1:
            g[y][x] = 3
            g[y][W - 1 - x] = 3
    # outline
    out = [row[:] for row in g]
    for y in range(H):
        for x in range(W):
            if g[y][x] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < W and 0 <= ny < H and g[ny][nx] != 0:
                        out[y][x] = 2
                        break
    col = {1: pal["body"], 2: pal["line"], 3: pal["accent"], 4: pal["shade"]}
    frames = {}
    for name in ("open", "blink"):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(H):
            for x in range(W):
                if out[y][x]:
                    s.set_at((x, y), col[out[y][x]])
        for ex in (4, 10):  # eyes 2x2 (mirrored)
            if name == "open":
                for dy in (0, 1):
                    for dx in (0, 1):
                        s.set_at((ex + dx, 6 + dy), pal["eye"])
                s.set_at((ex + (1 if ex == 4 else 0), 7), pal["pupil"])
            else:
                s.set_at((ex, 7), pal["pupil"]); s.set_at((ex + 1, 7), pal["pupil"])
        s.set_at((7, 10), pal["line"]); s.set_at((8, 10), pal["line"])
        frames[name] = s
    return frames


# ---- egg ----
EW, EH = 14, 18


def make_egg(seed, traits):
    pal = palette(seed + 11, traits)
    rng = random.Random(seed)
    s = pygame.Surface((EW, EH), pygame.SRCALPHA)
    for y in range(EH):
        t = (y - 8.5) / 9.0
        hw = 6.8 * math.sqrt(max(0, 1 - t * t)) * (1.0 + 0.12 * t)  # wider at the bottom
        for x in range(EW):
            d = abs(x - 6.5)
            if d <= hw:
                c = pal["body"] if rng.random() > 0.0 else pal["shade"]
                if d > hw - 1:
                    c = pal["line"]
                s.set_at((x, y), c)
    for _ in range(5):  # spots
        x, y = rng.randrange(3, 10), rng.randrange(4, 15)
        if s.get_at((x, y))[3] and s.get_at((x, y)) != pal["line"]:
            s.set_at((x, y), pal["accent"])
    return s


def crack_pixels(seed):
    rng = random.Random(seed + 5)
    pts, x = [], 7
    for y in range(9, 3, -1):
        pts.append((x, y))
        x += rng.choice((-1, 1))
        pts.append((x, y))
    return pts
