import math

from ..core import BODY, BELLY, ACC, MARK
from .common import D, lerp, markings


def feather_fan(b, sx, sy, ws, a0, a1, n, z=3, name="wing", sym=False, flip=1, tipmat=ACC, len0=1.6, len1=1.1,
                width=.22):
    """Fan of overlapping elongated feathers from (sx, sy), angles a0..a1 degrees (0 = outward, 90 = up)."""
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / max(1, n - 1))
        L = ws * (len0 + (len1 - len0) * i / max(1, n - 1))
        dx, dy = math.cos(a) * flip, -math.sin(a)
        b.E(sx + dx * L * .5, sy + dy * L * .5, L * .5, ws * width, tipmat if i == 0 else BODY, z + n - i, name,
            sym=sym, rot=math.atan2(dy, dx), role="wing", pivot=(sx, sy))


def _crest(b, g, d, x, y, L, back):
    """Bird crests are feathers: tapered blades swept back (3/4) or fanned (front); accent-tipped, no stalks."""
    k = g["f1"]
    if k == 0:       # three swept blades, the middle one longest
        for i, (dx, h) in enumerate(((-1.0, .75), (0, 1.0), (1.0, .7))):
            a = (i - 1) * .45
            tx = x + dx * .4 + (back * L * .9 if back else math.sin(a) * L)
            ty = y - (L * h * .55 if back else math.cos(a) * L * h)
            b.P([(x + dx * .5 - .9, y + 1.0), (x + dx * .5 + .9, y + 1.2), (tx, ty)], MARK if i == 1 else BODY, 18,
                "crest", keep=True)
    elif k == 1:     # long single plume blade, swept back
        bb = back if back else 1
        b.P([(x - 1.0, y + 1.2), (x + 1.2, y + 1.4), (x + bb * L * 1.3, y - L * .55), (x + bb * L * .5, y - L * .5)],
            MARK, 18, "crest", keep=True)
    elif k == 2:
        n = 3 + (d.t >= 3) * 2
        for i in range(n):
            a = (i - (n - 1) / 2) * .38 + back * .5
            b.P([(x - 1 + a * 2, y + 1.6), (x + 1 + a * 2, y + 1.6), (x + math.sin(a) * L * 1.2,
                                                                  y + 1.5 - math.cos(a) * L * 1.15)],
                ACC if i % 2 == 0 else BODY, 18, "crest", keep=True)
    else:
        for dx in (-1.6, 0, 1.6):
            b.E(x + dx, y + .4 - (0 if dx else .6), .9 + .5 * d.fk, 1.2 + .8 * d.fk, ACC, 18, "crest")


