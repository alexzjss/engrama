"""Procedural pixel sprites: eggs, babies and children drawn into numpy index grids from a genome.

Cell indices: 0 clear, 1 outline, 2 main, 3 shade, 4 accent, 5 eye white, 6 pupil/line, 7 mouth, 8 tear.
Everything but the tail is left/right mirrored. adult/perfect/final reuse the child art (real art is M4).
"""
import random

import numpy as np
import pygame

ANIMS = ("idle", "walk", "eat", "sleep", "happy", "sad", "sick")
SIZES = {"egg": 16, "baby": 16, "child": 24, "adult": 24, "perfect": 24, "final": 24}

# --- shape tables -----------------------------------------------------------------------------------------
# baby body: (rx, ry, exponent, pear) -- pear > 0 widens the bottom
BABY_BODY = [(5.2, 4.8, 2.0, 0.0), (5.4, 4.2, 2.0, 0.0), (4.4, 5.0, 2.0, 0.0),
             (4.6, 4.8, 2.0, 0.3), (5.2, 4.6, 3.2, 0.0), (4.0, 4.2, 2.0, 0.0)]
# child: head (rx, ry, exponent) and torso (rx, ry)
CHILD_HEAD = [(7.6, 6.0, 2.0), (8.2, 5.4, 2.0), (6.6, 6.6, 2.0), (7.0, 6.0, 2.0), (7.6, 5.8, 3.2), (6.4, 5.6, 2.0)]
CHILD_TORSO = [(4.4, 3.8), (5.0, 3.4), (4.0, 4.2), (5.2, 3.8), (4.6, 3.8), (3.8, 3.4)]

# ears/horns: (k columns left of centre, height above the head, colour index); mirrored to the right
EARS = {
    "baby": {1: [(3, 1, 2), (4, 1, 2)],
             2: [(2, 1, 2), (3, 2, 2), (4, 3, 2)],
             3: [(2, 3, 2), (3, 3, 2)],
             4: [(0, 3, 4), (1, 1, 4)]},
    "child": {1: [(3, 1, 2), (4, 2, 2), (5, 2, 2)],
              2: [(3, 2, 2), (4, 3, 2), (5, 4, 2), (6, 4, 2)],
              3: [(2, 4, 2), (3, 4, 4), (4, 4, 2)],
              4: [(0, 5, 4), (1, 4, 4), (2, 2, 4)]},
}

# tails (right side only): offsets from the anchor on the body's right edge; (dx, dy, colour)
TAILS = {
    "baby": {1: [(1, 0, 2), (2, 0, 2)],
             2: [(1, 0, 2), (2, 0, 2), (2, -1, 2), (2, -2, 2)],
             3: [(1, 0, 2), (2, 0, 4), (2, -1, 4), (1, -1, 4)]},
    "child": {1: [(1, 0, 2), (2, 0, 2), (3, 0, 2), (1, 1, 2), (2, 1, 2), (3, 1, 2)],
              2: [(1, 0, 2), (2, 0, 2), (3, 0, 2), (3, -1, 2), (4, -1, 2), (4, -2, 2), (4, -3, 2), (4, -4, 2),
                  (1, 1, 2), (2, 1, 2), (3, 1, 2), (5, -4, 2)],
              3: [(1, 0, 2), (2, 0, 2), (2, -1, 4), (3, -1, 4), (4, -1, 4), (2, -2, 4), (3, -2, 4), (4, -2, 4),
                  (3, 0, 4), (4, 0, 4), (3, -3, 4)]},
}

