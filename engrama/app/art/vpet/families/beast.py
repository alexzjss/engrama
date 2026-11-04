import math

from ..core import BODY, BELLY, ACC, MARK, DARK
from .common import D, lerp, markings, quad, upright


def _ears(b, g, d, x, y, scale, facing):
    ek = scale
    inner = ACC if g["f4"] % 2 else BELLY
    sym = not facing
    k = g["f1"]
    ek_ = {"role": "ear", "pivot": (x, y + .8)}
    if k == 0:
        L = 2.2 + 3.4 * ek
        b.P([(x - 1.8, y + 1.4), (x + 1.6, y + 1.0), (x + .9, y - L)], BODY, 18, "ear", sym=sym, keep=True, **ek_)
        b.P([(x - .7, y + .9), (x + .7, y + .7), (x + .7, y - L * .55)], inner, 19, "earin", sym=sym, on=("ear",),
            **ek_)
    elif k == 1:
        r = 1.4 + 1.6 * ek
        b.E(x + .4, y - r * .3, r, r, BODY, 18, "ear", sym=sym, **ek_)
        b.E(x + .4, y - r * .25, r * .55, r * .55, inner, 19, "earin", sym=sym, on=("ear",), **ek_)
    elif k == 2:
        L = 3 + 5 * ek
        b.C([(x - .3, y + .5), (x + .5, y - L * .6), (x + .9, y - L)], [1.5, 1.4, .9], BODY, 18, "ear", sym=sym,
            **ek_)
        b.C([(x - .2, y), (x + .5, y - L * .6), (x + .8, y - L * .9)], [.6, .6, .35], inner, 19, "earin", sym=sym,
            on=("ear",), **ek_)
    else:
        L = 2.5 + 3.4 * ek
        b.C([(x, y + .5), (x + 1.6, y + 1.5), (x + 1.8, y + 1.5 + L * .7)], [1.4, 1.5, 1.2],
            MARK if g["mark_mat"] == MARK else BODY, 21, "ear", sym=sym, **ek_)
    if facing:   # the far ear peeks behind the head
        if k in (0, 2):
            b.P([(x - 3.6, y + 1.6), (x - .8, y + 1.2), (x - 2.2, y - (2 + 3 * ek) * (1.2 if k == 2 else .8))],
                MARK, 4, "farear", keep=True, role="ear", pivot=(x - 2.0, y + 1.4))


def _bushy_tail(b, g, d, base, s, size):
    x, y = base
    if g["f3"] in (0, 2):
        q1 = (x + s * size * .5, y + .6)
        q2 = (x + s * size * .95, y - size * .7)
        r2 = 1.3 + .9 * size / 4
        b.C([(x, y), q1, q2], [1.0, 1.3, r2], BODY, 5, "tail", role="tail", pivot=base)
        b.E(q2[0], q2[1] - r2 * .4, r2 * 1.05, r2 * 1.5, ACC if g["f3"] == 2 else BELLY, 6, "tailtip", rot=-.3 * s,
            on=("tail",), role="tail", pivot=base)
    else:
        b.C([(x, y), (x + s * size * .6, y - size * .1), (x + s * size * .85, y - size * .8),
             (x + s * size * .55, y - size * 1.2)], [1.1, .9, .7, .5], BODY, 5, "tail", role="tail", pivot=base)


def _mane(b, g, d, cx, cy, R1):
    n = 10
    R2 = R1 * (1.32 + .12 * d.fk)
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n
        r = R2 if i % 2 == 0 else R1
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r * .95))
    b.P(pts, ACC if g["f2"] == 0 else MARK, 4, "mane")


