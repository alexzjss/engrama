import math

from ..core import BODY, BELLY, ACC, BONE, DARK
from .common import D, lerp, markings, quad, upright


def tail_chain(b, base, length, r0, up=1.0, mat=BODY, z=5, name="tail", s=1):
    x, y = base
    pts = [(x, y), (x + s * length * .45, y + r0 * .6), (x + s * length * .85, y - length * .25 * up),
           (x + s * length, y - length * .6 * up)]
    b.C(pts, [r0, r0 * .78, r0 * .5, r0 * .3], mat, z, name, role="tail", pivot=base)
    return pts[-1]


def horns(b, g, d, x, y, L, mat, back=1):
    """Horn pair; `back` = direction the horns sweep (front plans use 0 = straight up/out)."""
    k = g["f1"]
    if k == 0:
        b.P([(x - .9, y + .8), (x + .9, y + 1.2), (x + L * .55 + back * L * .3, y - L)], mat, 18, "horn", keep=True,
            sym=not d.facing)
    elif k == 1:
        b.C([(x, y + .5), (x + L * .2 + back * L * .3, y - L * .55), (x + L * .75 + back * L * .5, y - L * .85)],
            [1.0, .7, .3], mat, 18, "horn", sym=not d.facing, keep=True)
    elif k == 2:
        b.P([(x - .8, y + .8), (x + .8, y + .9), (x + .2 + back * L * .3, y - L * .7)], mat, 18, "horn",
            sym=not d.facing, keep=True)
        if d.t >= 3:
            b.P([(x + 1.6, y + 1.8), (x + 2.6, y + 2.2), (x + 2.4 + L * .5 + back * L * .3, y - L * .3)], mat, 18,
                "horn", sym=not d.facing, keep=True)
    else:
        b.P([(x - 1.3, y + 1.2), (x + 1.3, y + 1.2), (x + back * L * .5, y - L)], ACC, 18, "horn", keep=True,
            sym=not d.facing)


def membrane_wing(b, sx, sy, ws, z=2, mat=ACC, name="wing", sym=False, flip=1, struts=True, simple=False,
                  arm=True):
    """Bat-like wing rising up-right from (sx, sy); flip=-1 mirrors it. `simple`: one scallop and no claw (the
    quadruped, whose wing sits against the head); `arm=False`: membrane only (far wing)."""
    f = flip
    top, tip = (sx + f * ws * .55, sy - ws * 1.25), (sx + f * ws * 1.3, sy - ws * .9)
    if simple:
        pts = [(sx - f * .4, sy + .8), top, tip, (sx + f * ws * 1.05, sy - ws * .08), (sx + f * ws * .78, sy - ws * .3),
               (sx + f * ws * .62, sy + ws * .12), (sx + f * .6, sy + ws * .35)]
        wk = {"role": "wing", "pivot": (sx, sy)}
        b.P(pts, mat, z, name, sym=sym, keep=True, **wk)
        if arm:
            b.C([(sx, sy + .5), top, tip], [.9, .65, .4], BODY, z + .5, name + "arm", sym=sym, keep=True, **wk)
        return
    pts = [(sx - f * .4, sy + .8), top, tip, (sx + f * ws * 1.15, sy - ws * .1), (sx + f * ws * .9, sy - ws * .32),
           (sx + f * ws * .72, sy + ws * .12), (sx + f * ws * .45, sy - ws * .08), (sx + f * .6, sy + ws * .35)]
    wk = {"role": "wing", "pivot": (sx, sy)}
    b.P(pts, mat, z, name, sym=sym, keep=True, **wk)
    b.C([(sx, sy + .5), top, tip], [.9, .65, .4], BODY, z + .5, name + "arm", sym=sym, keep=True, **wk)
    if struts:                          # finger struts from the wrist to the scallop points
        for q in (pts[4], pts[6]):
            b.C([top, q], [.5, .3], BODY, z + .4, name + "arm", sym=sym, keep=True, **wk)
    b.P([(top[0] - .6, top[1] + .4), (top[0] + .6, top[1] + .2), (top[0] - .2 * f, top[1] - 1.3)], BONE, z + .5,
        name + "claw", sym=sym, keep=True, **wk)


