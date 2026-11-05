from ..core import BODY, BELLY, ACC, MARK, BONE, DARK, GLASS
from .common import D, lerp, markings


def _antennae(b, g, d, x, y, L, sym=True):
    k = g["f1"]
    ak = {"role": "antenna", "pivot": (x, y)}
    if k == 0:
        b.C([(x, y), (x + L * .3, y - L)], .45, DARK, 17, "ant", sym=sym, keep=True, **ak)
        b.E(x + L * .3, y - L, 1.0 + .3 * d.fk, 1.0 + .3 * d.fk, ACC, 18, "antip", sym=sym, **ak)
    elif k == 1:
        b.C([(x, y), (x + L * .2, y - L * .8), (x + L * .6, y - L), (x + L * .7, y - L * .7)], .45, DARK, 17, "ant",
            sym=sym, keep=True, **ak)
    elif k == 2:
        b.C([(x, y), (x + L * .5, y - L)], .45, DARK, 17, "ant", sym=sym, keep=True, **ak)
        b.P([(x + L * .15, y - L * .3), (x + L * .55, y - L * 1.05), (x + L * .7, y - L * .4)], ACC, 16, "antf",
            sym=sym, keep=True, **ak)
    else:
        b.C([(x, y), (x + L * .1, y - L * .9), (x + L * .7, y - L * 1.15)], [.5, .4, .3], DARK, 17, "ant", sym=sym,
            keep=True, **ak)


