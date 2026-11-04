"""Helpers shared by more than one body-plan family."""
import math

from ..core import BODY, BELLY, MARK


GROW = (.42, .65, .85, 1.0, 1.15)          # feature growth per stage index


def lerp(a, b, t):
    return a + (b - a) * t


class D:
    """Anchors: head (head_cx, hcy, hr, hw, hy, htop), torso (bx, by, bw, bh, btop), neck (x, y, w) or None,
    hands [(x, y)], eye_dx/eye_y, mouth_x/mouth_y/mouth, eyes (allowed styles), facing (3/4 plan)."""

    def __init__(self, g, P, t):
        self.t, self.m = t, t / 4
        c = {k: P[k] - .5 for k in P}
        self.cur, self.soc, self.pac, self.ind, self.cri = (c[k] for k in ("curiosidade", "sociabilidade",
                                                                           "paciencia", "independencia",
                                                                           "criatividade"))
        self.G = GROW[t]
        self.fk = (1 + .6 * self.ind + .3 * self.cri) * self.G      # horns, crests, spikes, fins
        self.ck = (1 + .8 * self.cur) * self.G                        # ears, antennae
        self.wk = 1 + .45 * self.pac - .4 * self.ind + .15 * self.soc  # body width
        self.lk = 1 + .5 * self.ind - .35 * self.pac                  # limb length
        self.hk = lerp(1.55, 1.0, self.m) * (1 + .3 * self.cur)       # head scale (babies: big heads)
        self.side = g["side"]
        self.facing = False
        self.neck = None
        self.hands = []
        self.mouth = "smile"
        self.mouth_x = None
        self.eyes = ("gem",)
        self.no_slots = frozenset()      # accessory slots this plan cannot wear
        self.acc_max = 3

    def head(self, cx, cy, hr, hw=None, hy=1.0):
        self.head_cx, self.hcy, self.hr, self.hw, self.hy = cx, cy, hr, hw or hr, hy
        self.htop = cy - hr * hy
        self.eye_dx = (hw or hr) * .44
        self.eye_y = cy + hr * hy * .08

    def body(self, bx, by, bw, bh):
        self.bx, self.by, self.bw, self.bh = bx, by, bw, bh
        self.btop = by - bh / 2


def markings(b, g, d):
    mk, mm = g["mark"], g["mark_mat"]
    hx, hr, hy = d.head_cx, d.hr, d.hy
    if mk == "stripes":
        for i in (-1, 0, 1):
            x = hx + i * hr * .34
            b.C([(x, d.htop - .5), (x + i * .3, d.htop + hr * .4)], [hr * .1, hr * .05], mm, 21, "mk",
                on=("head",), line=False)
        for k in (-.25, .05):
            b.C([(d.bx - d.bw, d.by + d.bh * k), (d.bx - d.bw * .3, d.by + d.bh * (k + .06))], d.bh * .05, mm, 21,
                "mk", sym=not d.facing, on=("body",), line=False)
    elif mk == "spots":
        for x, y, r in ((.55, -.5, .15), (-.6, -.35, .12), (.68, .02, .1)):
            b.E(hx + x * d.hw, d.hcy + y * hr * hy, r * hr, r * hr, mm, 21, "mk", on=("head",), line=False)
        for x, y in ((.35, -.1), (-.3, .2), (.1, .32)):
            b.E(d.bx + x * d.bw, d.by + y * d.bh, d.bw * .07 + .3, d.bw * .07 + .3, mm, 21, "mk", on=("body",),
                line=False)
    elif mk == "mask":
        b.E(hx, d.eye_y, d.hw * .95, hr * hy * .32, mm, 21, "mk", on=("head",), line=False)
    elif mk == "cap":
        b.E(hx, d.htop + hr * .05, d.hw * 1.0, hr * hy * .42, mm, 21, "mk", on=("head",), line=False)
    elif mk == "socks":
        b.E(0, -.4, 80, 1.5 if d.t else 1.1, mm, 21, "mk", on=("foot", "leg", "paw"), line=False)


def leg(b, x0, y0, x1, r, mat=BODY, z=8, name="leg", sym=False, foot=1.0, toe=-1):
    """Leg from (x0, y0) to the ground at x1, with a foot pointing to `toe` (-1 left, +1 right, 0 front)."""
    b.C([(x0, y0), (x1, -r * .8)], [r, r * .9], mat, z, name, sym=sym)
    if foot:
        b.E(x1 + toe * r * .35, -r * .7, r * 1.2 * foot, r * .72, mat, z + 1, "foot", sym=sym)