def fera(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    d.eyes = ("gem", "slit", "sclera")
    d.mouth = "cat" if g["mouth"] == "cat" else "smile"
    m = d.m
    if plan == 0:      # four-legged 3/4, nimble, tail up
        L, bh = lerp(6.5, 13, m) * d.wk ** .5, lerp(5, 6.6, m) * d.wk
        hx, hy = quad(b, g, d, L, bh, lerp(1.0, 5.2, m) * d.lk, lerp(1.4, 1.8, m) * (1 + .3 * d.pac),
                      lerp(0, 2.0, m), lerp(5.4, 4.2, m) * d.hk / lerp(1.55, 1, m), slim=.9)
        hr = d.hr
        b.E(hx - hr * .45, hy + hr * .4, hr * .55, hr * .38, BELLY, 21, "muzzle", on=("head",))
        b.E(hx - hr * .78, hy + hr * .22, hr * .17, hr * .12, DARK, 22, "nose", line=False)
        d.head_cx = hx - hr * .02
        d.mouth_x, d.mouth_y = hx - hr * .45, hy + hr * .45
        _ears(b, g, d, hx + hr * .3, hy - hr * .7, d.ck, True)
        _bushy_tail(b, g, d, (L * .45, d.by - bh * .1), 1, 3 + 5 * m)
        if t >= 3 and g["f2"] in (0, 1):
            _mane(b, g, d, hx + hr * .2, hy + hr * .3, hr * 1.1)
    elif plan == 1:    # sitting: wide haunches, front paws straight down, tail around
        hw_ = lerp(4.2, 7.0, m) * d.wk
        hh = lerp(3.2, 5.6, m)
        cw, ch = hw_ * .72, lerp(3.5, 7.5, m)
        b.E(0, -hh / 2, hw_, hh / 2, BODY, 9, "body")
        cy = -hh - ch * .25
        b.E(0, cy, cw, ch / 2, BODY, 10, "body")
        d.body(0, cy, cw * 2, ch)
        if g["belly"]:
            b.E(0, cy + ch * .1, cw * .5, ch * .38, BELLY, 11, "belly", on=("body",))
        if t >= 1:
            x = cw * .42
            wave = d.soc > .12
            for sd in (-1, 1):
                if wave and sd == -d.side:     # sociable: one paw up, waving
                    b.C([(sd * x, cy), (sd * (x + 1.5), cy - ch * .55)], lerp(1.1, 1.5, m), BODY, 14, "leg",
                        role="arm", pivot=(sd * x, cy), side=sd)
                    b.E(sd * (x + 1.5), cy - ch * .6, lerp(1.3, 1.8, m), lerp(1.2, 1.6, m), BODY, 15, "paw",
                        role="arm", pivot=(sd * x, cy), side=sd)
                else:
                    b.C([(sd * x, cy), (sd * x, -.9)], [lerp(1.1, 1.6, m), lerp(1.1, 1.5, m)], BODY, 14, "leg",
                        role="arm", pivot=(sd * x, cy), side=sd)
                    b.E(sd * x, -.7, lerp(1.3, 1.8, m), .8, BODY, 15, "paw", role="arm", pivot=(sd * x, cy),
                        side=sd)
            b.E(hw_ * .82, -.7, lerp(1.3, 2.0, m), .85, BODY, 12, "foot", sym=True, role="leg")
        hr = 5.4 * d.hk
        hcy = cy - ch / 2 - hr * .5
        b.E(0, hcy, hr * 1.05, hr * .92, BODY, 20, "head")
        d.head(0, hcy, hr, hr * 1.05, .92)
        b.E(0, hcy + hr * .45, hr * .48, hr * .32, BELLY, 21, "muzzle", on=("head",))
        b.E(0, hcy + hr * .26, hr * .17, hr * .12, DARK, 22, "nose", line=False)
        d.mouth_y = hcy + hr * .46
        _ears(b, g, d, hr * .62, hcy - hr * .62, d.ck, False)
        s = d.side
        tl = 3 + 4 * m
        b.C([(s * hw_ * .7, -hh * .5), (s * (hw_ + tl * .4), -hh * .3), (s * (hw_ + tl * .55), -hh - tl * .5),
             (s * (hw_ + tl * .2), -hh - tl * .9)], [1.2, 1.2, 1.0, .7], BODY, 5, "tail", role="tail",
            pivot=(s * hw_ * .7, -hh * .5))
        if g["f3"] == 2:
            b.E(s * (hw_ + tl * .25), -hh - tl * .85, 1.4, 1.6, ACC, 6, "tailtip", on=("tail",), role="tail",
                pivot=(s * hw_ * .7, -hh * .5))
        d.neck = (0, cy - ch / 2 + .8, cw * 1.6)
        d.hands = [(cw * .42, -1.2), (-cw * .42, -1.2)]
        if t >= 3 and g["f2"] in (0, 1):
            _mane(b, g, d, 0, hcy + .5, hr * 1.12)
        if t >= 2:
            for k in (0, 1):
                y = hcy + hr * (.15 + k * .35)
                b.P([(hr * .9, y - 1.0), (hr * .9, y + 1.0), (hr * 1.05 + 1.2 + .5 * d.fk, y + .2)], BODY, 19,
                    "tuft", sym=True, keep=True)
    else:              # upright biped: big ears, round body
        upright(b, g, d, head_k=1.02, limb_k=1.12, head_w=1.08, neck=.58)
        hr, hy = d.hr, d.hy
        b.E(0, d.hcy + hr * hy * .45, hr * .5, hr * hy * .33, BELLY, 21, "muzzle", on=("head",))
        b.E(0, d.hcy + hr * hy * .26, hr * .17, hr * .12, DARK, 22, "nose", line=False)
        d.mouth_y = d.hcy + hr * hy * .47
        _ears(b, g, d, d.hw * .55, d.hcy - hr * hy * .62, d.ck, False)
        _bushy_tail(b, g, d, (d.side * d.bw * .3, d.by + d.bh * .38), d.side, 3 + 4.5 * m)
        if t >= 3 and g["f2"] in (0, 1):
            _mane(b, g, d, 0, d.hcy + .5, hr * 1.15)
    if t >= 2 and g["f4"] >= 2:
        x, y = d.head_cx, d.htop
        b.P([(x, y + .8), (x + 1.0, y + 2.2), (x, y + 3.6), (x - 1.0, y + 2.2)], ACC, 23, "gem", on=("head",))
    markings(b, g, d)
    return d