def ave(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    d.eyes = ("beady", "gem", "sclera")
    d.mouth = "none"
    m = d.m
    if plan == 0:      # perching bird, 3/4: horizontal tilted body, long tail, thin legs
        L, bh = lerp(6.5, 13, m) * d.wk ** .5, lerp(5.2, 7.4, m) * d.wk
        ll = lerp(.8, 4.4, m) * d.lk
        by = -ll - bh * .42
        d.body(0, by, L, bh)
        b.E(0, by, L / 2, bh / 2, BODY, 10, "body", rot=.18)
        if g["belly"]:
            b.E(-L * .12, by + bh * .22, L * .3, bh * .26, BELLY, 11, "belly", on=("body",))
        hr = lerp(4.6, 3.6, m) * d.hk / lerp(1.55, 1, m)
        hx, hy = -L * .42, by - bh * .42 - hr * .45
        b.E(hx, hy, hr, hr * .95, BODY, 20, "head")
        d.head(hx + hr * .1, hy, hr, hr, .95)
        d.eye_dx = hr * .4
        d.facing = True
        bl = hr * (.7 + .25 * m) * (1 + .4 * d.ind)
        b.P([(hx - hr * .75, hy - hr * .12), (hx - hr * .55, hy + hr * .55), (hx - hr * .7 - bl, hy + hr * .3)],
            ACC, 24, "beak", keep=True)
        d.mouth_x, d.mouth_y = hx - hr * .9, hy + hr * .3
        _crest(b, g, d, hx + hr * .2, hy - hr * .8, hr * .75 * d.fk + .8, 1)
        tl = 2.5 + 6 * m
        for i, a in enumerate((.55, .3, .05)):
            b.C([(L * .35, by - bh * .05), (L * .4 + tl * math.cos(a), by - tl * math.sin(a) * .6)],
                [1.2, .35], ACC if i == 1 else BODY, 3 + i, "tailf", keep=True, role="tail",
                pivot=(L * .35, by - bh * .05))
        if t >= 1:
            for x, z, mt in ((L * .12, 6, MARK), (-L * .08, 7, ACC)):
                lp = (x, by + bh * .3)
                b.C([(x, by + bh * .3), (x - .3, -.4)], .5 + .2 * m, mt if mt != MARK else ACC, z, "leg", keep=True,
                    role="leg", pivot=lp)
                b.C([(x - .3, -.35), (x - 1.6, -.35)], .45, ACC, z, "toe", keep=True, role="leg", pivot=lp)
        if t >= 1:
            ws = L * (0, .5, .55, .62, .7)[t] * (1 + .2 * d.soc)
            wy = by - bh * (.2 + .05 * max(0, d.soc))
            b.C([(-L * .22, wy), (L * .08, by + bh * .02), (L * .2 + ws * .55, by + bh * .05)],
                [bh * .38, bh * .32, .6], BODY, 12, "wing", keep=True, role="wing", pivot=(-L * .22, wy))
            b.E(L * .12 + ws * .35, by + bh * .05, ws * .32, bh * .16, ACC, 13, "wingtip", on=("wing",),
                role="wing", pivot=(-L * .22, wy))
            for k in range(1 + (t >= 3) + (t >= 4)):          # primaries fan out past the tail
                y = by + bh * (.02 + .1 * k)
                b.P([(L * .2 + ws * .3, y - .8), (L * .2 + ws * .3, y + .8), (L * .25 + ws * (.75 + .12 * k), y + .3)],
                    ACC if k == 0 else BODY, 12.5, "primary", keep=True, role="wing", pivot=(-L * .22, wy))
            if t >= 3:   # far wing peeks above the back
                b.E(L * .02, by - bh * .5, ws * .38, bh * .22, MARK, 2, "farwing", rot=-.35,
                    role="wing", pivot=(-L * .22, wy))
        d.neck = (hx + hr * .2, hy + hr * .85, hr * .8)
    elif plan == 1:    # round owl-like: big face disc, ear tufts, short legs
        bw, bh = lerp(8, 12.5, m) * d.wk, lerp(7.5, 12, m)
        ll = lerp(.5, 1.6, m)
        by = -ll - bh / 2
        b.E(0, by, bw / 2, bh / 2, BODY, 10, "body")
        d.body(0, by, bw, bh)
        if g["belly"]:
            b.E(0, by + bh * .18, bw * .3, bh * .3, BELLY, 11, "belly", on=("body",))
            if t >= 2:
                for k in range(3):
                    y = by + bh * (.05 + k * .13)
                    for x in (-1, 1):
                        b.P([(x * 1.4 - .7, y), (x * 1.4, y + .9), (x * 1.4 + .7, y)], MARK, 12, "chev",
                            on=("belly",), line=False)
        hr = 5.6 * d.hk
        hcy = by - bh * .42
        b.E(0, hcy, hr * 1.12, hr * .9, BODY, 20, "head")
        d.head(0, hcy, hr, hr * 1.12, .9)
        b.E(-hr * .45, hcy + .2, hr * .5, hr * .55, BELLY, 21, "disc", sym=True, on=("head",))
        bl = hr * .45
        b.P([(-hr * .2, hcy + hr * .2), (hr * .2, hcy + hr * .2), (0, hcy + hr * .2 + bl)], ACC, 24, "beak",
            keep=True)
        d.mouth_y = hcy + hr * .3
        L = (1.5 + 3 * d.fk) * (1 + .3 * d.cur)
        b.P([(hr * .55, hcy - hr * .55), (hr * 1.0, hcy - hr * .4), (hr * .95 + L * .3, hcy - hr * .7 - L)], BODY,
            18, "tuft", sym=True, keep=True)
        if t >= 1:
            sp = 1 if t < 3 else 1.25
            b.C([(bw * .42, by - bh * .3), (bw * .5 * sp, by + bh * .05), (bw * .42 * sp, by + bh * .42)],
                [bw * .14, bw * .15, .5], BODY, 14, "wing", sym=True, keep=True, role="wing",
                pivot=(bw * .42, by - bh * .3))
            b.E(bw * .46 * sp, by + bh * .22, bw * .08, bh * .14, ACC, 15, "wingtip", sym=True, on=("wing",),
                role="wing", pivot=(bw * .42, by - bh * .3))
            for x in (-.6, 0, .6):
                b.E(bw * .2 + x, -.4, .45, .55, ACC, 9, "talon", sym=True, line=False, role="leg",
                    pivot=(bw * .2, by + bh * .4))
        d.neck = (0, hcy + hr * .8, hr * 1.4)
    else:              # in flight: wings spread wide, tail fan below, legs tucked
        d.no_slots = frozenset({"back"})
        bw, bh = lerp(5, 7, m) * d.wk ** .5, lerp(6, 9.5, m)
        by = -bh / 2 - lerp(1.0, 4.5, m)
        b.E(0, by, bw / 2, bh / 2, BODY, 10, "body")
        d.body(0, by, bw, bh)
        if g["belly"]:
            b.E(0, by + bh * .15, bw * .3, bh * .3, BELLY, 11, "belly", on=("body",))
        hr = 4.4 * d.hk
        hcy = by - bh * .45 - hr * .45
        b.E(0, hcy, hr, hr * .92, BODY, 20, "head")
        d.head(0, hcy, hr, hr, .92)
        bw_ = hr * .36
        bl = hr * (.5 + .16 * m)
        by0 = hcy + hr * .35
        b.P([(-bw_, by0), (bw_, by0), (0, by0 + bl)], ACC, 24, "beak", keep=True)
        d.mouth_y = by0
        _crest(b, g, d, 0, hcy - hr * .85, hr * .7 * d.fk + .6, 0)
        ws = lerp(4, 10.5, m) * (1 + .2 * d.soc)
        if t == 0:
            b.E(bw * .55, by - .5, 1.6, 1.0, BODY, 9, "wing", sym=True, rot=-.4, role="wing",
                pivot=(bw * .38, by - bh * .3))
        else:
            feather_fan(b, bw * .38, by - bh * .3, ws, -15, 50, 4 + (t >= 3), z=3, name="wing", sym=True,
                        len0=1.25, len1=.95, width=.19)
        tl = 2 + 4 * m
        for i, a in enumerate((-.45, 0, .45)):
            b.C([(0, by + bh * .3), (math.sin(a) * tl * .8, by + bh * .4 + tl)], [1.0, .4], ACC if i == 1 else BODY,
                2, "tailf", keep=True, role="tail", pivot=(0, by + bh * .3))
        d.neck = (0, hcy + hr * .8, hr * 1.2)
    markings(b, g, d)
    return d
