"""Procedural pixel sprites: eggs, babies and children drawn into numpy index grids from a genome.

Cell indices: 0 clear, 1 outline, 2 main, 3 shade, 4 accent, 5 eye white, 6 pupil/line, 7 mouth, 8 tear,
9/10/11 branch accessory colours. Everything but the tail (and a few accessories) is left/right mirrored.
adult/perfect/final have their own taller proportions; every branch in vocab.BRANCHES adds a palette shift,
optional part overrides and a procedural accessory. All drawing is cached (bounded LRU), never per frame.
"""
import colorsys
import random
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import pygame

from engrama.vocab import BRANCHES


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


ANIMS = ("idle", "walk", "eat", "sleep", "happy", "sad", "sick", "evolve", "old", "dead")
SIZES = {"egg": 16, "baby": 16, "child": 24, "adult": 28, "perfect": 32, "final": 32}

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
    # bright: blend towards white; gray: blend towards grey; fade: alpha multiplier; hunch: head lowered; lie: on its side
    "evolve": [{"eyes": "closed", "mouth": "none", "bright": b} for b in (0.2, 0.45, 0.7, 0.92)],
    "old": [{"hunch": 1, "gray": 0.22}, {"hunch": 1, "gray": 0.22, "eyes": "closed"}],
    "dead": [{"lie": True, "eyes": "x", "mouth": "none", "gray": 0.3, "fade": 0.85},
             {"lie": True, "eyes": "x", "mouth": "none", "gray": 0.4, "fade": 0.5}],
}

_CACHE_MAX = 400
_cache: "OrderedDict[tuple, list[pygame.Surface]]" = OrderedDict()


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


def _to_surface(grid: _Grid, palette, tint: bool = False, extra=None, bright: float = 0.0,
                gray: float = 0.0, fade: float = 1.0) -> pygame.Surface:
    """extra: {9: rgb, 10: rgb, 11: rgb|rgba} branch accessory colours; bright/gray/fade are animation effects."""
    lut = np.zeros((15, 4), dtype=np.uint8)
    cols = {1: palette[0], 2: palette[1], 3: palette[2], 4: palette[3],
            5: (250, 250, 250), 6: palette[0], 7: palette[0], 8: (120, 190, 255)}
    for i, c in (extra or {}).items():
        cols[i] = c
    for i, c in cols.items():
        alpha = int(c[3]) if len(c) > 3 else 255
        c = _rgb(c)
        if tint and i in (2, 3, 4):
            c = tuple(int(v * 0.55 + g * 0.45) for v, g in zip(c, (130, 190, 100)))
        if gray:
            c = tuple(int(v * (1 - gray) + 140 * gray) for v in c)
        if bright:
            c = tuple(int(v + (255 - v) * bright) for v in c)
        lut[i] = (*c, int(alpha * fade))
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
# per stage: (eye width, left eye x, eye row, mouth row, mirrored centre column)
EYE_GEOM = {"baby": (2, 4, 8, 11, 7), "child": (3, 6, 8, 13, 11), "adult": (3, 8, 8, 13, 13),
            "perfect": (4, 9, 10, 16, 15), "final": (4, 9, 11, 17, 15)}
# non-baby proportions: grid n, head scale hs, head/torso centre rows, torso scale (x, y), leg gap and width,
# foot row (exclusive), arm start offset and length, extra ear height
GEO = {
    "child": dict(n=24, hs=1.0, hcy=10.3, tcy=17.0, ts=(1.0, 1.0), gap=1, lw=3, foot=23, arm_top=-2, arm_len=3, ear_extra=0),
    "adult": dict(n=28, hs=1.0, hcy=10.5, tcy=20.0, ts=(1.15, 1.2), gap=1, lw=3, foot=27, arm_top=-2, arm_len=5, ear_extra=0),
    "perfect": dict(n=32, hs=1.05, hcy=12.0, tcy=23.0, ts=(1.2, 1.3), gap=2, lw=4, foot=31, arm_top=-3, arm_len=7, ear_extra=1),
    "final": dict(n=32, hs=1.1, hcy=13.0, tcy=23.5, ts=(1.05, 1.45), gap=2, lw=4, foot=31, arm_top=-3, arm_len=7, ear_extra=2),
}


def _eye_geom(stage: str):
    return EYE_GEOM[stage]


