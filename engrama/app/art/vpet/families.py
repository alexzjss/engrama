"""Body plans: 8 families x 3 sub-plans, each with its own skeleton and silhouette.

Every plan is a pure function of (genes, persona, stage index). Stage only scales proportions and grows the
features (horns, wings, fins, petals...), so a lineage keeps one body plan for life. 3/4 plans are drawn facing
left; gen.sprite flips them by the seed's `side`. Every plan names its torso "body" and its head "head" (markings
and accessories rely on that) and fills the anchors of `D`.
"""
import math

from .core import BODY, BELLY, ACC, MARK, BONE, DARK, GLASS, GOLD, Builder

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


# --- shared pieces ------------------------------------------------------------------------------------------------
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


def tail_chain(b, base, length, r0, up=1.0, mat=BODY, z=5, name="tail", s=1):
    x, y = base
    pts = [(x, y), (x + s * length * .45, y + r0 * .6), (x + s * length * .85, y - length * .25 * up),
           (x + s * length, y - length * .6 * up)]
    b.C(pts, [r0, r0 * .78, r0 * .5, r0 * .3], mat, z, name)
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


def membrane_wing(b, sx, sy, ws, z=2, mat=ACC, name="wing", sym=False, flip=1, struts=True):
    """Bat-like wing rising up-right from (sx, sy); flip=-1 mirrors it."""
    f = flip
    top, tip = (sx + f * ws * .55, sy - ws * 1.25), (sx + f * ws * 1.3, sy - ws * .9)
    pts = [(sx - f * .4, sy + .8), top, tip, (sx + f * ws * 1.15, sy - ws * .1), (sx + f * ws * .9, sy - ws * .32),
           (sx + f * ws * .72, sy + ws * .12), (sx + f * ws * .45, sy - ws * .08), (sx + f * .6, sy + ws * .35)]
    b.P(pts, mat, z, name, sym=sym, keep=True)
    b.C([(sx, sy + .5), top, tip], [.9, .65, .4], BODY, z + .5, name + "arm", sym=sym, keep=True)
    if struts:                          # finger struts from the wrist to the scallop points
        for q in (pts[4], pts[6]):
            b.C([top, q], [.5, .3], BODY, z + .4, name + "arm", sym=sym, keep=True)
    b.P([(top[0] - .6, top[1] + .4), (top[0] + .6, top[1] + .2), (top[0] - .2 * f, top[1] - 1.3)], BONE, z + .5,
        name + "claw", sym=sym, keep=True)


def feather_fan(b, sx, sy, ws, a0, a1, n, z=3, name="wing", sym=False, flip=1, tipmat=ACC, len0=1.6, len1=1.1,
                width=.22):
    """Fan of overlapping elongated feathers from (sx, sy), angles a0..a1 degrees (0 = outward, 90 = up)."""
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / max(1, n - 1))
        L = ws * (len0 + (len1 - len0) * i / max(1, n - 1))
        dx, dy = math.cos(a) * flip, -math.sin(a)
        b.E(sx + dx * L * .5, sy + dy * L * .5, L * .5, ws * width, tipmat if i == 0 else BODY, z + n - i, name,
            sym=sym, rot=math.atan2(dy, dx))


# --- dragão ---------------------------------------------------------------------------------------------------
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
        tip = tail_chain(b, (L * .4, d.by + bh * .1), tl, bh * .36, up=.9)
        _tail_tip(b, g, d, tip, 1)
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
        tip = tail_chain(b, (s * d.bw * .25, d.by + d.bh * .32), tl, d.lr * 1.6 * (1 + .3 * d.m), s=s)
        _tail_tip(b, g, d, tip, s)
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
                b.E(d.footx + d.lr * (x + .1), -.35, .42, .5, BONE, 23, "claw", sym=True, line=False)
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
            grp="body")
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
            b.C([(ax - 1, ay + 1), (ax - 3.5 * k, ay + 2.5 * k)], .9, BODY, 14, "arm")
            b.E(ax - 3.6 * k, ay + 2.6 * k, 1.0, 1.0, BODY, 15, "hand")
            d.hands = [(ax - 3.6 * k, ay + 2.6 * k)]
        d.neck = (hx + hr * .3, hy + hr * .85, hr * .9)
    markings(b, g, d)
    return d


