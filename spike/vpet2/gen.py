"""Public prototype entry: sprite(seed, stage, ...) -> Sprite; egg(seed) -> RGBA; idle(...) -> RGBA."""
import math
from dataclasses import dataclass

import numpy as np

from .core import BODY, BELLY, ACC, MARK, BONE, DARK, GLASS, GOLD, Builder, render
from .face import eye_size, stamp_face
from .families import FAMILY_FN
from .genes import NEGLECT, genes, persona, temperament

STAGES = ("baby", "child", "adult", "perfect", "final")
SIZES = {"egg": 16, "baby": 24, "child": 32, "adult": 40, "perfect": 44, "final": 48}
FILL = (.74, .84, .92, .96, 1.0)
BRANCH_STAGE = {"brincalhao": 1, "curioso": 1, "sonhador": 1, "arisco": 1, "companheiro": 2, "explorador": 2,
                "artista": 2, "tecnico": 2, "sombrio": 2, "guardiao": 3, "sabio": 3, "virtuoso": 3,
                "aventureiro": 3, "rebelde": 3, "lendario": 4, "mestre": 4, "eco": 4, "sombra": 4}
MAX_ACC = 3


@dataclass
class Sprite:
    body: np.ndarray
    face: dict
    n: int
    family: str
    plan: int


def branch_at(t: int, lineage) -> str:
    for b in reversed(tuple(lineage or ())):
        if BRANCH_STAGE.get(b) == t:
            return b
    return "base"


# --- branch accessories ---------------------------------------------------------------------------------------
# branch -> slot; one accessory per slot, latest branch first, at most MAX_ACC
SLOT = {"brincalhao": "face", "curioso": "top", "sonhador": "top", "arisco": "face", "companheiro": "neck",
        "explorador": "top", "artista": "top", "tecnico": "top", "sombrio": "back", "guardiao": "chest",
        "sabio": "back", "virtuoso": "top", "aventureiro": "top", "rebelde": "wrist", "lendario": "top",
        "mestre": "chest", "eco": "back", "sombra": "back"}


def accessories(b: Builder, d, lineage, t):
    chosen, used = [], set()
    for k in range(t, 0, -1):
        bid = branch_at(k, lineage)
        if bid == "base":
            continue
        slot = SLOT[bid]
        if slot == "wrist" and not d.hands:
            slot = "chest"
        if slot in used:
            continue
        used.add(slot)
        chosen.append((bid, 1.0 if not chosen else .88))
        if len(chosen) >= MAX_ACC:
            break
    for bid, k in chosen:
        _accessory(b, d, bid, k)
    return [c[0] for c in chosen]


def _star(cx, cy, r, n=5, inner=.45):
    return [(cx + math.cos(math.pi * i / n - math.pi / 2) * (r if i % 2 == 0 else r * inner),
             cy + math.sin(math.pi * i / n - math.pi / 2) * (r if i % 2 == 0 else r * inner)) for i in range(2 * n)]