def _draw_eye(g: _Grid, stage: str, mode: str, style: int, tear: int | None, oy: int = 0) -> None:
    w, x0, ey, _, _ = _eye_geom(stage)
    ey += oy
    big = stage != "baby"
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


def _draw_mouth(g: _Grid, stage: str, mode: str, oy: int = 0) -> None:
    _, _, _, my, c = _eye_geom(stage)
    my += oy
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
        if stage != "baby":
            g.setm(c, my + 1, 7)
    else:  # line
        g.setm(c, my, 7)


def _pattern(g: _Grid, genome, stage: str, pattern: int) -> None:
    rng = random.Random(f"pat:{genome.seed}")
    ey = _eye_geom(stage)[2]
    ys, xs = np.nonzero(g.a == 2)
    if pattern == 1:  # belly patch
        by, cx = np.nonzero(g.part == 2)
        if len(by):
            cyb, rxb, ryb = by.mean() + (0.5 if stage == "baby" else 0.8), (2.6 if stage == "baby" else 3.0), 2.2
            rxb *= g.n / 24 if stage != "baby" else 1.0
            ryb *= g.n / 24 if stage != "baby" else 1.0
            if stage != "baby":
                cyb = by.max() - 2.0 * g.n / 24
            for y in range(g.n):
                for x in range(g.n):
                    if g.part[y, x] == 2 and g.a[y, x] == 2 and ((x - (g.n - 1) / 2) / rxb) ** 2 + ((y - cyb) / ryb) ** 2 <= 1:
                        g.a[y, x] = 4
    elif pattern == 2:  # spots
        cells = [(x, y) for x, y in zip(xs, ys) if x <= g.n // 2 - 1 and not (ey - 1 <= y <= ey + 5)]
        rng.shuffle(cells)
        for x, y in cells[: 3 if stage == "baby" else (5 if g.n == 24 else 8)]:
            g.setm(int(x), int(y), 4)
    elif pattern == 3:  # stripes
        top = int(ys.min()) if len(ys) else 0
        for y in range(top + 2, ey - 1, 2):
            for x in range(g.n):
                if g.a[y, x] == 2 and g.part[y, x] in (1, 2):
                    g.a[y, x] = 3


# --- branches ---------------------------------------------------------------------------------------------
# pal: (hue shift, saturation x, value x); cols: accessory colours 9/10/11; optional eyes/ears/pattern overrides.
# Neglect branches are darker and desaturated, artista/virtuoso saturated, lendario brighter, eco pale.
BRANCH_SPEC = {
    "brincalhao": dict(pal=(0.02, 1.15, 1.05), cols=((220, 60, 70), (150, 30, 50), (250, 225, 90)), eyes=1),
    "curioso": dict(pal=(-0.04, 1.05, 1.0), cols=((90, 200, 90), (40, 120, 60), (250, 230, 90)), eyes=1),
    "sonhador": dict(pal=(0.08, 0.85, 1.1), cols=((170, 140, 255), (90, 70, 170), (255, 245, 170)), eyes=2),
    "arisco": dict(pal=(0.0, 0.5, 0.62), cols=((200, 60, 60), (55, 45, 70), (210, 210, 60)), eyes=3, ears=0),
    "companheiro": dict(pal=(0.02, 1.0, 1.05), cols=((230, 70, 80), (250, 160, 170), (250, 220, 120)), eyes=1),
    "explorador": dict(pal=(-0.05, 0.9, 0.95), cols=((190, 130, 70), (215, 175, 100), (240, 200, 80)), ears=0),
    "artista": dict(pal=(0.06, 1.4, 1.05), cols=((235, 50, 90), (150, 90, 50), (60, 200, 240)), ears=0, pattern=2),
    "tecnico": dict(pal=(0.10, 0.9, 0.95), cols=((60, 200, 230), (80, 90, 110), (255, 230, 80)), pattern=3),
    "sombrio": dict(pal=(0.0, 0.45, 0.55), cols=((120, 40, 140), (60, 45, 80), (220, 60, 70)), eyes=3, ears=0),
    "guardiao": dict(pal=(-0.02, 1.05, 1.05), cols=((220, 60, 60), (150, 160, 190), (250, 210, 70)), ears=0),
    "sabio": dict(pal=(0.12, 0.8, 0.95), cols=((120, 90, 220), (50, 50, 140), (250, 230, 120)), ears=0, eyes=2),
    "virtuoso": dict(pal=(0.05, 1.35, 1.08), cols=((240, 60, 130), (70, 60, 100), (250, 230, 90)), ears=0),
    "aventureiro": dict(pal=(-0.06, 1.1, 1.0), cols=((210, 70, 50), (130, 85, 50), (240, 200, 80)), eyes=1),
    "rebelde": dict(pal=(0.0, 0.5, 0.6), cols=((230, 40, 120), (60, 60, 70), (210, 210, 220)), eyes=3, ears=0),
    "lendario": dict(pal=(0.0, 1.1, 1.2), cols=((230, 70, 80), (250, 240, 200), (255, 215, 70)), ears=0),
    "mestre": dict(pal=(0.03, 0.9, 1.0), cols=((200, 40, 40), (120, 80, 50), (120, 220, 250)), ears=0),
    "eco": dict(pal=(0.45, 0.5, 1.1), cols=((140, 230, 250), (200, 240, 255), (150, 230, 255, 120)), eyes=2),
    "sombra": dict(pal=(0.0, 0.35, 0.45), cols=((90, 40, 120), (35, 25, 50), (200, 80, 255)), eyes=3, ears=0),
}


def _resolve_branch(look, stage: str) -> str:
    br = getattr(look, "branch", "base")
    return br if br in BRANCHES.get(stage, ()) and br in BRANCH_SPEC else "base"


def _branch_palette(palette, branch: str):
    if branch == "base":
        return palette
    dh, ds, dv = BRANCH_SPEC[branch]["pal"]
    out = []
    for c in palette:
        h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in _rgb(c)))
        r, gg, b = colorsys.hsv_to_rgb((h + dh) % 1.0, min(1.0, s * ds), min(1.0, v * dv))
        out.append((int(r * 255), int(gg * 255), int(b * 255)))
    return tuple(out)


