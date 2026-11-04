import math

from ..core import BODY, ACC, MARK, BONE, DARK, GLASS
from .common import D, lerp, upright


def _antenna(b, g, d, x, top, L):
    k = g["f1"]
    if k == 0:
        b.C([(x, top + .6), (x, top - L)], .45, DARK, 17, "ant", keep=True)
        b.E(x, top - L, 1.0 + .2 * d.fk, 1.0 + .2 * d.fk, ACC, 18, "antb")
    elif k == 1:
        for sd in (-1, 1):
            b.C([(x + sd * d.hw * .45, top + .6), (x + sd * d.hw * .55, top - L)], .45, DARK, 17, "ant", keep=True)
            b.E(x + sd * d.hw * .55, top - L, .9, .9, ACC, 18, "antb")
    elif k == 2:
        for sd in (-1, 1):
            b.E(x + sd * (d.hw + .4), d.hcy, 1.2 + .5 * d.fk, 1.6 + .9 * d.fk, ACC, 18, "bolt")
    else:
        b.P([(x - 1.4, top + 1), (x + 1.4, top + 1), (x + d.side * 1.4, top - L), (x - d.side * .4, top - L * .4)],
            ACC, 18, "fin")


def maquina(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    d.eyes = ("visor", "glow", "gem")
    d.mouth = "grille" if g["mouth"] in ("fang", "cat") else "line"
    m = d.m
    if plan == 0:      # boxy biped
        upright(b, g, d, boxy=True, limb_k=.95, leg_k=.95)
        hr, hy = d.hr, d.hy
        b.R(-d.hw * .78, d.hcy - hr * hy * .52, d.hw * .78, d.hcy + hr * hy * .62, r=hr * .3, mat=GLASS, z=21,
            name="screen", on=("head",), flat=True)
        b.R(-d.bw * .28, d.by - d.bh * .28, d.bw * .28, d.by + d.bh * .12, r=.8, mat=ACC, z=12, name="panel",
            on=("body",), flat=True)
        d.mouth_y = d.hcy + hr * hy * .36
        for hx, hy2 in d.hands[:1]:
            b.E(d.bw * .42, d.by - d.bh * .22, d.ar * 1.15, d.ar * 1.15, MARK, 16, "joint", sym=True)
        if t >= 3:
            b.R(d.bw * .25, d.btop - .8, d.bw * .62, d.btop + d.bh * .22, r=1.0, mat=ACC, z=17, name="pad", sym=True)
        if t >= 4:
            b.R(d.bw * .35, d.btop - 3.5, d.bw * .62, d.btop + 2, r=.8, mat=MARK, z=3, name="jet", sym=True)
            b.E(d.bw * .485, d.btop - 3.8, .9, 1.0, ACC, 4, "flame", sym=True)
        _antenna(b, g, d, 0, d.htop, 2.2 + 3.2 * d.fk)
    elif plan == 1:    # tank: treads, hull, turret head, cannon
        tw, th = lerp(10, 18, m) * d.wk, lerp(2.6, 4.2, m)
        b.R(-tw / 2, -th, tw / 2, 0, r=th / 2, mat=DARK, z=8, name="tread")
        nw = 3 + (t >= 2)
        for i in range(nw):
            x = -tw / 2 + th / 2 + (tw - th) * i / (nw - 1)
            b.E(x, -th / 2, th * .32, th * .32, BONE, 9, "wheel", on=("tread",), line=False)
        hw_, hh = tw * .4, lerp(2.5, 5, m)
        b.R(-hw_, -th - hh, hw_, -th + .4, r=1.0, mat=BODY, z=10, name="body")
        b.R(-hw_ * .6, -th - hh * .8, hw_ * .6, -th - hh * .25, r=.6, mat=ACC, z=11, name="panel", on=("body",),
            flat=True)
        d.body(0, -th - hh / 2, hw_ * 2, hh)
        hr = 4.6 * d.hk
        hcy = -th - hh - hr * .75
        b.R(-hr * 1.1, hcy - hr * .8, hr * 1.1, hcy + hr * .85, r=hr * .45, mat=BODY, z=20, name="head")
        b.R(-hr * .85, hcy - hr * .45, hr * .85, hcy + hr * .55, r=hr * .3, mat=GLASS, z=21, name="screen",
            on=("head",), flat=True)
        d.head(0, hcy, hr, hr * 1.1, .82)
        d.eye_dx = hr * .45
        d.mouth_y = hcy + hr * .35
        if t >= 2:
            s = d.side
            cl = lerp(3, 7, m) * (1 + .3 * d.ind)
            b.C([(s * hr * .9, hcy + hr * .3), (s * (hr + cl), hcy + hr * .1)], lerp(.9, 1.3, m), MARK, 22, "cannon")
            b.E(s * (hr + cl), hcy + hr * .1, 1.1, 1.3, ACC, 23, "muzzle")
        _antenna(b, g, d, 0, hcy - hr * .8, 2 + 3 * d.fk)
        if t >= 3:
            for sd in (-1, 1):
                b.C([(sd * hw_, -th - hh * .5), (sd * (hw_ + 2.5), -th - hh * .3), (sd * (hw_ + 3), -th - hh - 1)],
                    [1.0, .9, .8], MARK, 12, "arm", keep=True)
                b.P([(sd * (hw_ + 2.2), -th - hh - .6), (sd * (hw_ + 3.8), -th - hh - .6),
                     (sd * (hw_ + 3), -th - hh - 3)], ACC, 13, "claw", keep=True)
            d.hands = [(hw_ + 3, -th - hh - 1), (-hw_ - 3, -th - hh - 1)]
        d.neck = (0, hcy + hr * .8, hr * 1.6)
    else:              # hover drone: round core, rotor on top, dangling claw arms, thruster
        d.no_slots = frozenset({"back", "neck"})
        R = lerp(5, 7.5, m) * d.wk ** .5
        fl = lerp(1.5, 5, m)
        cy = -fl - R
        b.E(0, cy, R, R, BODY, 20, "head")
        b.E(0, cy + R * .1, R * 1.02, R * .3, MARK, 21, "band", on=("head",), line=False)
        d.body(0, cy, R * 2, R * 2)
        b.R(-R * .7, cy - R * .6, R * .7, cy + R * .25, r=R * .3, mat=GLASS, z=22, name="screen", on=("head",),
            flat=True)
        d.head(0, cy - R * .18, R * .7, R * .7, .8)
        d.eye_dx = R * .3
        d.mouth_y = cy + R * .05
        d.mouth = "none" if d.mouth == "line" else d.mouth
        b.R(-R * .35, cy + R * .8, R * .35, cy + R * 1.2, r=.4, mat=MARK, z=12, name="jetbox")
        b.E(0, cy + R + fl * .55, R * .28, fl * .55, ACC, 11, "flame")
        mast = lerp(1.0, 2.5, m)
        b.C([(0, cy - R * .9), (0, cy - R - mast)], .5, DARK, 17, "mast", keep=True)
        rw = lerp(3, 7, m) * (1 + .3 * d.cri)
        b.E(0, cy - R - mast - .2, rw, .55 + .1 * m, ACC, 18, "rotor")
        if t >= 1:
            for sd in (-1, 1):
                a1 = (sd * (R + 1.5), cy + R * .3)
                a2 = (sd * (R + 2.0 + m), cy + R * .9 + 1.5 * m)
                b.C([(sd * R * .85, cy), a1, a2], [.8, .7, .6], MARK, 13, "arm", keep=True)
                b.P([(a2[0] - .9, a2[1]), (a2[0] + .9, a2[1]), (a2[0] + sd * .5, a2[1] + 1.8)], ACC, 14, "claw",
                    keep=True)
            d.hands = [(R + 2, cy + R), (-R - 2, cy + R)]
        if t >= 2:
            n = 16
            ring = [(math.cos(2 * math.pi * i / n) * R * 1.35, cy + math.sin(2 * math.pi * i / n) * R * .35)
                    for i in range(n + 1)]
            b.C(ring[n // 2:], .5, BONE, 1, "ring", keep=True)
            b.C(ring[:n // 2 + 1], .5, BONE, 25, "ring", keep=True)
        d.neck = (0, cy + R * .9, R)
    if g["mark"] in ("stripes", "cap") and plan != 2:
        b.R(-d.hw, d.htop - 1, d.hw, d.htop + d.hr * .3, mat=g["mark_mat"], z=22, name="mk", on=("head",), flat=True)
    return d