# --- animation frame parameters ---------------------------------------------------------------------------
# dy: vertical hop, tall: squash/stretch, eyes: face mode, mouth, lift: raised foot, arms: arm pose, tint: sick
ANIM_FRAMES = {
    "idle": [{}, {"dy": -1}, {"eyes": "closed"}],
    "walk": [{"lift": "l"}, {"dy": -1}, {"lift": "r"}, {"dy": -1}],
    "eat": [{"mouth": "line"}, {"mouth": "open"}, {"mouth": "chew"}],
    "sleep": [{"eyes": "closed", "mouth": "none"}, {"eyes": "closed", "mouth": "none", "tall": 0.7, "z": True}],
    "happy": [{"eyes": "happy", "mouth": "smile", "arms": "up"},
              {"eyes": "happy", "mouth": "smile", "arms": "up", "dy": -1}],
    "sad": [{"eyes": "sad", "mouth": "frown", "tear": 0}, {"eyes": "sad", "mouth": "frown", "tear": 1}],
    "sick": [{"eyes": "x", "mouth": "wavy", "tint": True}, {"eyes": "x", "mouth": "wavy", "tint": True, "tall": 0.5}],
}

_cache: dict[tuple, list[pygame.Surface]] = {}


class _Grid:
    def __init__(self, n: int):
        self.n = n
        self.a = np.zeros((n, n), dtype=np.uint8)
        self.part = np.zeros((n, n), dtype=np.uint8)  # 1 head, 2 body/torso, 3 other

    def set(self, x: int, y: int, c: int, part: int = 3) -> None:
        if 0 <= x < self.n and 0 <= y < self.n:
            self.a[y, x] = c
            if part:
                self.part[y, x] = part

    def setm(self, x: int, y: int, c: int) -> None:
        self.set(x, y, c, 0)
        self.set(self.n - 1 - x, y, c, 0)

    def ellipse(self, cx, cy, rx, ry, p, pear, part, c=2) -> None:
        for y in range(self.n):
            for x in range(self.n):
                w = rx * (1 + pear * (y - cy) / ry)
                if w > 0 and (abs(x - cx) / w) ** p + (abs(y - cy) / ry) ** p <= 1:
                    self.set(x, y, c, part)

    def top(self, x: int) -> int | None:
        ys = np.nonzero(self.a[:, x])[0]
        return int(ys[0]) if len(ys) else None

    def bottom(self, x: int) -> int | None:
        ys = np.nonzero(self.a[:, x])[0]
        return int(ys[-1]) if len(ys) else None

    def row_extent(self, y: int) -> tuple[int, int] | None:
        xs = np.nonzero(self.a[y])[0]
        return (int(xs[0]), int(xs[-1])) if len(xs) else None

    def shade_bottoms(self) -> None:
        for x in range(self.n):
            b = self.bottom(x)
            if b is not None and self.a[b, x] == 2:
                self.a[b, x] = 3

    def outline(self) -> None:
        m = self.a != 0
        near = np.zeros_like(m)
        near[1:] |= m[:-1]
        near[:-1] |= m[1:]
        near[:, 1:] |= m[:, :-1]
        near[:, :-1] |= m[:, 1:]
        self.a[near & ~m] = 1


def _rgb(c) -> tuple[int, int, int]:
    return int(c[0]), int(c[1]), int(c[2])


