"""Public prototype entry: sprite(seed, stage, ...) -> Sprite; frames(...) -> list of RGBA arrays."""
import math
from dataclasses import dataclass

import numpy as np

from .core import BODY, BELLY, ACC, MARK, BONE, DARK, GLASS, GOLD, Builder, render
from .face import EYE_WH, stamp_face
from .families import FAMILY_FN
from .genes import NEGLECT, genes, persona, temperament

STAGES = ("baby", "child", "adult", "perfect", "final")
SIZES = {"egg": 16, "baby": 24, "child": 32, "adult": 40, "perfect": 44, "final": 48}
FILL = (.74, .84, .92, .96, 1.0)
BRANCH_STAGE = {"brincalhao": 1, "curioso": 1, "sonhador": 1, "arisco": 1, "companheiro": 2, "explorador": 2,
                "artista": 2, "tecnico": 2, "sombrio": 2, "guardiao": 3, "sabio": 3, "virtuoso": 3,
                "aventureiro": 3, "rebelde": 3, "lendario": 4, "mestre": 4, "eco": 4, "sombra": 4}


@dataclass
class Sprite:
    body: np.ndarray
    face: dict
    n: int
    family: str


def branch_at(t: int, lineage) -> str:
    for b in reversed(tuple(lineage or ())):
        if BRANCH_STAGE.get(b) == t:
            return b
    return "base"