def _tail_tip(b, g, d, tip, s, base):
    x, y = tip
    fk = d.fk
    tk = {"role": "tail", "pivot": base}
    if g["f3"] == 0:
        b.P([(x - s * 1.6, y + .3), (x + s * 1.0, y + 1.0), (x + s * .3, y - 2.4 * fk - .6)], ACC, 6, "tailtip",
            keep=True, **tk)
    elif g["f3"] == 1:
        b.E(x, y - .8, 1.1 + fk * .7, 1.6 + fk * 1.0, ACC, 6, "tailtip", **tk)
    elif g["f3"] == 2:
        b.E(x, y, 1.2 + fk * .6, 1.2 + fk * .6, BODY, 6, "tailtip", **tk)
        for a in (-.8, .8, 2.3):
            b.P([(x + math.cos(a) * 1.0, y - math.sin(a) * 1.0), (x + math.cos(a + .6), y - math.sin(a + .6)),
                 (x + math.cos(a + .3) * (2.4 + fk), y - math.sin(a + .3) * (2.4 + fk))], BONE, 6, "tailspike",
                keep=True, **tk)


def draco(b, g, P, t):
    d = D(g, P, t)
    plan = g["plan"]
    hm = BONE if g["f4"] % 2 == 0 else ACC
    d.eyes = ("slit", "gem", "slit")
    d.mouth = "fang" if g["mouth"] != "smile" else "smile"
    if plan == 0:      # four-legged, 3/4 view, heavy tail, wings on the back
        m = d.m
        L, bh = lerp(7, 15, m) * d.wk ** .5, lerp(5.5, 8, m) * d.wk
        hx, hy = quad(b, g, d, L, bh, lerp(.9, 5.0, m) * d.lk, lerp(1.5, 2.3, m) * (1 + .3 * d.pac),
                      lerp(0, 3.5, m) * (1 + .4 * d.ind), lerp(5.2, 4.0, m) * d.hk / lerp(1.55, 1, m))
        hr = d.hr
        sn = (hx - hr * .85, hy + hr * .32)
        b.E(sn[0], sn[1], hr * .62, hr * .45, BODY, 21, "snout")
        b.E(sn[0] + .2, sn[1] + hr * .25, hr * .55, hr * .2, BELLY, 22, "jaw", on=("snout",))
        b.E(sn[0] - hr * .35, sn[1] - hr * .18, .35, .3, DARK, 22, "nostril", on=("snout",), line=False)
        d.mouth_x, d.mouth_y = sn[0] + hr * .1, sn[1] + hr * .12
        horns(b, g, d, hx + hr * .3, hy - hr * .6, hr * .85 * d.fk + .6, hm, back=1)
        tl = (3 + 7 * m) * (1 + .25 * d.ind)
        tbase = (L * .4, d.by + bh * .1)
        tip = tail_chain(b, tbase, tl, bh * .36, up=.9)
        _tail_tip(b, g, d, tip, 1, tbase)
        winged = t >= 2 and g["f2"] != 3
        # feature priority: wings > horns > back spikes; spikes only on wingless dragons, and few of them
        if t >= 1 and not winged:
            for k in range(3):
                x = -L * .15 + k * L * .22
                y = d.by - bh * .48
                b.P([(x - 1.0, y + 1.1), (x + 1.0, y + 1.1), (x + .6, y - .8 - 1.0 * d.fk)], ACC, 9, "spike",
                    keep=True)
        if winged:
            ws = L * (0, 0, .48, .58, .68)[t] * (1 + .25 * d.ind)
            if t == 2:                  # lighter adult: one simple wing, no far wing
                membrane_wing(b, L * .22, d.by - bh * .4, ws, z=3, simple=True)
            else:
                membrane_wing(b, L * .22, d.by - bh * .4, ws, z=3, struts=t >= 3)
                membrane_wing(b, L * .02, d.by - bh * .42, ws * .8, z=2, mat=ACC, name="farwing", struts=False)
        d.acc_max = 2
    elif plan == 1:    # upright, heavy-bottomed, big tail mass and wings
        upright(b, g, d, head_k=.88, body_k=1.15, limb_k=1.3, leg_k=1.1, pear=.22, body_hk=1.05)
        hr, hy = d.hr, d.hy
        b.E(0, d.hcy + hr * hy * .62, hr * (.62 + .06 * d.m), hr * hy * (.38 + .05 * d.m), BELLY, 21, "snout")
        if t >= 2:
            for sx in (-1, 1):
                b.E(sx * hr * .2, d.hcy + hr * hy * .45, .32, .3, DARK, 22, "nostril", on=("snout",), line=False)
        d.mouth_y = d.hcy + hr * hy * .62
        horns(b, g, d, hr * .5, d.hcy - hr * hy * .72, hr * .85 * d.fk, hm, back=0)
        tl = (3 + 6 * d.m) * (1 + .2 * d.ind)
        s = d.side
        tbase = (s * d.bw * .25, d.by + d.bh * .32)
        tip = tail_chain(b, tbase, tl, d.lr * 1.6 * (1 + .3 * d.m), s=s)
        _tail_tip(b, g, d, tip, s, tbase)
        if t >= 2 and g["f2"] != 3:
            ws = d.hr * (0, 0, 1.0, 1.35, 1.7)[t] * (1 + .25 * d.ind)
            membrane_wing(b, d.bw * .3, d.btop + .5, ws, sym=True)
        elif t >= 1:
            for k in (.35, .7):
                x = d.bw * k * .7
                b.P([(x - 1, d.btop + 1.2), (x + 1, d.btop + 1.5), (x + .4, d.btop - 1.5 * d.fk - .5)], ACC, 9,
                    "spike", sym=True, keep=True)
        if t >= 2:
            for x in (.0, .75):
                b.E(d.footx + d.lr * (x + .1), -.35, .42, .5, BONE, 23, "claw", sym=True, line=False, role="leg",
                pivot=d.hip)
    else:              # wyrm: long coiled body rising from the ground, small arms, frills
        m = d.m
        k = lerp(.55, 1.0, m)
        r0 = lerp(2.0, 2.5, m) * d.wk ** .5
        pts = [(8 * k, -1.4 * k), (1.5 * k, -r0 * .9), (-5.5 * k, -2.0 * k), (-7.5 * k, -7 * k), (-2 * k, -10.5 * k),
               (2.5 * k, -14.5 * k * d.lk ** .3)]
        rs = [r0 * .45, r0, r0 * 1.05, r0, r0 * .92, r0 * .82]
        b.C(pts[:4], rs[:4], BODY, 9, "coil", grp="body")
        b.C(pts[3:], rs[3:], BODY, 10, "body")
        b.C([(x - r * .3, y + r * .2) for (x, y), r in zip(pts[1:], rs[1:])], [r * .5 for r in rs[1:]], BELLY, 11,
            "belly", on=("body", "coil"))
        b.C([pts[0], (pts[0][0] + 2.5 * k, pts[0][1] - 1.5 * k)], [r0 * .45, .4], BODY, 9, "tail", keep=True,
            grp="body", role="tail", pivot=pts[0])
        d.no_slots = frozenset({"back", "wrist"})
        d.body(-1, -6 * k, 10 * k, 12 * k)
        hr = lerp(5.0, 3.9, m) * d.hk / lerp(1.55, 1, m)
        hx, hy = pts[-1][0] - .5, pts[-1][1] - hr * .55
        b.E(hx, hy, hr, hr * .9, BODY, 20, "head")
        sn = (hx - hr * .7, hy + hr * .35)
        b.E(sn[0], sn[1], hr * .55, hr * .42, BODY, 21, "snout")
        b.E(sn[0] + .2, sn[1] + hr * .22, hr * .5, hr * .18, BELLY, 22, "jaw", on=("snout",))
        d.head(hx + hr * .08, hy, hr, hr, .9)
        d.facing = True
        d.mouth_x, d.mouth_y = sn[0] + hr * .1, sn[1] + hr * .1
        horns(b, g, d, hx + hr * .35, hy - hr * .6, hr * .8 * d.fk + .5, hm, back=1)
        # whiskers + back frill
        if t >= 1:
            b.C([(sn[0] - hr * .3, sn[1]), (sn[0] - hr * .9, sn[1] + hr * .4), (sn[0] - hr * 1.2, sn[1] + hr * 1.0)],
                [.45, .35, .25], ACC, 23, "whisker", keep=True)
            for (x, y), r in list(zip(pts, rs))[2:5]:
                b.P([(x + r * .5, y - r * .6), (x + r * 1.0, y - r * .1), (x + r * 1.7 + d.fk, y - r * 1.1)], ACC, 8,
                    "frill", keep=True)
        if t >= 2:
            ax, ay = pts[4]
            b.C([(ax - 1, ay + 1), (ax - 3.5 * k, ay + 2.5 * k)], .9, BODY, 14, "arm", role="arm",
                pivot=(ax - 1, ay + 1))
            b.E(ax - 3.6 * k, ay + 2.6 * k, 1.0, 1.0, BODY, 15, "hand", role="arm", pivot=(ax - 1, ay + 1))
            d.hands = [(ax - 3.6 * k, ay + 2.6 * k)]
        d.neck = (hx + hr * .3, hy + hr * .85, hr * .9)
    markings(b, g, d)
    return d
