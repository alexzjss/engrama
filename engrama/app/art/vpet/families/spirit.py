import math

from ..core import BODY, BELLY, ACC, MARK, BONE, DARK
from .common import D, lerp, markings


def espirito(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    d.eyes = ("glow", "gem", "glow")
    d.mouth = "o" if g["mouth"] in ("fang", "cat") else "wavy" if g["mouth"] == "smile" and t % 2 else "smile"
    m = d.m
    if plan == 0:      # sheet: dome head, wavy hem, nub arms, floats
        R = lerp(5.2, 7.0, m) * d.wk ** .5 * d.hk ** .3
        H = R * lerp(2.0, 2.9, m) * d.lk ** .3
        cy = -H + R
        b.E(0, cy, R, R, BODY, 20, "head")
        n = 3 + (t >= 2)
        w0, w1 = R * .98, R * (1.2 + .1 * m)
        pts = [(-w0, cy)]
        for i in range(n * 2 + 1):
            x = -w1 + 2 * w1 * i / (n * 2)
            pts.append((x, 0 if i % 2 == 0 else -lerp(1.4, 2.6, m)))
        pts.append((w0, cy))
        b.P(pts, BODY, 19, "body")
        d.body(0, (cy + 0) / 2, w1 * 2, -cy)
        d.head(0, cy + R * .1, R, R, 1.0)
        d.eye_dx = R * .4
        if t >= 1:
            ay = cy + R * .9
            a = .5 + .8 * max(0, d.soc)
            for sd in (-1, 1):
                b.E(sd * (w0 + .8), ay - a * 1.2, lerp(1.2, 2.0, m), lerp(.8, 1.1, m), BODY, 21, "arm",
                    rot=-sd * a)
            d.hands = [(w0 + 1.5, ay - a * 1.2), (-w0 - 1.5, ay - a * 1.2)]
        _spirit_crest(b, g, d, 0, cy - R * .9, R)
        d.neck = (0, cy + R * .95, R * 1.6)
    elif plan == 1:    # flame: teardrop body crowned with flame tongues, wisp tail
        d.no_slots = frozenset({"back", "neck"})
        bw, bh = lerp(7, 10, m) * d.wk, lerp(6.5, 10, m)
        tl = lerp(2, 7, m)
        by = -tl - bh / 2
        b.E(0, by, bw / 2, bh / 2, BODY, 20, "head")
        b.E(0, by, bw / 2, bh / 2, BODY, 1, "body", line=False)
        s = d.side
        b.C([(0, by + bh * .3), (s * bw * .2, by + bh * .5 + tl * .5), (s * bw * .5, -0.3)],
            [bw * .32, bw * .18, .4], BODY, 9, "wisp", keep=True)
        d.body(0, by, bw, bh)
        d.head(0, by + bh * .12, bh * .5, bw * .5, .9)
        d.eye_dx = bw * .22
        n = 3 + (t >= 2) + (t >= 4)
        Lf = lerp(3, 9, m) * d.fk / d.G * (1 + .3 * d.cri)
        for i in range(n):
            x = (i - (n - 1) / 2) * bw * .8 / max(1, n - 1)
            h = Lf * (1 - .35 * abs(i - (n - 1) / 2) / max(1, n / 2))
            b.C([(x * .9, by - bh * .2), (x * 1.1 + s * .6, by - bh * .45 - h * .5), (x * 1.2 + s * 1.4,
                                                                                     by - bh * .4 - h)],
                [bw * .14, bw * .1, .3], ACC if i % 2 == 0 else BODY, 18, "flame", keep=True)
        b.E(0, by + bh * .28, bw * .25, bh * .18, ACC, 21, "core", on=("head",))
        if t >= 2:
            for sd in (-1, 1):
                b.C([(sd * bw * .45, by + bh * .1), (sd * bw * .75, by - bh * .05), (sd * bw * .85, by - bh * .3)],
                    [1.0, .7, .35], BODY, 19, "arm", keep=True)
            d.hands = [(bw * .85, by - bh * .3), (-bw * .85, by - bh * .3)]
        d.neck = (0, by + bh * .35, bw * .8)
    else:              # hooded wraith: cloak, face in shadow with glowing eyes, floating hands, staff
        d.eyes = ("glow",)
        cw = lerp(7, 11, m) * d.wk
        H = lerp(9, 19, m)
        hr = lerp(4.4, 5.4, m) * d.hk ** .5
        hcy = -H + hr
        pts = [(-hr * .55, hcy + hr * .4), (-cw * .7, -lerp(1, 2.5, m))]
        n = 4
        for i in range(n * 2 + 1):
            x = -cw * .7 + cw * 1.4 * i / (n * 2)
            pts.append((x, 0 if i % 2 == 0 else -lerp(1.0, 2.5, m)))
        pts += [(cw * .7, -lerp(1, 2.5, m)), (hr * .55, hcy + hr * .4)]
        b.P(pts, BODY, 10, "body")
        d.body(0, (hcy + 0) / 2, cw, -hcy)
        b.E(0, hcy, hr * 1.12, hr, BODY, 20, "head")
        b.P([(-hr * .6, hcy - hr * .7), (hr * .6, hcy - hr * .7), (d.side * hr * .9, hcy - hr - 3.5 * d.fk)],
            BODY, 19, "hoodtip", keep=True)
        b.E(0, hcy + hr * .2, hr * .78, hr * .66, DARK, 21, "face", on=("head",), line=False)
        d.head(0, hcy + hr * .15, hr * .8, hr * .8, .8)
        d.eye_dx = hr * .32
        d.mouth = "none"
        b.C([(-cw * .3, hcy + hr * 1.1), (cw * .3, hcy + hr * 1.1)], lerp(.7, 1.1, m), ACC, 22, "clasp")
        if t >= 1:
            for sd in (-1, 1):
                b.E(sd * (cw * .5 + 1.2), hcy + hr * 1.6 + (sd * .8 * max(0, d.soc)), lerp(1.1, 1.6, m),
                    lerp(1.1, 1.5, m), BELLY, 23, "hand")
            d.hands = [(cw * .5 + 1.2, hcy + hr * 1.6), (-cw * .5 - 1.2, hcy + hr * 1.6)]
        if t >= 2:
            sx = -d.side * (cw * .5 + 1.2)
            b.C([(sx, -.3), (sx, hcy - hr * .6)], .55, BONE, 22.5, "staff", keep=True)
            b.E(sx, hcy - hr * .6 - 1.0, 1.1 + .3 * d.G, 1.1 + .3 * d.G, ACC, 23, "orb")
        d.neck = (0, hcy + hr * .9, hr * 1.6)
    if t >= 3 and plan != 2:
        for x, y, r in ((d.bw * .6 + 2, d.hcy, 1.0), (-(d.bw * .6 + 2.5), d.by, .85)):
            b.E(x, y, r * (1 + .25 * (t - 3)), r * (1 + .25 * (t - 3)), ACC, 30, "orb")
    markings(b, g, d)
    return d


def _spirit_crest(b, g, d, x, y, R):
    L = R * .8 * d.fk
    k = g["f1"]
    if k == 0:
        for dx, h in ((-1.6, .7), (1.6, .7), (0, 1.0)):
            b.C([(x + dx * .8, y + 1.5), (x + dx + d.side * .5, y - L * h * .6), (x + dx * 1.2 + d.side, y - L * h)],
                [1.2, .8, .3], ACC, 18, "flame", keep=True)
    elif k == 1:
        b.C([(x + R * .45, y + 1.2), (x + R * .6, y - L * .5), (x + R * .4, y - L * .8)], [1.0, .6, .3], BONE, 18,
            "horn", sym=True, keep=True)
    elif k == 2:
        n = 14
        rr = R * (.55 + .15 * d.fk)
        ring = [(x + math.cos(2 * math.pi * i / n) * rr, y - 1.5 - .3 * L + math.sin(2 * math.pi * i / n) * rr * .3)
                for i in range(n + 1)]
        b.C(ring, .55, ACC, 3, "halo", keep=True)
    else:
        b.P([(x - R * .5, y + 1), (x + R * .5, y + 1), (x + d.side * R * .5, y - L)], MARK, 19, "hood", keep=True)