# --- branch accessories: drawn over the family body using the skeleton anchors ---------------------------------
def accessory(b: Builder, d, bid: str, g):
    hr, hy, hcy, htop = d.hr, d.hy, d.hcy, d.htop
    nk = d.btop + .6
    if bid == "brincalhao":
        b.E(hr * .66, d.eye_y + hr * .34, hr * .16, hr * .1, ACC, 23, "blush", sym=True, on=("head", "muzzle"),
            line=False)
    elif bid == "curioso":
        b.E(0, htop + hr * .35, hr * .14, hr * .14, ACC, 23, "dot", on=("head", "mk"), line=False)
    elif bid == "sonhador":
        cx, cy, r = hr * .75, htop - .2, 1.6
        b.P([(cx + math.cos(a) * (r if i % 2 == 0 else r * .45), cy + math.sin(a) * (r if i % 2 == 0 else r * .45))
             for i, a in enumerate(math.pi * 2 * k / 10 - math.pi / 2 for k in range(10))], GOLD, 31, "star")
    if bid == "companheiro":
        b.C([(-d.bw * .48, nk), (0, nk + .9), (d.bw * .48, nk)], 1.1 + .1 * d.t, ACC, 19, "scarf")
        b.C([(d.bw * .25, nk + .6), (d.bw * .38, nk + 3.2)], [1.0, .8], ACC, 18.5, "scarf")
    elif bid == "explorador":
        y = htop + hr * .4
        b.C([(-hr * .95, y + .4), (hr * .95, y + .4)], .45, DARK, 26, "strap", on=("head", "mk", "muzzle"),
            line=False)
        b.E(hr * .36, y, hr * .26, hr * .24, GLASS, 27, "goggle", sym=True)
    elif bid == "artista":
        b.E(-hr * .2, htop + .6, hr * .9, hr * .32, ACC, 26, "beret", rot=-.15)
        b.C([(-hr * .2, htop + .2), (-hr * .1, htop - 1.0)], .45, ACC, 26, "beret", keep=True)
    elif bid == "tecnico":
        n = 9
        ring = [(math.cos(math.pi + math.pi * i / (n - 1)) * hr * 1.05, hcy + math.sin(math.pi + math.pi * i / (n - 1))
                 * hr * hy * 1.05) for i in range(n)]
        b.C(ring, .5, DARK, 26, "headset", keep=True)
        b.E(hr * 1.02, hcy, hr * .2, hr * .3, MARK, 27, "cup", sym=True)
        b.C([(-hr * 1.0, hcy + 1), (-hr * .55, hcy + hr * .65)], .35, DARK, 27, "mic", keep=True)
    elif bid == "guardiao":
        b.E(d.bw * .52, d.btop + 1.0, d.bw * .3, d.bh * .2, ACC, 25, "pauldron", sym=True)
        b.P([(0, d.by - d.bh * .3), (1.6, d.by - d.bh * .1), (0, d.by + d.bh * .15), (-1.6, d.by - d.bh * .1)],
            GOLD, 24, "emblem")
    elif bid == "sabio":
        b.P([(-d.bw * .62, d.btop + .3), (d.bw * .62, d.btop + .3), (d.bw * .85, -0.6), (-d.bw * .85, -0.6)],
            ACC, 4, "cape")
        b.P([(0, htop + 1.0), (1.0, htop + 2.0), (0, htop + 3.0), (-1.0, htop + 2.0)], GOLD, 24, "gem")
    elif bid == "virtuoso":
        x, y = hr * .7, htop + .8
        b.P([(x, y), (x + 2.4, y - 1.6), (x + 2.6, y + 1.4)], ACC, 26, "bow")
        b.P([(x, y), (x - 2.4, y - 1.6), (x - 2.0, y + 1.6)], ACC, 26, "bow")
        b.E(x, y, .9, .9, ACC, 27, "bow")
    elif bid == "aventureiro":
        y = htop + hr * .3
        b.C([(-hr * .98, y + .6), (0, y - .2), (hr * .98, y + .6)], 1.0, ACC, 26, "bandana", on=("head", "mk"))
        b.C([(-d.bw * .45, d.btop + 1), (d.bw * .4, d.by + d.bh * .35)], .6, DARK, 24, "strap", on=("body", "belly"),
            line=False)
    elif bid == "rebelde":
        for hx, hy2 in d.hands:
            b.E(hx, hy2 - 1.0, d.ar * 1.25, .8, MARK, 24, "cuff", sym=True)
            b.P([(hx - .5, hy2 - 1.5), (hx + .5, hy2 - 1.5), (hx + 1.2, hy2 - 3.0)], BONE, 23, "stud", sym=True,
                keep=True)
        b.P([(d.bw * .35, d.btop + .5), (d.bw * .55, d.btop + .5), (d.bw * .5, d.btop - 2.2)], BONE, 24, "stud",
            sym=True, keep=True)
    elif bid == "lendario":
        w, y = hr * .7, htop + 1.2
        pts = [(-w, y), (-w, y - 1.6), (-w * .5, y - .6), (0, y - 2.6), (w * .5, y - .6), (w, y - 1.6), (w, y)]
        b.P(pts, GOLD, 28, "crown", keep=True)
        b.P([(0, d.by - d.bh * .3), (1.6, d.by - d.bh * .1), (0, d.by + d.bh * .15), (-1.6, d.by - d.bh * .1)],
            GOLD, 24, "emblem")
    elif bid == "mestre":
        b.P([(-d.bw * .6, d.btop + .3), (d.bw * .6, d.btop + .3), (d.bw * .9, -0.4), (-d.bw * .9, -0.4)],
            ACC, 4, "cape")
        y = d.by + d.bh * .25
        b.C([(-d.bw, y), (d.bw, y)], .8, MARK, 24, "belt", on=("body", "belly"), line=False)
        b.R(-1.1, y - 1.0, 1.1, y + 1.0, r=.3, mat=GOLD, z=25, name="buckle")
    elif bid == "eco":
        n = 16
        R = d.bw * .95
        ring = [(math.cos(2 * math.pi * i / n) * R, d.by + math.sin(2 * math.pi * i / n) * R * .3) for i in range(n + 1)]
        b.C(ring[n // 2:], .5, GLASS, 1, "ring", keep=True)
        b.C(ring[:n // 2 + 1], .5, GLASS, 29, "ring", keep=True)
    elif bid == "sombra":
        for x, h in ((-.9, 1.3), (.9, 1.3), (0, 1.6)):
            b.P([(x * d.bw * .5 - 1.5, d.by), (x * d.bw * .5 + 1.5, d.by), (x * d.bw * .8, d.btop - h * hr)], MARK,
                1, "wisp", keep=True)


def _face(d, info, t, g, P, bid, N):
    to_px = info["to_px"]
    ox = info["ox"]
    w, h = EYE_WH[t]
    if P["curiosidade"] > .66 and t >= 2:
        h += 1
    style = "gem" if t == 0 else g["eye"]
    if t >= 1 and P["independencia"] > .66:
        style = "sharp" if style == "sclera" else style
    if t >= 1 and P["paciencia"] > .72 and style != "sharp":
        style = "calm"
    if style == "sclera" and w < 4:
        style = "gem"
    if P["independencia"] > .72 and t >= 2 and style == "gem":
        style = "sharp"
    ex, ey = to_px(-d.eye_x, d.eye_y)
    hx0, _ = to_px(-d.hr, d.hcy)
    x0 = int(round(ex - w / 2))
    x0 = min(x0, ox - w - 1)                 # at least a 2 px gap between the eyes
    x0 = max(x0, int(math.ceil(hx0)) + 1)    # stay on the head
    y0 = int(round(ey - h / 2))
    mouth = g["mouth"]
    if P["sociabilidade"] > .65:
        mouth = "smile"
    elif P["independencia"] > .65:
        mouth = "fang"
    f = dict(ex0=x0, ey0=y0, w=w, h=h, axis=2 * ox - 1, style=style, red=bid in NEGLECT,
             iris=tuple(int(c) for c in g["pal"][ACC][1]), mouth=mouth, mw=4)
    if d.mouth_y is None:               # beak
        by0, bl = d.beak
        _, my = to_px(0, by0 + bl * .25)
        f["mouth"] = "none"
        f["my0"] = int(round(my)); f["mx0"] = ox - 2
    else:
        _, my = to_px(0, d.mouth_y)
        f["my0"] = max(int(round(my)), y0 + h)
        f["mx0"] = ox - 2
    return f


def sprite(seed: int, stage: str, lineage=(), traits=None, hue_rgb=None, family=None) -> Sprite:
    t = STAGES.index(stage)
    N = SIZES[stage]
    g = genes(seed, hue_rgb)
    if family:
        g["family"] = family
    lin = tuple(lineage or ())
    P = persona(seed, lin, traits) if t >= 1 else temperament(seed)
    bid = branch_at(t, lin)
    b = Builder()
    d = FAMILY_FN[g["family"]](b, g, P, t)
    nb = len(b.parts)
    if bid != "base":
        accessory(b, d, bid, g)
    body, info = render(b, N, FILL[t], pal=g["pal"], n_base=nb)
    face = _face(d, info, t, g, P, bid, N)
    return Sprite(body, face, N, g["family"])


def idle(seed, stage, **kw):
    sp = sprite(seed, stage, **kw)
    a = sp.body.copy()
    return stamp_face(a, sp.face)