def _tail_tip(b, g, d, tip, s):
    x, y = tip
    fk = d.fk
    if g["f3"] == 0:
        b.P([(x - s * 1.6, y + .3), (x + s * 1.0, y + 1.0), (x + s * .3, y - 2.4 * fk - .6)], ACC, 6, "tailtip",
            keep=True)
    elif g["f3"] == 1:
        b.E(x, y - .8, 1.1 + fk * .7, 1.6 + fk * 1.0, ACC, 6, "tailtip")
    elif g["f3"] == 2:
        b.E(x, y, 1.2 + fk * .6, 1.2 + fk * .6, BODY, 6, "tailtip")
        for a in (-.8, .8, 2.3):
            b.P([(x + math.cos(a) * 1.0, y - math.sin(a) * 1.0), (x + math.cos(a + .6), y - math.sin(a + .6)),
                 (x + math.cos(a + .3) * (2.4 + fk), y - math.sin(a + .3) * (2.4 + fk))], BONE, 6, "tailspike",
                keep=True)


# --- fera -----------------------------------------------------------------------------------------------------
def _ears(b, g, d, x, y, scale, facing):
    ek = scale
    inner = ACC if g["f4"] % 2 else BELLY
    sym = not facing
    k = g["f1"]
    if k == 0:
        L = 2.2 + 3.4 * ek
        b.P([(x - 1.8, y + 1.4), (x + 1.6, y + 1.0), (x + .9, y - L)], BODY, 18, "ear", sym=sym, keep=True)
        b.P([(x - .7, y + .9), (x + .7, y + .7), (x + .7, y - L * .55)], inner, 19, "earin", sym=sym, on=("ear",))
    elif k == 1:
        r = 1.4 + 1.6 * ek
        b.E(x + .4, y - r * .3, r, r, BODY, 18, "ear", sym=sym)
        b.E(x + .4, y - r * .25, r * .55, r * .55, inner, 19, "earin", sym=sym, on=("ear",))
    elif k == 2:
        L = 3 + 5 * ek
        b.C([(x - .3, y + .5), (x + .5, y - L * .6), (x + .9, y - L)], [1.5, 1.4, .9], BODY, 18, "ear", sym=sym)
        b.C([(x - .2, y), (x + .5, y - L * .6), (x + .8, y - L * .9)], [.6, .6, .35], inner, 19, "earin", sym=sym,
            on=("ear",))
    else:
        L = 2.5 + 3.4 * ek
        b.C([(x, y + .5), (x + 1.6, y + 1.5), (x + 1.8, y + 1.5 + L * .7)], [1.4, 1.5, 1.2],
            MARK if g["mark_mat"] == MARK else BODY, 21, "ear", sym=sym)
    if facing:   # the far ear peeks behind the head
        if k in (0, 2):
            b.P([(x - 3.6, y + 1.6), (x - .8, y + 1.2), (x - 2.2, y - (2 + 3 * ek) * (1.2 if k == 2 else .8))],
                MARK, 4, "farear", keep=True)