def inseto(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    d.eyes = ("compound", "beady", "compound")
    d.mouth = "none"
    m = d.m
    if plan == 0:      # beetle: tall split dome of wing cases, pronotum, small head with horn, short legs
        bw, bh = lerp(8.5, 15, m) * d.wk, lerp(6, 9.5, m)
        ll = lerp(.5, 1.6, m)
        by = -ll - bh * .5
        b.E(0, by, bw / 2, bh / 2, MARK, 9, "body")                          # underside / shadow rim
        for sd in (-1, 1):                                                  # the two elytra
            b.E(sd * bw * .24, by - bh * .04, bw * .27, bh * .47, ACC, 11, "elytra", rot=sd * .08, grp="shell")
        b.C([(0, by - bh * .5), (0, by + bh * .4)], .38 + .1 * m, DARK, 12, "seam", on=("elytra",), line=False)
        for x, y in ((.25, -.2), (.3, .12), (.16, .3)):
            if g["mark"] != "none" or t >= 2:
                b.E(x * bw, by + y * bh, bw * .05 + .25, bw * .05 + .25, DARK, 12, "dot", sym=True,
                    on=("elytra",), line=False)
        d.body(0, by, bw, bh)
        hr = lerp(4.6, 3.5, m) * d.hk / lerp(1.55, 1, m)
        py = by + bh * .32
        b.E(0, py, bw * .3, bh * .14, BODY, 19, "pronotum")
        hcy = py + bh * .06
        b.E(0, hcy, hr * 1.05, hr * .8, BODY, 20, "head")
        d.head(0, hcy, hr, hr * 1.05, .8)
        _antennae(b, g, d, hr * .45, hcy - hr * .55, hr * .55 * d.ck + 1.2)
        if t >= 2:
            Lh = hr * .8 * d.fk
            b.C([(0, hcy - hr * .5), (0, hcy - hr * .6 - Lh * .6), (d.side * Lh * .3, hcy - hr * .6 - Lh)],
                [1.1, .8, .35], BONE, 21, "horn", keep=True)
        if t >= 1:
            for k, ax in enumerate((.18, .32, .44)):
                x0 = bw * ax
                b.C([(x0, by + bh * .35), (x0 + .6 + .3 * k, -.3)], .55 + .2 * m, DARK, 8 - k, "leg", sym=True,
                    keep=True, role="leg", pivot=(x0, by + bh * .35))
        if t >= 2:
            my = hcy + hr * .7
            b.C([(hr * .35, my - .5), (hr * .45, my + .8), (hr * .15, my + 1.3)], [.7, .55, .3], BONE, 24,
                "mandible", sym=True, keep=True)
        d.neck = (0, py, bw * .5)
        d.no_slots = frozenset({"back"})
    elif plan == 1:    # bee: round fuzzy thorax, big striped abdomen, glassy wings, short legs, stinger
        ab_w, ab_h = lerp(6.5, 11, m) * d.wk, lerp(5.5, 9, m)
        ll = lerp(.6, 2.4, m) * d.lk
        ay = -ll - ab_h * .5
        b.E(0, ay, ab_w / 2, ab_h / 2, ACC, 8, "body")
        for k in (-.22, .05, .32):
            b.C([(-ab_w, ay + ab_h * k), (ab_w, ay + ab_h * k)], .45 + .25 * m, DARK, 9, "stripe", on=("body",),
                line=False)
        b.P([(-.8, ay + ab_h * .45), (.8, ay + ab_h * .45), (0, ay + ab_h * .5 + 1.2 + m)], DARK, 7, "sting",
            keep=True)
        tw, th = ab_w * .42, lerp(3.2, 5.0, m)
        ty = ay - ab_h * .42
        b.E(0, ty, tw, th / 2, BODY, 12, "thorax")
        b.E(0, ty - th * .2, tw * .9, th * .3, BELLY, 13, "fuzz", on=("thorax",))
        d.body(0, ay, ab_w, ab_h)
        hr = lerp(4.6, 3.8, m) * d.hk / lerp(1.55, 1, m)
        hcy = ty - th * .45 - hr * .6
        b.E(0, hcy, hr * 1.05, hr * .9, BODY, 20, "head")
        d.head(0, hcy, hr, hr * 1.05, .9)
        _antennae(b, g, d, hr * .4, hcy - hr * .65, hr * .7 * d.ck + 1.5)
        ws = lerp(2.5, 7.5, m) * (1 + .2 * d.soc)
        if t >= 1:
            wp = (tw * .5, ty - th * .2)
            b.E(tw * .6 + ws * .55, ty - th * .3 - ws * .35, ws * .62, ws * .36, GLASS, 3, "wing", sym=True, rot=-.7,
                flat=True, role="wing", pivot=wp)
            b.E(tw * .5 + ws * .4, ty - th * .1, ws * .4, ws * .24, GLASS, 2, "wing2", sym=True, rot=-.25, flat=True,
                role="wing", pivot=wp)
            for k, x in enumerate((.25, .42)):
                b.C([(ab_w * x, ay + ab_h * .3), (ab_w * x + .5, -.3)], .5 + .15 * m, DARK, 6 - k, "leg", sym=True,
                    keep=True, role="leg", pivot=(ab_w * x, ay + ab_h * .3))
            ex, ey = tw * .9 + .8, ty + th * .15
            b.C([(tw * .8, ty - th * .1), (ex, ey)], lerp(.7, 1.0, m), DARK, 14, "arm", sym=True, keep=True,
                role="arm", pivot=(tw * .8, ty - th * .1))
            d.hands = [(ex, ey), (-ex, ey)]
        d.eyes = ("compound", "gem", "compound")
        d.neck = (0, ty - th * .4, tw * 1.6)
    else:              # butterfly/moth: small segmented body, two pairs of large wings
        bh = lerp(5, 9, m)
        by = -bh / 2 - lerp(1.0, 2.5, m)
        b.C([(0, by - bh * .3), (0, by + bh * .55)], [lerp(1.5, 2.0, m), .8], BODY, 10, "body")
        for k in (.1, .3):
            b.C([(-3, by + bh * k), (3, by + bh * k)], .3, MARK, 11, "band", on=("body",), line=False)
        d.body(0, by, 4, bh)
        hr = 3.2 * d.hk
        hcy = by - bh * .3 - hr * .75
        b.E(0, hcy, hr * 1.05, hr * .9, BODY, 20, "head")
        d.head(0, hcy, hr, hr * 1.05, .9)
        if t >= 1:
            b.E(0, hcy + hr * .6, hr * .9, hr * .45, BELLY, 19, "ruff")
        _antennae(b, g, d, hr * .35, hcy - hr * .6, hr * .9 * d.ck + 2.0)
        ws = lerp(4.5, 12, m) * (1 + .25 * d.cri)
        wm = ACC if g["f4"] % 2 else BODY
        other = BODY if wm == ACC else ACC
        wk = {"role": "wing", "pivot": (1.0, by)}
        b.E(ws * .8, by - ws * .38, ws * .68, ws * .5, wm, 3, "wing", sym=True, rot=-.55, **wk)
        b.E(ws * .62, by + ws * .3, ws * .45, ws * .38, wm, 2, "wing2", sym=True, rot=.5, **wk)
        if t >= 1:
            b.E(ws * 1.1, by - ws * .62, ws * .3, ws * .22, other, 4, "wband", sym=True, rot=-.55, on=("wing",),
                **wk)
            b.E(ws * .78, by - ws * .38, ws * .17, ws * .17, BELLY, 4, "eyespot", sym=True, on=("wing",), **wk)
            b.E(ws * .78, by - ws * .38, ws * .08, ws * .08, DARK, 5, "eyespot2", sym=True, on=("eyespot",),
                line=False, **wk)
            b.E(ws * .72, by + ws * .4, ws * .15, ws * .15, other, 4, "spot2", sym=True, on=("wing2",), **wk)
        d.neck = (0, hcy + hr * .8, hr * 1.4)
        d.no_slots = frozenset({"back"})
    markings(b, g, d)
    return d
