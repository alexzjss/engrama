import math

from ..core import BODY, BELLY, ACC, DARK, GLASS
from .common import D, lerp, markings, upright


def aquatico(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    m = d.m
    if plan == 0:      # jellyfish: dome bell, scalloped skirt, trailing tentacles
        d.no_slots = frozenset({"back", "neck", "wrist"})
        d.eyes = ("glow", "gem")
        d.mouth = "o" if g["mouth"] == "fang" else "smile"
        bw = lerp(9, 14, m) * d.wk
        bellh = lerp(7, 10, m)
        tl = lerp(2.5, 11, m) * d.lk
        cy = -tl - bellh * .35
        b.E(0, cy, bw / 2, bellh / 2, BODY, 20, "head")
        n = 4 + (t >= 2)
        pts = [(-bw * .5, cy)]
        for i in range(n * 2 + 1):
            x = -bw * .48 + bw * .96 * i / (n * 2)
            pts.append((x, cy + bellh * (.42 if i % 2 == 0 else .3)))
        pts.append((bw * .5, cy))
        b.P(pts, BODY, 19, "body")
        b.P([(x, y + .2) for x, y in pts[1:-1]] + [(bw * .45, cy + bellh * .2), (-bw * .45, cy + bellh * .2)],
            BELLY, 21, "rim", on=("body",), flat=True)
        d.body(0, cy, bw, bellh)
        d.head(0, cy + bellh * .05, bellh * .5, bw * .5, .9)
        d.eye_dx = bw * .2
        nt = 3 + min(4, t)
        for i in range(nt):
            x = (i - (nt - 1) / 2) * bw * .8 / max(1, nt - 1)
            L = tl * (1 - .25 * ((i * 7 + g["f2"]) % 3) / 2)
            w = 1 if i % 2 else -1
            pts2 = [(x, cy + bellh * .35)]
            for k in range(1, 4):
                pts2.append((x + w * (.8 if k % 2 else -.8) * (1 + m), cy + bellh * .35 + L * k / 3))
            b.C(pts2, [lerp(.7, 1.0, m), .7, .5, .35], ACC if i % 2 else BODY, 8, "tentacle", keep=True)
        if t >= 2:
            b.C([(0, cy + bellh * .3), (d.side * 1.5, cy + bellh * .3 + tl * .45), (0, cy + bellh * .3 + tl * .7)],
                [1.6, 1.3, .7], BELLY, 9, "oral", keep=True)
        if g["f1"] == 2:
            b.C([(0, cy - bellh * .45), (d.side * 1.5, cy - bellh * .5 - 3 * d.fk)], [.6, .4], DARK, 17, "lure",
                keep=True)
            b.E(d.side * 1.5, cy - bellh * .5 - 3 * d.fk - .8, 1.1, 1.1, GLASS, 18, "lureb")
        d.neck = None
    elif plan == 1:    # fish, 3/4: horizontal body, forked tail, dorsal and side fins, floats
        d.no_slots = frozenset({"back", "neck", "wrist"})
        d.eyes = ("beady", "gem")
        d.mouth = "o" if g["mouth"] == "fang" else "wide"
        L, bh = lerp(8, 15, m) * d.wk ** .5, lerp(6.5, 9.5, m) * d.wk
        by = -bh / 2 - lerp(1.0, 2.0, m)
        b.E(0, by, L / 2, bh / 2, BODY, 10, "body")
        b.E(-L * .2, by, L * .3, bh * .47, BODY, 11, "head", line=False)
        d.body(0, by, L, bh)
        d.head(-L * .22, by - bh * .1, bh * .45, L * .28, 1.0)
        d.eye_dx = L * .12
        d.facing = True
        d.mouth_x, d.mouth_y = -L * .4, by + bh * .18
        if g["belly"]:
            b.E(-L * .05, by + bh * .3, L * .38, bh * .2, BELLY, 12, "belly", on=("body", "head"))
        tf = lerp(2.5, 6, m) * (1 + .3 * d.cri)
        tx = L * .42
        b.P([(tx, by - bh * .1), (tx + tf * 1.1, by - tf * 1.0), (tx + tf * .6, by), (tx + tf * 1.1, by + tf * 1.0),
             (tx, by + bh * .1)], ACC, 6, "fluke", keep=True)
        df = lerp(1.5, 4.5, m) * d.fk / d.G
        b.P([(-L * .15, by - bh * .42), (L * .05 + d.ind, by - bh * .5 - df), (L * .3, by - bh * .38)], ACC, 8,
            "dorsal", keep=True)
        b.P([(-L * .02, by + bh * .1), (L * .2, by + bh * .35 + df * .3), (L * .2, by + bh * .05)], ACC, 13,
            "pectoral", keep=True)
        b.P([(L * .05, by + bh * .45), (L * .2, by + bh * .5 + df * .5), (L * .3, by + bh * .38)], ACC, 7,
            "anal", keep=True)
        if g["f1"] == 2 and t >= 1:
            b.C([(-L * .3, by - bh * .4), (-L * .45, by - bh * .5 - 3 * d.fk), (-L * .6, by - bh * .4 - 3 * d.fk)],
                [.5, .4, .35], DARK, 17, "lure", keep=True)
            b.E(-L * .62, by - bh * .3 - 3 * d.fk, 1.0, 1.1, GLASS, 18, "lureb")
        elif g["f1"] == 1 and t >= 1:
            b.C([(-L * .4, by + bh * .2), (-L * .5, by + bh * .4 + 1.5 * d.fk)], [.4, .3], ACC, 24, "barbel",
                keep=True)
        d.neck = (-L * .1, by + bh * .1, bh * .6)
    else:              # axolotl-like amphibian, upright, frilly gills or fin ears
        d.eyes = ("gem", "beady")
        d.mouth = "wide" if g["mouth"] != "fang" else "smile"
        upright(b, g, d, body_k=1.05, leg_k=.65, head_w=1.2, neck=.55, pear=.25)
        hx, hcy = d.hw, d.hcy
        if g["f1"] in (0, 3):
            L = 1.6 + 2.6 * d.fk
            pts = [(hx - 1.2, hcy - 1.6), (hx + L * .9, hcy - L * 1.0), (hx + L * .55, hcy - L * .38),
                   (hx + L * 1.1, hcy - L * .15), (hx + L * .5, hcy + L * .12), (hx + L * .75, hcy + L * .5),
                   (hx - 1.0, hcy + 1.3)]
            b.P(pts, ACC, 18, "fin", sym=True, keep=True)
        else:
            for a in (-.5, 0, .5):
                L = 1.6 + 2.6 * d.fk
                b.C([(hx - .8, hcy - .5 + a * 2.4), (hx + L * math.cos(a), hcy - .5 + a * 2.4 - L * .3 + a * L * .6)],
                    [.95, .5], ACC, 18, "gill", sym=True, keep=True)
        tl = 2.5 + 4 * m
        s = d.side
        p0 = (s * d.bw * .3, d.by + d.bh * .35)
        p1 = (s * (d.bw * .5 + tl * .5), d.by + d.bh * .45)
        p2 = (s * (d.bw * .5 + tl * .95), d.by + d.bh * .05)
        b.C([p0, p1, p2], [d.lr * 1.2, d.lr * .85, d.lr * .5], BODY, 5, "tail")
        F = 1.6 + 2.4 * m
        b.P([(p2[0], p2[1] + .4), (p2[0] + s * F * 1.1, p2[1] - F * 1.3), (p2[0] + s * F * .2, p2[1] - .2),
             (p2[0] - s * F * .3, p2[1] - F * 1.4)], ACC, 6, "fluke", keep=True)
        b.E(0, d.hcy + d.hr * d.hy * .42, d.hr * .62, d.hr * d.hy * .3, BELLY, 21, "muzzle", on=("head",))
        d.mouth_y = d.hcy + d.hr * d.hy * .42
    markings(b, g, d)
    return d