def upright(b, g, d, head_k=1.0, body_k=1.0, limb_k=1.0, leg_k=1.0, arms=True, legs=True, arm_mat=BODY,
            head_w=1.0, neck=.62, pear=0.0, body_hk=1.0, boxy=False):
    """Front-view biped skeleton (the M11 round-1 plan, kept for the plans that are naturally upright)."""
    t, m = d.t, d.m
    hr = 6.0 * head_k * (1 + .3 * d.cur) * (1 - .05 * m)
    hy = g["hy"] * (1.0 if t else .92)
    hw = hr * head_w * (1 + .08 * d.soc)
    bw = lerp(7.2, 8.8, m) * body_k * g["bodyk"] * d.wk
    bh = (4.2, 6.6, 8.6, 9.8, 10.8)[t] * body_hk * (1 + .1 * d.pac)
    ll = (0, 2.0, 3.6, 4.4, 5.2)[t] * leg_k * g["limbk"] * d.lk if legs else 0
    lr = lerp(1.5, 1.9, m) * limb_k * g["limbk"] * (1 + .3 * d.pac - .15 * d.ind)
    al = (0, 3.0, 4.4, 5.2, 6.0)[t] * g["limbk"] * (1 + .25 * d.soc) if arms else 0
    ar = lerp(1.15, 1.55, m) * limb_k
    by = -ll - bh * .46 - (.6 if legs and t else 0)
    btop = by - bh / 2
    hcy = btop - hr * hy * ((neck if t else .5) - .05 * d.ind) + (.8 if t == 0 else 0)
    d.body(0, by, bw, bh)
    d.head(0, hcy, hr, hw, hy)
    d.lr, d.ll = lr, ll
    if boxy:
        b.R(-bw / 2, by - bh / 2, bw / 2, by + bh / 2, r=bw * .22, mat=BODY, z=10, name="body")
        b.R(-hw, hcy - hr * hy, hw, hcy + hr * hy, r=hr * .42, mat=BODY, z=20, name="head")
    else:
        b.E(0, by, bw / 2, bh / 2, BODY, 10, "body")
        if pear and t:
            b.E(0, by + bh * .22, bw / 2 * (1 + pear), bh * .32, BODY, 10, "body")
        b.E(0, hcy, hw, hr * hy, BODY, 20, "head")
    if g["belly"]:
        b.E(0, by + bh * .1, bw * .3 * (1 + pear * .6), bh * .36, BELLY, 11, "belly", on=("body",))
    hipx = bw * .3 * (1 + pear * .5)
    d.footx = hipx * (1 + .5 * d.pac)
    if t == 0:
        b.E(hipx * 1.05, -.9, lr * 1.05, .95, BODY, 8, "foot", sym=True)
    elif legs:
        b.C([(hipx, by + bh * .2), (d.footx, -lr * .8)], [lr, lr * .92], BODY, 8, "leg", sym=True)
        b.E(d.footx + lr * .25, -lr * .72, lr * 1.2, lr * .75, BODY, 9, "foot", sym=True)
    if arms and t >= 1:
        ang = math.radians(min(78, 30 + 110 * max(0, d.soc)) - 25 * max(0, d.pac - .05) - 20 * max(0, d.ind - .1))
        sx, sy = bw * .4, by - bh * .22
        hx, hy2 = sx + al * math.sin(ang), sy + al * math.cos(ang)
        b.C([(sx, sy), (hx, hy2)], [ar * 1.05, ar * .9], arm_mat, 14, "arm", sym=True)
        b.E(hx, hy2, ar * 1.05, ar, arm_mat, 15, "hand", sym=True)
        d.hands = [(hx, hy2), (-hx, hy2)]
        d.ar = ar
    d.neck = (0, btop + .6, bw * .48)
    return d


def quad(b, g, d, L, bh, ll, lr, neck_len, hr, tail=True, slim=1.0):
    """Quadruped seen 3/4 from the front-left: horizontal torso, near and far legs, head raised on a neck."""
    t = d.t
    by = -ll - bh * .45
    d.body(0, by, L, bh)
    b.E(0, by, L / 2, bh / 2, BODY, 10, "body")
    if g["belly"]:
        b.E(-L * .05, by + bh * .3, L * .36, bh * .24, BELLY, 11, "belly", on=("body",))
    for k, x in enumerate((-L * .3, L * .3)):
        if t == 0:
            b.E(x - .4, -.8, lr, .9, BODY, 12, "foot")
            continue
        leg(b, x + 1.0, by + bh * .1, x + 1.3, lr * .9 * slim, MARK, 5, "leg", toe=-1)        # far legs
        leg(b, x, by + bh * .2, x - .2, lr * slim, BODY, 12, "leg", toe=-1)                      # near legs
    hx = -L * .5 + hr * .1
    hy = by - bh * .35 - neck_len - hr * .35
    if t >= 1:
        b.C([(-L * .28, by - bh * .1), (hx + hr * .2, hy + hr * .3)], [bh * .34, hr * .5], BODY, 15, "neck")
    b.E(hx, hy, hr, hr * .92, BODY, 20, "head")
    d.head(hx + hr * .08, hy, hr, hr, .92)
    d.eye_dx = hr * .4
    d.facing = True
    d.neck = (hx + hr * .3, hy + hr * .9, hr * .9)
    d.lr = lr
    return hx, hy