def _bushy_tail(b, g, d, base, s, size):
    x, y = base
    if g["f3"] in (0, 2):
        q1 = (x + s * size * .5, y + .6)
        q2 = (x + s * size * .95, y - size * .7)
        r2 = 1.3 + .9 * size / 4
        b.C([(x, y), q1, q2], [1.0, 1.3, r2], BODY, 5, "tail")
        b.E(q2[0], q2[1] - r2 * .4, r2 * 1.05, r2 * 1.5, ACC if g["f3"] == 2 else BELLY, 6, "tailtip", rot=-.3 * s,
            on=("tail",))
    else:
        b.C([(x, y), (x + s * size * .6, y - size * .1), (x + s * size * .85, y - size * .8),
             (x + s * size * .55, y - size * 1.2)], [1.1, .9, .7, .5], BODY, 5, "tail")


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
                    b.C([(sd * x, cy), (sd * (x + 1.5), cy - ch * .55)], lerp(1.1, 1.5, m), BODY, 14, "leg")
                    b.E(sd * (x + 1.5), cy - ch * .6, lerp(1.3, 1.8, m), lerp(1.2, 1.6, m), BODY, 15, "paw")
                else:
                    b.C([(sd * x, cy), (sd * x, -.9)], [lerp(1.1, 1.6, m), lerp(1.1, 1.5, m)], BODY, 14, "leg")
                    b.E(sd * x, -.7, lerp(1.3, 1.8, m), .8, BODY, 15, "paw")
            b.E(hw_ * .82, -.7, lerp(1.3, 2.0, m), .85, BODY, 12, "foot", sym=True)
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
             (s * (hw_ + tl * .2), -hh - tl * .9)], [1.2, 1.2, 1.0, .7], BODY, 5, "tail")
        if g["f3"] == 2:
            b.E(s * (hw_ + tl * .25), -hh - tl * .85, 1.4, 1.6, ACC, 6, "tailtip", on=("tail",))
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


def _mane(b, g, d, cx, cy, R1):
    n = 10
    R2 = R1 * (1.32 + .12 * d.fk)
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n
        r = R2 if i % 2 == 0 else R1
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r * .95))
    b.P(pts, ACC if g["f2"] == 0 else MARK, 4, "mane")


# --- ave ------------------------------------------------------------------------------------------------------
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
                [1.2, .35], ACC if i == 1 else BODY, 3 + i, "tailf", keep=True)
        if t >= 1:
            for x, z, mt in ((L * .12, 6, MARK), (-L * .08, 7, ACC)):
                b.C([(x, by + bh * .3), (x - .3, -.4)], .5 + .2 * m, mt if mt != MARK else ACC, z, "leg", keep=True)
                b.C([(x - .3, -.35), (x - 1.6, -.35)], .45, ACC, z, "toe", keep=True)
        if t >= 1:
            ws = L * (0, .5, .55, .62, .7)[t] * (1 + .2 * d.soc)
            wy = by - bh * (.2 + .05 * max(0, d.soc))
            b.C([(-L * .22, wy), (L * .08, by + bh * .02), (L * .2 + ws * .55, by + bh * .05)],
                [bh * .38, bh * .32, .6], BODY, 12, "wing", keep=True)
            b.E(L * .12 + ws * .35, by + bh * .05, ws * .32, bh * .16, ACC, 13, "wingtip", on=("wing",))
            for k in range(1 + (t >= 3) + (t >= 4)):          # primaries fan out past the tail
                y = by + bh * (.02 + .1 * k)
                b.P([(L * .2 + ws * .3, y - .8), (L * .2 + ws * .3, y + .8), (L * .25 + ws * (.75 + .12 * k), y + .3)],
                    ACC if k == 0 else BODY, 12.5, "primary", keep=True)
            if t >= 3:   # far wing peeks above the back
                b.E(L * .02, by - bh * .5, ws * .38, bh * .22, MARK, 2, "farwing", rot=-.35)
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
                [bw * .14, bw * .15, .5], BODY, 14, "wing", sym=True, keep=True)
            b.E(bw * .46 * sp, by + bh * .22, bw * .08, bh * .14, ACC, 15, "wingtip", sym=True, on=("wing",))
            for x in (-.6, 0, .6):
                b.E(bw * .2 + x, -.4, .45, .55, ACC, 9, "talon", sym=True, line=False)
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
            b.E(bw * .55, by - .5, 1.6, 1.0, BODY, 9, "wing", sym=True, rot=-.4)
        else:
            feather_fan(b, bw * .38, by - bh * .3, ws, -15, 50, 4 + (t >= 3), z=3, name="wing", sym=True,
                        len0=1.25, len1=.95, width=.19)
        tl = 2 + 4 * m
        for i, a in enumerate((-.45, 0, .45)):
            b.C([(0, by + bh * .3), (math.sin(a) * tl * .8, by + bh * .4 + tl)], [1.0, .4], ACC if i == 1 else BODY,
                2, "tailf", keep=True)
        d.neck = (0, hcy + hr * .8, hr * 1.2)
    markings(b, g, d)
    return d