def _to_surface(grid: _Grid, palette, tint: bool = False) -> pygame.Surface:
    lut = np.zeros((9, 4), dtype=np.uint8)
    cols = {1: palette[0], 2: palette[1], 3: palette[2], 4: palette[3],
            5: (250, 250, 250), 6: palette[0], 7: palette[0], 8: (120, 190, 255)}
    for i, c in cols.items():
        c = _rgb(c)
        if tint and i in (2, 3, 4):
            c = tuple(int(v * 0.55 + g * 0.45) for v, g in zip(c, (130, 190, 100)))
        lut[i] = (*c, 255)
    rgba = lut[grid.a]  # (h, w, 4)
    surf = pygame.Surface((grid.n, grid.n), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    rgb[:] = rgba[:, :, :3].swapaxes(0, 1)
    del rgb
    alpha = pygame.surfarray.pixels_alpha(surf)
    alpha[:] = rgba[:, :, 3].swapaxes(0, 1)
    del alpha
    return surf


# --- egg --------------------------------------------------------------------------------------------------
CRACKS = [[(7, 3), (8, 4), (7, 5)],
          [(6, 6), (7, 7), (6, 8), (7, 9)],
          [(9, 5), (10, 6), (9, 7), (10, 8), (5, 9), (4, 10), (5, 11)]]


def _egg_grid(genome, dx: int = 0, crack: int = 0) -> _Grid:
    n = 16
    g = _Grid(n)
    cx, cy, ry = 7.5 + dx, 8.2, 6.2
    rx = 5.0 + 0.3 * (genome.body % 3)
    for y in range(n):
        for x in range(n):
            w = rx * (1 - 0.18 * max(0.0, cy - y) / ry)
            if (abs(x - cx) / w) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                g.set(x, y, 2, 2)
    rng = random.Random(f"egg:{genome.seed}")
    for _ in range(3 + genome.pattern % 2):
        x, y = rng.randrange(3, 8), rng.randrange(4, 13)
        for sx in range(x, x + 1 + rng.randrange(2)):
            mx = 15 + 2 * dx - sx  # mirror about the (shifted) centre
            for px in (sx, mx):
                if 0 <= px < n and g.a[y, px] == 2:
                    g.a[y, px] = 4
    g.shade_bottoms()
    g.outline()
    for lv in range(crack):
        for x, y in CRACKS[lv]:
            g.set(x + dx, y, 6, 0)
    if crack >= 3:  # shell chipped open at the top
        for x in (7, 8):
            g.set(x + dx, 2, 5, 0)
    return g


def make_egg_crack(genome, level: int) -> pygame.Surface:
    level = max(0, min(3, int(level)))
    return _to_surface(_egg_grid(genome, 0, level), genome.palette)


# --- creatures --------------------------------------------------------------------------------------------
def _eye_geom(stage: str):
    # w: eye width, left x0, row ey, mouth row my, mirrored centre column
    return (2, 4, 8, 11, 7) if stage == "baby" else (3, 6, 8, 13, 11)


def _draw_eye(g: _Grid, stage: str, mode: str, style: int, tear: int | None) -> None:
    w, x0, ey, _, _ = _eye_geom(stage)
    big = stage == "child"
    if mode == "closed":
        for i in range(w):
            g.setm(x0 + i, ey + 1, 6)
    elif mode == "happy":
        span = 5 if big else 3
        for i in range(span):
            g.setm(x0 + i, ey + 1 - min(i, span - 1 - i), 6)
    elif mode == "x":
        for i in range(w):
            g.setm(x0 + i, ey + i, 6)
            g.setm(x0 + w - 1 - i, ey + i, 6)
    elif mode == "sad":
        for i in range(w):
            g.setm(x0 + i, ey + 1, 5)
            g.setm(x0 + i, ey + 2, 6)
        g.setm(x0 + w - 1, ey, 6)  # drooping lid on the inner side
        if tear is not None:
            g.setm(x0, ey + 3 + tear, 8)
    elif style == 0:  # beady
        for i in range(w):
            for j in range(2):
                g.setm(x0 + i, ey + j, 6)
    elif style == 1:  # big shiny
        h = 4 if big else 3
        pw = 2 if big else 1
        for i in range(w):
            for j in range(h):
                g.setm(x0 + i, ey + j, 6 if i >= w - pw and j >= 1 else 5)
    elif style == 2:  # sleepy half-lids
        g.setm(x0, ey, 6)
        for i in range(w):
            g.setm(x0 + i, ey, 6)
            g.setm(x0 + i, ey + 1, 5 if i < w - 1 else 6)
            if big:
                g.setm(x0 + i, ey + 2, 6)
    else:  # fierce: slanted brow, inner end lower
        for i in range(w):
            g.setm(x0 + i, ey - 1 if i < w - 1 else ey, 6)
            if i < w - 1:
                g.setm(x0 + i, ey, 5)
            for j in range(1, w):
                g.setm(x0 + i, ey + j, 6)


def _draw_mouth(g: _Grid, stage: str, mode: str) -> None:
    _, _, _, my, c = _eye_geom(stage)
    if mode == "none":
        return
    if mode == "smile":
        g.setm(c - 1, my, 7)
        g.setm(c, my + 1, 7)
    elif mode == "frown":
        g.setm(c - 1, my + 1, 7)
        g.setm(c, my, 7)
    elif mode == "wavy":
        g.setm(c - 2, my, 7)
        g.setm(c - 1, my + 1, 7)
        g.setm(c, my, 7)
    elif mode == "open":
        for j in range(2):
            g.setm(c, my + j, 7)
            g.setm(c - 1, my + j, 7)
    elif mode == "chew":
        g.setm(c, my, 7)
        g.setm(c - 1, my, 7)
        if stage == "child":
            g.setm(c, my + 1, 7)
    else:  # line
        g.setm(c, my, 7)


def _pattern(g: _Grid, genome, stage: str) -> None:
    rng = random.Random(f"pat:{genome.seed}")
    ey = _eye_geom(stage)[2]
    ys, xs = np.nonzero(g.a == 2)
    if genome.pattern == 1:  # belly patch
        by, cx = np.nonzero(g.part == 2)
        if len(by):
            cyb, rxb, ryb = by.mean() + (0.5 if stage == "baby" else 0.8), (2.6 if stage == "baby" else 3.0), 2.2
            if stage == "child":
                cyb = by.max() - 2.0
            for y in range(g.n):
                for x in range(g.n):
                    if g.part[y, x] == 2 and g.a[y, x] == 2 and ((x - (g.n - 1) / 2) / rxb) ** 2 + ((y - cyb) / ryb) ** 2 <= 1:
                        g.a[y, x] = 4
    elif genome.pattern == 2:  # spots
        cells = [(x, y) for x, y in zip(xs, ys) if x <= g.n // 2 - 1 and not (ey - 1 <= y <= ey + 5)]
        rng.shuffle(cells)
        for x, y in cells[: 3 if stage == "baby" else 5]:
            g.setm(int(x), int(y), 4)
    elif genome.pattern == 3:  # stripes
        top = int(ys.min()) if len(ys) else 0
        for y in range(top + 2, ey - 1, 2):
            for x in range(g.n):
                if g.a[y, x] == 2 and g.part[y, x] in (1, 2):
                    g.a[y, x] = 3


def _draw_creature(genome, stage: str, p: dict) -> _Grid:
    child = stage != "baby"
    n = 24 if child else 16
    g = _Grid(n)
    dy = p.get("dy", 0)
    tall = p.get("tall", 0.0)
    cxl = n // 2 - 1
    c = (n - 1) / 2
    body = genome.body % 6
    lift = p.get("lift")
    if not child:
        rx, ry, ex, pear = BABY_BODY[body]
        cy = 8.8 + dy - tall
        g.ellipse(c, cy, rx, ry + tall, ex, pear, 2)
        for x, side in ((cxl - 2, "l"), (n - 1 - (cxl - 2), "r")):  # tiny feet
            b = g.bottom(x)
            if b is not None and lift != side:
                g.set(x, b + 1, 3, 3)
        ay_row = int(cy + 2)
    else:
        hrx, hry, hex_ = CHILD_HEAD[body]
        trx, try_ = CHILD_TORSO[body]
        hcy = 10.3 + dy - tall
        tcy = 17.0 + dy * 0.0
        # legs, then torso over them
        leg_top = int(tcy + try_) - 1
        for side, xs in (("l", (8, 9, 10)), ("r", (13, 14, 15))):
            for x in xs:
                for y in range(leg_top, 23 - (1 if lift == side else 0)):
                    g.set(x, y, 3, 3)
        # arms
        arm_dy = {"up": -2}.get(p.get("arms"), 0)
        for side in ("l", "r"):
            swing = 1 if lift == side else 0
            for dx in (0, 1):
                xl = int(c - trx - 2.5) + dx  # left arm column; the right arm mirrors it
                x = xl if side == "l" else n - 1 - xl
                for y in range(int(tcy) - 2 + arm_dy + swing, int(tcy) + 1 + arm_dy + swing):
                    g.set(x, y, 3, 3)
        g.ellipse(c, tcy, trx, try_, 2.0, 0.0, 2)
        g.ellipse(c, hcy, hrx, hry + tall, hex_, 0.0, 1)
        ay_row = int(tcy + 1)
    # ears / horns
    for k, h, col in EARS[stage if stage == "baby" else "child"].get(genome.ears, []):
        for x in (cxl - k, n - 1 - (cxl - k)):
            t = g.top(x)
            if t is not None:
                for y in range(t - h, t):
                    g.set(x, y, col, 3)
    # tail on the right edge
    tail = TAILS[stage if stage == "baby" else "child"].get(genome.tail)
    if tail:
        ext = g.row_extent(ay_row)
        if ext:
            for ox, oy, col in tail:
                g.set(ext[1] + ox, ay_row + oy, col, 3)
    _pattern(g, genome, stage)
    g.shade_bottoms()
    g.outline()
    # face
    style = genome.eyes % 4
    _draw_eye(g, stage, p.get("eyes", "open"), style, p.get("tear"))
    _draw_mouth(g, stage, p.get("mouth", "line"))
    if p.get("z"):
        zx = 12 if not child else 19
        for i in range(3):
            g.set(zx + i, 1, 4, 0)
        g.set(zx + 1, 2, 4, 0)
        g.set(zx, 3, 4, 0)
        g.set(zx + 1, 3, 4, 0)
        g.set(zx + 2, 3, 4, 0)
    return g


def _key(genome, stage: str, anim: str) -> tuple:
    return (genome.seed, genome.body, genome.eyes, genome.ears, genome.tail, genome.pattern,
            tuple(map(tuple, genome.palette)), stage, anim)


def make_frames(genome, stage: str, anim: str) -> list[pygame.Surface]:
    """2-4 transparent frames for (genome, stage, anim). Cached; callers must not mutate the surfaces."""
    if anim not in ANIMS:
        raise ValueError(f"unknown anim {anim!r}")
    if stage not in SIZES:
        raise ValueError(f"unknown stage {stage!r}")
    key = _key(genome, stage, anim)
    if key in _cache:
        return _cache[key]
    if stage == "egg":
        wobble = [0, 1, 0, -1] if anim == "idle" else [0, 1]
        frames = [_to_surface(_egg_grid(genome, dx), genome.palette) for dx in wobble]
    else:
        st = "baby" if stage == "baby" else "child"
        frames = [_to_surface(_draw_creature(genome, st, p), genome.palette, p.get("tint", False))
                  for p in ANIM_FRAMES[anim]]
    _cache[key] = frames
    return frames


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
def _demo_genome(seed: int):
    import colorsys
    from types import SimpleNamespace
    r = random.Random(seed)
    h = r.random()

    def hsv(hh, s, v):
        return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hh % 1.0, s, v))
    pal = (hsv(h, 0.6, 0.22), hsv(h, 0.5, 0.92), hsv(h, 0.65, 0.68), hsv(h + 0.45, 0.6, 1.0))
    return SimpleNamespace(seed=seed, body=r.randrange(6), eyes=r.randrange(4), ears=r.randrange(5),
                           tail=r.randrange(4), pattern=r.randrange(4), palette=pal,
                           voice_pitch=r.uniform(180, 520), branch="demo")


def contact_sheet(path: str = "data/contact_sheet.png", seeds: int = 12, scale: int = 6) -> None:
    import os
    cell = 24 * scale + 8
    sheet = pygame.Surface((cell * 3, cell * seeds), pygame.SRCALPHA)
    sheet.fill((46, 44, 62))
    for row in range(seeds):
        g = _demo_genome(row + 1)
        for col, stage in enumerate(("egg", "baby", "child")):
            f = make_frames(g, stage, "idle")[0]
            big = pygame.transform.scale(f, (f.get_width() * scale, f.get_height() * scale))
            sheet.blit(big, (col * cell + (cell - big.get_width()) // 2, row * cell + (cell - big.get_height()) // 2))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pygame.image.save(sheet, path)


if __name__ == "__main__":
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    contact_sheet()
    print("wrote data/contact_sheet.png")
