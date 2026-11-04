import math

from ..core import BODY, BELLY, ACC, MARK, BONE, GOLD
from .common import D, lerp, markings, upright


def _leaves(b, g, d, x, top, L, leaf=MARK):
    b.C([(x, top + .6), (x, top - L * .4)], .5, leaf, 17, "stem", keep=True)
    b.E(x + L * .45, top - L * .45, L * .5, L * .24, leaf, 18, "leaf", rot=-.5)
    b.E(x - L * .45, top - L * .45, L * .5, L * .24, leaf, 18, "leaf", rot=.5)


def planta(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    d.eyes = ("gem", "sleepy", "beady")
    d.mouth = "smile" if g["mouth"] != "fang" else "o"
    m = d.m
    if plan == 0:      # bulb walker: pear bulb, leafy top, root feet, leaf hands
        upright(b, g, d, body_k=1.05, limb_k=.9, leg_k=.45, arm_mat=MARK, pear=.35, neck=.68, body_hk=1.1)
        hr = d.hr
        top = d.htop + .8
        if g["f1"] in (0, 2) or t < 2:
            _leaves(b, g, d, 0, top, 2 + 3.6 * d.fk)
        if g["f1"] == 1:
            L = 2.5 + 3 * d.fk
            r = 1.3 + 1.1 * d.fk
            b.C([(0, top + .6), (d.side * .8, top - L * .5), (d.side * .4, top - L)], .55, MARK, 17, "stem",
                keep=True)
            b.E(d.side * .4, top - L - r * .5, r, r * 1.15, ACC, 19, "bud")
        if g["f1"] in (2, 3) and t >= 2:
            for a in (-.9, -.3, .3, .9):
                L = 3 + 2.8 * d.fk
                b.E(math.sin(a) * L * .7, top - math.cos(a) * L * .55, L * .22, L * .5,
                    MARK if g["f1"] == 2 else ACC, 18, "leaf", rot=a)
        for hx, hy in d.hands[:1]:
            b.E(hx + .6, hy + .3, d.ar * 1.6, d.ar * .9, MARK, 16, "leafhand", sym=True, rot=.6)
        if t >= 1:
            for x in (.6, -.6):
                b.P([(d.bw * .3 + x, -1), (d.bw * .3 + x + .8, -1), (d.bw * .3 + x * 2.6, 0)], MARK, 7, "root",
                    sym=True, keep=True)
    elif plan == 1:    # flower: a face in a ring of petals on a stem, leaf arms, root base
        sh = lerp(2.5, 9, m) * d.lk
        sr = lerp(1.3, 1.9, m)
        b.E(0, -.9, lerp(2.6, 5.0, m), lerp(1.0, 1.6, m), MARK, 8, "mound")
        if t >= 1:
            for x in (1.0, 2.6):
                b.P([(x, -1.4), (x + 1.0, -1.2), (x + 2.0 + m, 0)], MARK, 7, "root", sym=True, keep=True)
        b.C([(0, -1.0), (d.side * .6, -sh * .55), (0, -sh)], sr, BODY, 10, "body")
        d.body(0, -sh * .5, sr * 2, sh)
        if t >= 1:
            for k, (y, sd) in enumerate(((.35, 1), (.6, -1))):
                L = lerp(2.5, 5.5, m) * (1 + .3 * d.soc)
                a = .35 + .5 * max(0, d.soc)
                b.E(sd * (L * .5 + .6), -sh * y - L * .2 * a, L * .55, L * .25, MARK, 12, "leafarm", rot=sd * a)
            d.hands = [(L * .9, -sh * .35), (-L * .9, -sh * .6)]
        hr = 4.8 * d.hk
        hcy = -sh - hr * .7
        n = 6 + (t >= 3) * 2 + (g["f1"] == 2) * 2
        R = hr * (1.0 + .18 * d.G)
        for i in range(n):
            a = 2 * math.pi * i / n + (math.pi / n if g["f1"] % 2 else 0)
            pr = hr * (.5 if g["f1"] != 3 else .4) * (1 + .2 * d.G)
            b.E(math.cos(a) * R * .85, hcy + math.sin(a) * R * .85, pr, pr * .62, ACC, 4, "petal", rot=a)
        b.E(0, hcy, hr, hr * .92, BODY, 20, "head")
        if g["belly"]:
            b.E(0, hcy + hr * .2, hr * .7, hr * .6, BELLY, 21, "face", on=("head",))
        d.head(0, hcy, hr, hr, .92)
        d.neck = (0, hcy + hr * .9, hr * .8)
    else:              # cactus column: tall body, bent arms, spines, flower on top
        H = lerp(7, 17, m) * d.lk ** .5
        r = lerp(3.4, 4.6, m) * d.wk
        b.C([(0, -r * .9), (0, -H + r)], [r, r * .92], BODY, 10, "body")
        b.E(0, -H + r * 1.1, r * .92, r * .85, BODY, 20, "head", line=False)
        b.E(0, -.8, r * 1.15, 1.0, MARK, 9, "foot")
        d.body(0, -H * .4, r * 2, H * .6)
        d.head(0, -H + r * 1.15, r * .9, r * .92, .85)
        d.eye_dx = r * .4
        if g["belly"]:
            b.C([(0, -r * 1.2), (0, -H * .55)], r * .5, BELLY, 11, "belly", on=("body",))
        for i, (x, y) in enumerate(((-.55, .4), (.6, .55), (-.5, .7), (.55, .25), (0, .8), (-.2, .15))):
            b.E(x * r, -H * y, .32, .32, BONE, 12, "spine", on=("body", "head"), line=False)
        if t >= 1:
            for sd, y, up in ((d.side, .45, 1.0), (-d.side, .3, .6)):
                ax = sd * (r * .9)
                L = lerp(2.0, 5.0, m) * up
                ar = lerp(1.1, 1.7, m)
                b.C([(ax, -H * y), (sd * (r + L * .7), -H * y), (sd * (r + L * .8), -H * y - L * 1.1 * up)],
                    [ar, ar, ar * .9], BODY, 12, "arm")
            d.hands = [(d.side * (r + 2), -H * .45 - 2)]
        if t >= 2:
            fy = -H - r * .1
            for k in range(5):
                a = -math.pi / 2 + (k - 2) * .55
                b.E(math.cos(a) * 1.3, fy + math.sin(a) * 1.0 + .3, 1.2 + .4 * d.G, .8 + .3 * d.G, ACC, 21, "flower",
                    rot=a)
            b.E(0, fy + .4, .9, .9, GOLD, 22, "pistil")
        d.neck = None
    markings(b, g, d)
    return d