# --- inseto ---------------------------------------------------------------------------------------------------
def _antennae(b, g, d, x, y, L, sym=True):
    k = g["f1"]
    if k == 0:
        b.C([(x, y), (x + L * .3, y - L)], .45, DARK, 17, "ant", sym=sym, keep=True)
        b.E(x + L * .3, y - L, 1.0 + .3 * d.fk, 1.0 + .3 * d.fk, ACC, 18, "antip", sym=sym)
    elif k == 1:
        b.C([(x, y), (x + L * .2, y - L * .8), (x + L * .6, y - L), (x + L * .7, y - L * .7)], .45, DARK, 17, "ant",
            sym=sym, keep=True)
    elif k == 2:
        b.C([(x, y), (x + L * .5, y - L)], .45, DARK, 17, "ant", sym=sym, keep=True)
        b.P([(x + L * .15, y - L * .3), (x + L * .55, y - L * 1.05), (x + L * .7, y - L * .4)], ACC, 16, "antf",
            sym=sym, keep=True)
    else:
        b.C([(x, y), (x + L * .1, y - L * .9), (x + L * .7, y - L * 1.15)], [.5, .4, .3], DARK, 17, "ant", sym=sym,
            keep=True)


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
                    keep=True)
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
            b.E(tw * .6 + ws * .55, ty - th * .3 - ws * .35, ws * .62, ws * .36, GLASS, 3, "wing", sym=True, rot=-.7,
                flat=True)
            b.E(tw * .5 + ws * .4, ty - th * .1, ws * .4, ws * .24, GLASS, 2, "wing2", sym=True, rot=-.25, flat=True)
            for k, x in enumerate((.25, .42)):
                b.C([(ab_w * x, ay + ab_h * .3), (ab_w * x + .5, -.3)], .5 + .15 * m, DARK, 6 - k, "leg", sym=True,
                    keep=True)
            ex, ey = tw * .9 + .8, ty + th * .15
            b.C([(tw * .8, ty - th * .1), (ex, ey)], lerp(.7, 1.0, m), DARK, 14, "arm", sym=True, keep=True)
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
        b.E(ws * .8, by - ws * .38, ws * .68, ws * .5, wm, 3, "wing", sym=True, rot=-.55)
        b.E(ws * .62, by + ws * .3, ws * .45, ws * .38, wm, 2, "wing2", sym=True, rot=.5)
        if t >= 1:
            b.E(ws * 1.1, by - ws * .62, ws * .3, ws * .22, other, 4, "wband", sym=True, rot=-.55, on=("wing",))
            b.E(ws * .78, by - ws * .38, ws * .17, ws * .17, BELLY, 4, "eyespot", sym=True, on=("wing",))
            b.E(ws * .78, by - ws * .38, ws * .08, ws * .08, DARK, 5, "eyespot2", sym=True, on=("eyespot",),
                line=False)
            b.E(ws * .72, by + ws * .4, ws * .15, ws * .15, other, 4, "spot2", sym=True, on=("wing2",))
        d.neck = (0, hcy + hr * .8, hr * 1.4)
        d.no_slots = frozenset({"back"})
    markings(b, g, d)
    return d


# --- planta ---------------------------------------------------------------------------------------------------
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


# --- espírito -------------------------------------------------------------------------------------------------
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


# --- aquático -------------------------------------------------------------------------------------------------
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


# --- máquina --------------------------------------------------------------------------------------------------
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


FAMILY_FN = dict(draco=draco, fera=fera, ave=ave, inseto=inseto, planta=planta, espirito=espirito,
                 aquatico=aquatico, maquina=maquina)