def _branch_extra(branch: str, lineage=()):
    """Colour overrides: 9/10/11 accessory, 12..14 primary colours of the (up to three) ancestor branches."""
    if branch == "base":
        return None
    extra = dict(zip((9, 10, 11), BRANCH_SPEC[branch]["cols"]))
    anc = [b for b in lineage if b in BRANCH_SPEC and b != branch][-3:]
    for i, b in enumerate(anc):
        extra[12 + i] = BRANCH_SPEC[b]["cols"][0]
    return extra


def _R(g: _Grid, y: int, k0: int, k1: int, c: int, only_body: bool = False) -> None:
    """Mirrored run of columns k0..k1 counted outward from the centre pair (k=0)."""
    cxl = g.n // 2 - 1
    for k in range(max(0, k0), k1 + 1):
        for x in (cxl - k, g.n - 1 - (cxl - k)):
            if 0 <= x < g.n and 0 <= y < g.n and (not only_body or g.a[y, x] != 0):
                g.a[y, x] = c


def _P(g: _Grid, x: int, y: int, c: int, empty_only: bool = False) -> None:
    if 0 <= x < g.n and 0 <= y < g.n and (not empty_only or g.a[y, x] == 0):
        g.a[y, x] = c


def _T(g: _Grid, k: int, fallback: int) -> int:
    t = g.top(g.n // 2 - 1 - k)
    return fallback if t is None else t


def _geo(g: _Grid, stage: str, arm_l: int) -> dict:
    hy, hx = np.nonzero(g.part == 1)
    ty, tx = np.nonzero(g.part == 2)
    cxl = g.n // 2 - 1
    hy0, hy1, hx0, hx1 = int(hy.min()), int(hy.max()), int(hx.min()), int(hx.max())
    if len(ty):
        ty0, ty1, tx0, tx1 = int(ty.min()), int(ty.max()), int(tx.min()), int(tx.max())
    else:
        ty0, ty1, tx0, tx1 = hy1 + 1, hy1 + 4, hx0 + 2, hx1 - 2
    w, x0, ey, my, _ = EYE_GEOM[stage]
    return dict(cxl=cxl, hx0=hx0, hx1=hx1, hy0=hy0, hy1=hy1, tx0=tx0, tx1=tx1, ty0=ty0, ty1=ty1,
                kh=cxl - hx0, kt=max(0, cxl - tx0), ey=ey, my=my, al=arm_l, ar=g.n - 1 - arm_l)


def _a_brincalhao(g, G):
    y = G["hy0"]
    _R(g, y - 1, 1, 3, 9)
    _R(g, y - 2, 2, 3, 9)
    _R(g, y - 1, 0, 0, 10)


def _a_curioso(g, G):
    y = G["hy0"]
    for i in (1, 2, 3):
        _R(g, y - i, 0, 0, 10)
    _R(g, y - 3, 1, 2, 9)
    _R(g, y - 4, 2, 3, 9)


def _a_arisco(g, G):
    for k, h in ((0, 2), (2, 3), (4, 2)):
        yt = _T(g, k, G["hy0"])
        for i in range(1, h + 1):
            _R(g, yt - i, k, k, 10)


def _a_companheiro(g, G):
    y = G["hy1"] + 1
    _R(g, y, 0, G["kt"] + 1, 9)
    _R(g, y + 1, 0, G["kt"] + 1, 9)
    for i in range(2, 5):
        _P(g, G["tx1"] - 1, y + i, 9)
        _P(g, G["tx1"], y + i, 9)


def _a_explorador(g, G):
    y, kh = G["hy0"] + 1, G["kh"]
    _R(g, y, 0, kh + 2, 10)
    _R(g, y - 1, 0, kh - 1, 9)
    _R(g, y - 2, 0, kh - 2, 10)
    _R(g, y - 3, 0, kh - 4, 10)


def _a_artista(g, G):
    y, kh = G["hy0"] + 1, G["kh"]
    _R(g, y, 0, kh + 1, 9)
    _R(g, y - 1, 0, kh, 9)
    _R(g, y - 2, 0, max(0, kh - 2), 9)
    _R(g, y - 3, 0, 0, 10)
    bx = G["ar"] + 1
    for yy in range(G["ty0"], G["ty0"] + 6):
        _P(g, bx, yy, 10)
    _P(g, bx, G["ty0"] - 1, 11)
    _P(g, bx, G["ty0"] - 2, 11)


def _a_tecnico(g, G):
    y, kh, ey = G["hy0"], G["kh"], G["ey"]
    for i in (1, 2, 3):
        _R(g, y - i, 0, 0, 10)
    _R(g, y - 4, 0, 0, 11)
    for yy in range(ey - 1, ey + 3):
        _R(g, yy, kh + 1, kh + 2, 10)


def _a_sombrio(g, G):
    k0 = max(1, G["kh"] - 3)
    yb = _T(g, k0, G["hy0"])
    pts = [(0, -1), (0, -2), (1, -3), (1, -4), (2, -5)]
    for j, (dk, dy) in enumerate(pts):
        _R(g, yb + dy, k0 + dk, k0 + dk, 11 if j == len(pts) - 1 else 10)


def _a_guardiao(g, G):
    y, kh = G["hy0"], G["kh"]
    _R(g, y, 0, kh, 10)
    _R(g, y + 1, 0, kh, 10)
    _R(g, y - 1, 0, 0, 9)
    _R(g, y - 2, 0, 1, 9)
    _R(g, y - 3, 0, 1, 9)
    _R(g, y - 4, 0, 0, 9)
    xl, t0 = G["al"], G["ty0"] + 1
    for xx in range(xl - 4, xl + 1):
        for yy in range(t0, t0 + 7):
            edge = xx in (xl - 4, xl) or yy in (t0, t0 + 6)
            _P(g, xx, yy, 11 if edge else 10)
    _P(g, xl - 2, t0 + 3, 9)


def _a_sabio(g, G):
    y, kh = G["hy0"] + 1, G["kh"]
    _R(g, y, 0, kh + 2, 10)
    for i in range(5):
        _R(g, y - 1 - i, 0, max(0, kh - 1 - 2 * i), 10)
    _R(g, y - 3, 0, 0, 11)
    for i, km in enumerate((2, 2, 1, 0)):
        _R(g, G["my"] + 1 + i, 0, km, 5)


def _a_virtuoso(g, G):
    kh, ey = G["kh"], G["ey"]
    for yy in range(ey - 1, ey + 3):
        _R(g, yy, kh + 1, kh + 2, 9)
    _R(g, G["hy0"] - 1, 0, kh + 1, 9)
    for yy in range(G["hy0"], ey - 1):
        _R(g, yy, kh + 1, kh + 1, 9)


def _a_aventureiro(g, G):
    t0, kt = G["ty0"], G["kt"]
    for yy in range(t0, G["ty1"] + 3):
        w = 1 + (yy - t0) // 3
        _R(g, yy, kt + 1, kt + 1 + w, 9)
    for i in range(5):
        _P(g, G["hx1"] - 2 + i, G["hy0"] - i, 11)
        _P(g, G["hx1"] - 3 + i, G["hy0"] - i, 9)


def _a_rebelde(g, G):
    for k, h in ((0, 5), (1, 4), (2, 2)):
        yt = _T(g, k, G["hy0"])
        for i in range(1, h + 1):
            _R(g, yt - i, k, k, 9)
    _R(g, G["ty0"] + 1, G["kt"], G["kt"], 11)
    _R(g, G["ty0"] + 3, G["kt"], G["kt"], 11)


def _a_lendario(g, G):
    base, kh = G["hy0"] + 1, G["kh"]
    top = min(kh - 1, 5)
    _R(g, base, 0, top, 11)
    for k in range(0, top + 1, 2):
        _R(g, base - 1, k, k, 11)
    _R(g, base - 2, 0, 0, 11)
    _R(g, base, 0, 0, 9)


def _a_mestre(g, G):
    kh, hy0 = G["kh"], G["hy0"]
    yb = hy0 + 3
    _R(g, yb, 0, kh, 9, only_body=True)
    _P(g, G["hx1"] + 1, yb, 9)
    _P(g, G["hx1"] + 2, yb + 1, 9)
    _P(g, G["hx1"] + 2, yb + 2, 9)
    _R(g, hy0 - 1, 0, 1, 10)
    _R(g, hy0 - 2, 0, 0, 10)
    _R(g, G["ty0"] + 4, 0, G["kt"], 9, only_body=True)
    bx = G["ar"] + 1
    for yy in range(G["ty0"] - 6, g.n - 2):
        _P(g, bx, yy, 10)
    _P(g, bx, G["ty0"] - 8, 11)
    _P(g, bx, G["ty0"] - 7, 11)
    _P(g, bx + 1, G["ty0"] - 7, 11)


def _a_sombra(g, G):
    y, kh = G["hy0"], G["kh"]
    for i in range(3):
        _R(g, y + i, 0, kh, 10, only_body=True)
    _R(g, y - 1, 0, max(0, kh - 3), 10)
    _R(g, y - 2, 0, max(0, kh - 6), 10)
    _R(g, y - 3, 0, 0, 10)
    for yy in range(y + 3, y + 9):
        ext = g.row_extent(yy)
        if ext:
            _P(g, ext[0], yy, 10)
            _P(g, ext[1], yy, 10)


ACCESSORIES = {
    "brincalhao": _a_brincalhao, "curioso": _a_curioso, "arisco": _a_arisco,
    "companheiro": _a_companheiro, "explorador": _a_explorador, "artista": _a_artista,
    "tecnico": _a_tecnico, "sombrio": _a_sombrio,
    "guardiao": _a_guardiao, "sabio": _a_sabio, "virtuoso": _a_virtuoso,
    "aventureiro": _a_aventureiro, "rebelde": _a_rebelde,
    "lendario": _a_lendario, "mestre": _a_mestre, "sombra": _a_sombra,
}


# floating decorations drawn after the outline, only into empty cells
def _plus(g, x, y, c):
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        _P(g, x + dx, y + dy, c, True)


def _p_sonhador(g, G):
    _plus(g, g.n - 5, 4, 11)
    _P(g, 4, 7, 11, True)


def _p_virtuoso(g, G):
    n = g.n
    for yy in range(2, 6):
        _P(g, n - 6, yy, 11, True)
    _P(g, n - 5, 2, 11, True)
    for xx in (n - 8, n - 7):
        for yy in (5, 6):
            _P(g, xx, yy, 11, True)


def _p_lendario(g, G):
    yy = G["hy0"] - 5
    _R(g, yy, 0, 3, 11)
    _R(g, yy + 1, 4, 4, 11)
    _R(g, yy + 2, 0, 3, 11)


def _p_eco(g, G):
    m = g.a != 0
    n = g.n
    echo = np.zeros_like(m)
    echo[:, 3:] |= m[:, :-3]
    echo[:, :-3] |= m[:, 3:]
    g.a[echo & ~m] = 11


def _p_sombra(g, G):
    n = g.n
    for x, y in ((3, 6), (n - 4, 9), (4, n // 2 + 2), (n - 5, n // 2 + 1), (n // 2 - 1, 1)):
        _P(g, x, y, 11, True)
        _P(g, n - 1 - x if x != n // 2 - 1 else x + 1, y, 11, True)


POST = {"sonhador": _p_sonhador, "virtuoso": _p_virtuoso, "lendario": _p_lendario,
        "eco": _p_eco, "sombra": _p_sombra}


def _draw_creature(genome, stage: str, p: dict, branch: str = "base", lineage=()) -> _Grid:
    spec = BRANCH_SPEC.get(branch, {})
    dy = p.get("dy", 0)
    tall = p.get("tall", 0.0)
    hunch = p.get("hunch", 0)
    lift = p.get("lift")
    body = genome.body % 6
    ears = spec.get("ears", genome.ears)
    pattern = spec.get("pattern", genome.pattern)
    style = spec.get("eyes", genome.eyes % 4)
    G = None
    if stage == "baby":
        n = 16
        g = _Grid(n)
        cxl, c = n // 2 - 1, (n - 1) / 2
        rx, ry, ex, pear = BABY_BODY[body]
        cy = 8.8 + dy - tall + hunch
        g.ellipse(c, cy, rx, ry + tall, ex, pear, 2)
        for x, side in ((cxl - 2, "l"), (n - 1 - (cxl - 2), "r")):  # tiny feet
            b = g.bottom(x)
            if b is not None and lift != side:
                g.set(x, b + 1, 3, 3)
        ay_row = int(cy + 2)
        ear_extra = 0
    else:
        geo = GEO[stage]
        n = geo["n"]
        g = _Grid(n)
        cxl, c = n // 2 - 1, (n - 1) / 2
        hrx, hry, hex_ = CHILD_HEAD[body]
        hrx, hry = hrx * geo["hs"], hry * geo["hs"]
        trx, try_ = CHILD_TORSO[body]
        trx, try_ = trx * geo["ts"][0], try_ * geo["ts"][1]
        hcy = geo["hcy"] + dy - tall + 2 * hunch
        tcy = geo["tcy"]
        leg_top = int(tcy + try_) - 1
        for side in ("l", "r"):  # legs, then torso over them
            for i in range(geo["lw"]):
                xl = cxl - geo["gap"] - i
                x = xl if side == "l" else n - 1 - xl
                for y in range(leg_top, geo["foot"] - (1 if lift == side else 0)):
                    g.set(x, y, 3, 3)
        arm_dy = {"up": -2}.get(p.get("arms"), 0)
        arm_l = int(c - trx - 2.5)
        for side in ("l", "r"):
            swing = 1 if lift == side else 0
            for dx in (0, 1):
                x = arm_l + dx if side == "l" else n - 1 - (arm_l + dx)
                a0 = int(tcy) + geo["arm_top"] + arm_dy + swing
                for y in range(a0, a0 + geo["arm_len"]):
                    g.set(x, y, 3, 3)
        g.ellipse(c, tcy, trx, try_, 2.0, 0.0, 2)
        g.ellipse(c, hcy, hrx, hry + tall, hex_, 0.0, 1)
        ay_row = int(tcy + 1)
        ear_extra = geo["ear_extra"]
        if branch != "base":
            G = _geo(g, stage, arm_l)
    # ears / horns
    for k, h, col in EARS["baby" if stage == "baby" else "child"].get(ears, []):
        for x in (cxl - k, n - 1 - (cxl - k)):
            t = g.top(x)
            if t is not None:
                for y in range(t - h - ear_extra, t):
                    g.set(x, y, col, 3)
    # tail on the right edge
    tail = TAILS["baby" if stage == "baby" else "child"].get(genome.tail)
    if tail:
        ext = g.row_extent(ay_row)
        if ext:
            for ox, oy, col in tail:
                g.set(ext[1] + ox, ay_row + oy, col, 3)
    _pattern(g, genome, stage, pattern)
    if G is not None and branch in ACCESSORIES:
        ACCESSORIES[branch](g, G)
    g.shade_bottoms()
    g.outline()
    # face
    eoy = (1 if stage == "baby" else 2) * hunch
    _draw_eye(g, stage, p.get("eyes", "open"), style, p.get("tear"), eoy)
    _draw_mouth(g, stage, p.get("mouth", "line"), eoy)
    if G is not None:
        if branch in POST:
            POST[branch](g, G)
        for i, _b in enumerate([b for b in lineage if b in BRANCH_SPEC and b != branch][-3:]):
            _P(g, 1 + 2 * i, 1, 12 + i, True)
    if p.get("z"):
        zx = n - 5
        for i in range(3):
            g.set(zx + i, 1, 4, 0)
        g.set(zx + 1, 2, 4, 0)
        g.set(zx, 3, 4, 0)
        g.set(zx + 1, 3, 4, 0)
        g.set(zx + 2, 3, 4, 0)
    if p.get("lie"):  # lying on its side, resting on the ground row
        a = np.rot90(g.a).copy()
        rows = np.nonzero(a.any(axis=1))[0]
        if len(rows):
            a = np.roll(a, n - 1 - int(rows[-1]), axis=0)
        g.a = a
    return g


def _key(genome, stage: str, anim: str, branch: str = "base", lineage=()) -> tuple:
    return (genome.seed, genome.body, genome.eyes, genome.ears, genome.tail, genome.pattern,
            tuple(map(tuple, genome.palette)), stage, anim, branch, tuple(lineage))


def frames(look, stage: str, anim: str) -> list[pygame.Surface]:
    """2-4 transparent frames for (look, stage, anim). Cached (bounded LRU); callers must not mutate the surfaces.

    An unknown or stage-mismatched look.branch draws as "base"."""
    if anim not in ANIMS:
        raise ValueError(f"unknown anim {anim!r}")
    if stage not in SIZES:
        raise ValueError(f"unknown stage {stage!r}")
    branch = _resolve_branch(look, stage)
    lineage = tuple(b for b in (getattr(look, "lineage", ()) or ()) if isinstance(b, str)) if branch != "base" else ()
    key = _key(look, stage, anim, branch, lineage)
    hit = _cache.get(key)
    if hit is not None:
        _cache.move_to_end(key)
        return hit
    if stage == "egg":
        if anim in ("evolve", "dead"):
            out = [_to_surface(_egg_grid(look, 0), look.palette, bright=p.get("bright", 0.0),
                               gray=p.get("gray", 0.0), fade=p.get("fade", 1.0)) for p in ANIM_FRAMES[anim]]
        else:
            wobble = [0, 1, 0, -1] if anim == "idle" else [0, 1]
            out = [_to_surface(_egg_grid(look, dx), look.palette) for dx in wobble]
    else:
        pal = _branch_palette(look.palette, branch)
        extra = _branch_extra(branch, lineage)
        out = [_to_surface(_draw_creature(look, stage, p, branch, lineage), pal, p.get("tint", False), extra,
                           p.get("bright", 0.0), p.get("gray", 0.0), p.get("fade", 1.0))
               for p in ANIM_FRAMES[anim]]
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
    import colorsys
    r = random.Random(seed)
    h = r.random()

    def hsv(hh, sat, v):
        return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hh % 1.0, sat, v))
    pal = (hsv(h, 0.6, 0.22), hsv(h, 0.5, 0.92), hsv(h, 0.65, 0.68), hsv(h + 0.45, 0.6, 1.0))
    return Look(seed=seed, body=r.randrange(6), eyes=r.randrange(4), ears=r.randrange(5),
                tail=r.randrange(4), pattern=r.randrange(4), palette=pal, voice_pitch=r.uniform(180, 520))


def contact_sheet(path: str = "data/contact_sheet.png", seeds: int = 12, scale: int = 6) -> None:
    import os
    cell = 32 * scale + 8
    sheet = pygame.Surface((cell * 3, cell * seeds), pygame.SRCALPHA)
    sheet.fill((46, 44, 62))
    for row in range(seeds):
        g = _demo_look(row + 1)
        for col, stage in enumerate(("egg", "baby", "child")):
            f = frames(g, stage, "idle")[0]
            big = pygame.transform.scale(f, (f.get_width() * scale, f.get_height() * scale))
            sheet.blit(big, (col * cell + (cell - big.get_width()) // 2, row * cell + (cell - big.get_height()) // 2))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pygame.image.save(sheet, path)


if __name__ == "__main__":
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    contact_sheet()
    print("wrote data/contact_sheet.png")