def _accessory(b, d, bid, k):
    hx, hr, hw, hy, hcy, htop = d.head_cx, d.hr * k, d.hw * k, d.hy, d.hcy, d.htop
    nx, ny, nw = d.neck if d.neck else (hx, hcy + d.hr * hy * .95, d.hw * 1.4)
    head = ("head", "mk", "muzzle", "face", "disc", "screen")
    if bid == "brincalhao":
        b.E(hx + hw * .66, d.eye_y + hr * .36, hr * .22, hr * .14, ACC, 23, "blush", on=head, line=False)
        b.E(hx - hw * .66, d.eye_y + hr * .36, hr * .22, hr * .14, ACC, 23, "blush", on=head, line=False)
    elif bid == "curioso":
        b.C([(hx + .3, htop + 1.0), (hx + hr * .25, htop - hr * .55), (hx + hr * .6, htop - hr * .5),
             (hx + hr * .45, htop - hr * .25)], [.75, .6, .5, .4], ACC, 26, "ahoge", keep=True)
    elif bid == "sonhador":
        b.P(_star(hx + hw * .62, htop + .2, hr * .42), GOLD, 27, "star", keep=True)
    elif bid == "arisco":
        cx, cy = hx + hw * .55, d.eye_y + hr * .45
        b.P([(cx - hr * .3, cy - hr * .05), (cx + hr * .2, cy - hr * .25), (cx + hr * .3, cy + hr * .05),
             (cx - hr * .2, cy + hr * .25)], BONE, 23, "plaster", on=head)
    elif bid == "companheiro":
        r = max(1.1, min(1.5 + .3 * d.t, d.hr * .32)) * k
        b.C([(nx - nw * .5, ny - .3), (nx, ny + .8), (nx + nw * .5, ny - .3)], r, ACC, 19.5, "scarf")
        b.C([(nx + nw * .22, ny + .5), (nx + nw * .35, ny + 2.2 + d.t), (nx + nw * .5, ny + 3 + d.t)],
            [r * .9, r * .8, r * .6], ACC, 19.4, "scarf")
    elif bid == "explorador":
        y = htop + hr * .38
        b.C([(hx - hw * 1.02, y + .5), (hx + hw * 1.02, y + .5)], .55 * k + .1, DARK, 26, "strap", on=head,
            line=False)
        for sd in (-1, 1):
            b.E(hx + sd * hw * .38, y, hr * .3, hr * .27, GLASS, 27, "goggle")
    elif bid == "artista":
        b.E(hx - hw * .15, htop + .5, hw * 1.0, hr * .36, ACC, 26, "beret", rot=-.15)
        b.C([(hx - hw * .15, htop), (hx - hw * .05, htop - 1.3 * k)], .55, ACC, 26, "beret", keep=True)
        b.E(hx + hw * .55, htop + hr * .1, hr * .12, hr * .1, GOLD, 27, "paint", on=("beret",))
    elif bid == "tecnico":          # scouter: a lens frame around one eye + antenna on that side
        ex, ey = hx + d.eye_dx, d.eye_y
        n = 12
        r = hr * .42
        ring = [(ex + math.cos(2 * math.pi * i / n) * r * 1.05, ey + math.sin(2 * math.pi * i / n) * r * 1.15)
                for i in range(n + 1)]
        b.C(ring, .55, DARK, 26, "scouter", keep=True)
        b.C([(ex + r * 1.0, ey), (hx + hw * 1.05, ey - hr * .2), (hx + hw * 1.15, ey - hr * 1.2)], [.55, .5, .4],
            DARK, 26, "scouterarm", keep=True)
        b.E(hx + hw * 1.15, ey - hr * 1.25, .8, .8, ACC, 27, "scouterb")
    elif bid == "sombrio":
        cw = max(d.bw * .65, hw * 1.2)
        top = ny - .4
        pts = [(d.bx - cw * .45, top), (d.bx + cw * .45, top)]
        for i in range(7):
            x = d.bx + cw * (.75 - 1.5 * i / 6)
            pts.append((x, -.3 if i % 2 == 0 else -2.5))
        b.P(pts, MARK, 3, "cape")
    elif bid == "guardiao":
        cx, cy = d.bx, d.by - d.bh * .1
        r = max(1.8, d.bw * .16) * k
        b.P([(cx - r, cy - r * .9), (cx + r, cy - r * .9), (cx + r, cy), (cx, cy + r * 1.1), (cx - r, cy)], GOLD, 24,
            "shield")
        b.E(cx, cy - r * .1, r * .4, r * .4, ACC, 25, "shieldgem", on=("shield",))
        if d.hands:
            b.E(nx + nw * .55, ny + .3, nw * .25 + .6, nw * .17 + .5, ACC, 25, "pauldron")
            b.E(nx - nw * .55, ny + .3, nw * .25 + .6, nw * .17 + .5, ACC, 25, "pauldron")
    elif bid == "sabio":
        cw = max(d.bw * .7, hw * 1.3)
        b.P([(nx - nw * .55, ny - .5), (nx + nw * .55, ny - .5), (d.bx + cw * .75, -.4), (d.bx - cw * .75, -.4)],
            ACC, 3, "cape")
        b.C([(nx - nw * .5, ny - .2), (nx + nw * .5, ny - .2)], .9 * k, GOLD, 19.6, "collar")
    elif bid == "virtuoso":
        x, y = hx + hw * .6, htop + .8
        s = 2.6 * k
        b.P([(x, y), (x + s, y - s * .7), (x + s * 1.1, y + s * .6)], ACC, 27, "bow")
        b.P([(x, y), (x - s, y - s * .7), (x - s * .9, y + s * .7)], ACC, 27, "bow")
        b.E(x, y, .9, .9, GOLD, 28, "bowk")
    elif bid == "aventureiro":
        y = htop + hr * .32
        b.C([(hx - hw * 1.05, y + .6), (hx, y - .3), (hx + hw * 1.05, y + .6)], 1.0 * k + .2, ACC, 26, "bandana",
            on=head)
        b.C([(hx + hw * .95, y + .6), (hx + hw * 1.25, y + 2.2), (hx + hw * 1.5, y + 3.0)], [.9, .8, .5], ACC, 25,
            "knot", keep=True)
    elif bid == "rebelde":
        for x, y in d.hands:
            b.E(x, y - 1.1, 1.6 * k + .4, .9, MARK, 24, "cuff")
            b.P([(x - .6, y - 1.6), (x + .6, y - 1.6), (x + (1 if x > 0 else -1) * 1.2, y - 3.2)], BONE, 23, "stud",
                keep=True)
    elif bid == "lendario":
        w, y = hw * .72, htop + 1.2
        pts = [(hx - w, y), (hx - w, y - 2.0), (hx - w * .5, y - .8), (hx, y - 3.2 * k), (hx + w * .5, y - .8),
               (hx + w, y - 2.0), (hx + w, y)]
        b.P(pts, GOLD, 28, "crown", keep=True)
        b.E(hx, y - .9, .7, .7, ACC, 29, "crowngem", on=("crown",))
    elif bid == "mestre":
        y = d.by + d.bh * .22
        b.C([(d.bx - d.bw, y), (d.bx + d.bw, y)], .9 * k, MARK, 24, "belt", on=("body", "belly"), line=False)
        b.R(d.bx - 1.3, y - 1.1, d.bx + 1.3, y + 1.1, r=.3, mat=GOLD, z=25, name="buckle")
        b.P(_star(nx, ny + 1.6, 1.4 * k), GOLD, 25, "medal", keep=True)
    elif bid == "eco":
        n = 18
        R = max(d.bw * .75, hw * 1.3)
        cy = d.by
        ring = [(d.bx + math.cos(2 * math.pi * i / n) * R, cy + math.sin(2 * math.pi * i / n) * R * .3)
                for i in range(n + 1)]
        b.C(ring[n // 2:], .6, GLASS, 1, "ring", keep=True)
        b.C(ring[:n // 2 + 1], .6, GLASS, 29, "ring", keep=True)
    elif bid == "sombra":
        w = max(d.bw * .55, hw)
        for x, h in ((-1, 1.2), (1, 1.2), (0, 1.6)):
            b.P([(d.bx + x * w * .6 - 1.6, d.by), (d.bx + x * w * .6 + 1.6, d.by),
                 (d.bx + x * w * .95, d.btop - h * d.hr)], MARK, 1, "wisp", keep=True)


# --- face -----------------------------------------------------------------------------------------------------
def _face(d, info, t, g, P, red):
    s, ox = info["s"], info["ox"]
    oy = info["oy"]
    styles = d.eyes
    style = styles[int(g["eye_pick"] * len(styles)) % len(styles)]
    if t == 0 and style in ("sclera", "slit"):
        style = "gem"
    if P["paciencia"] > .72 and style == "gem" and t >= 1:
        style = "sleepy"
    bump = 1 if (P["curiosidade"] > .66 and t >= 2) else 0
    w, h = eye_size(t, style, bump)
    cxp = int(round(ox + d.head_cx * s))
    ex = ox + (d.head_cx - d.eye_dx) * s
    ey = oy + d.eye_y * s
    hx0 = ox + (d.head_cx - d.hw) * s
    x0 = int(round(ex - w / 2))
    x0 = min(x0, cxp - w - 1)
    x0 = max(x0, int(math.ceil(hx0)) + 1)
    y0 = int(round(ey - h / 2))
    mouth = d.mouth
    if mouth not in ("none", "grille"):
        if P["sociabilidade"] > .65:
            mouth = "smile"
        elif P["independencia"] > .65 and g["family"] in ("draco", "fera"):
            mouth = "fang"
    mw = 6 if t >= 3 and mouth in ("smile", "wide", "grille", "fang") else 4
    mx = d.mouth_x if d.mouth_x is not None else d.head_cx
    my = oy + (d.mouth_y if getattr(d, "mouth_y", None) is not None else d.hcy + d.hr * .5) * s
    my0 = int(round(my))
    if d.mouth_x is None:
        my0 = max(my0, y0 + h)
    pal = g["pal"]
    f = dict(ex0=x0, ey0=y0, w=w, h=h, axis=2 * cxp - 1, style=style, red=red,
             brow=P["independencia"] > .66 and t >= 1,
             iris=tuple(int(c) for c in pal[ACC][1]), iris2=tuple(int(c) for c in pal[ACC][2]),
             glow=tuple(int(c) for c in pal[ACC][0]) if style != "visor" else tuple(int(c) for c in pal[GLASS][0]),
             mouth=mouth, mw=mw, mx0=int(round(ox + mx * s)) - mw // 2, my0=my0)
    return f


def sprite(seed: int, stage: str, lineage=(), traits=None, hue_rgb=None, family=None, plan=None) -> Sprite:
    t = STAGES.index(stage)
    N = SIZES[stage]
    g = genes(seed, hue_rgb)
    if family:
        g["family"] = family
    if plan is not None:
        g["plan"] = plan
    lin = tuple(lineage or ())
    P = persona(seed, lin, traits) if t >= 1 else temperament(seed)
    b = Builder()
    d = FAMILY_FN[g["family"]](b, g, P, t)
    d.mouth_y = getattr(d, "mouth_y", None)
    nb = len(b.parts)
    if t >= 1:
        accessories(b, d, lin, t)
    if d.facing and g["side"] == 1:
        b.flip()
        d.head_cx = -d.head_cx
        if d.mouth_x is not None:
            d.mouth_x = -d.mouth_x
    body, info = render(b, N, FILL[t], pal=g["pal"], n_base=nb)
    face = _face(d, info, t, g, P, branch_at(t, lin) in NEGLECT)
    return Sprite(body, face, N, g["family"], g["plan"])


def idle(seed, stage, **kw):
    sp = sprite(seed, stage, **kw)
    return stamp_face(sp.body.copy(), sp.face)


# --- egg: family colour + a small family motif ------------------------------------------------------------------
def egg(seed: int, hue_rgb=None, dx: float = 0.0) -> np.ndarray:
    g = genes(seed, hue_rgb)
    fam = g["family"]
    b = Builder()
    b.E(dx, -6.0, 4.6, 6.0, BODY, 10, "body")
    b.E(dx, -4.2, 4.95, 4.2, BODY, 10, "body")
    if fam == "draco":
        pts = [(dx - 6, -5.0)] + [(dx - 4.5 + i * 1.5, -6.6 if i % 2 else -4.6) for i in range(7)] + [(dx + 6, -5.0),
                                                                                                      (dx + 6, -3.6),
                                                                                                      (dx - 6, -3.6)]
        b.P(pts, ACC, 12, "mk", on=("body",))
    elif fam == "fera":
        for x, y, r in ((-2.2, -8, 1.2), (1.8, -6, 1.0), (-1.5, -3.2, .9), (2.4, -2.6, .7)):
            b.E(dx + x, y, r, r, MARK, 12, "mk", on=("body",), line=False)
    elif fam == "ave":
        for x, y in ((-2, -9), (1.5, -8), (-.5, -6.2), (2.5, -5.2), (-2.6, -4.2), (.8, -3)):
            b.E(dx + x, y, .55, .55, ACC, 12, "mk", on=("body",), line=False)
    elif fam == "inseto":
        for y in (-7.2, -4.6):
            b.C([(dx - 6, y), (dx + 6, y)], .7, MARK, 12, "mk", on=("body",), line=False)
    elif fam == "planta":
        b.C([(dx, -11.6), (dx + .3, -13.4)], .45, MARK, 12, "stem", keep=True)
        b.E(dx + 1.6, -13.4, 1.7, .8, MARK, 13, "leaf", rot=-.4)
    elif fam == "espirito":
        b.P([(dx - 1.6, -3.4), (dx + 1.6, -3.4), (dx + 1.2, -6), (dx + .5, -5.2), (dx, -8.2), (dx - .6, -5.4),
             (dx - 1.3, -6.2)], ACC, 12, "mk", on=("body",))
    elif fam == "aquatico":
        pts = [(dx - 6 + i * 1.5, -5.4 + (.8 if i % 2 else -.8)) for i in range(9)]
        b.C(pts, .6, ACC, 12, "mk", on=("body",), line=False)
    else:
        b.C([(dx - 6, -5.6), (dx + 6, -5.6)], .55, DARK, 12, "mk", on=("body",), line=False)
        for x in (-2.4, 0, 2.4):
            b.E(dx + x, -4.0, .45, .45, BONE, 13, "rivet", on=("body",), line=False)
        b.C([(dx, -11.8), (dx, -13.2)], .35, DARK, 9, "ant", keep=True)
        b.E(dx, -13.5, .7, .7, ACC, 9, "antb")
    rgba, _ = render(b, 16, .9, pal=g["pal"], n_base=2)
    return rgba
