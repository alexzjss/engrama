"""Body plans. One shared skeleton (head, body, legs, arms) parameterised by stage maturity and persona,
then per-family features whose size grows with the stage. Same genes at every stage -> one creature maturing."""
import math

from .core import BODY, BELLY, ACC, MARK, BONE, DARK, GLASS, GOLD, Builder

GROW = (.42, .65, .85, 1.0, 1.15)          # feature growth per stage index
LEG = (.0, 2.0, 3.6, 4.4, 5.2)
ARM = (.0, 3.0, 4.4, 5.2, 6.0)
BODY_H = (4.2, 6.6, 8.6, 9.8, 10.8)


def lerp(a, b, t):
    return a + (b - a) * t


class D:  # dims bag
    pass


def skeleton(b: Builder, g, P, t, fam, legs=True, arms=True, head_k=1.0, body_k=1.0, limb_k=1.0, leg_k=1.0,
             boxy=False, arm_mat=BODY, head_w=1.0, neck=.62, pear=0.0, body_hk=1.0):
    """head_w: head x-stretch; neck: how deep the head sinks into the body; pear: extra width at the hips."""
    m = t / 4
    d = D()
    d.t, d.m = t, m
    cur, soc, pac, ind, cri = (P[k] for k in ("curiosidade", "sociabilidade", "paciencia", "independencia",
                                              "criatividade"))
    d.fk = (1 + .6 * (ind - .5) + .3 * (cri - .5)) * GROW[t]          # feature scale (horns, crests, spikes)
    d.ck = 1 + .8 * (cur - .5)                                          # sensory features (ears, antennae)
    d.hr = 6.0 * head_k * (1 + .3 * (cur - .5)) * (1 - .05 * m)
    d.hw = d.hr * head_w * (1 + .08 * (soc - .5))
    d.hy = g["hy"] * (1.0 if t else .92)
    d.bw = lerp(7.2, 8.8, m) * body_k * g["bodyk"] * (1 + .45 * (pac - .5) - .4 * (ind - .5) + .15 * (soc - .5))
    d.bh = BODY_H[t] * body_hk * (1 + .1 * (pac - .5))
    d.ll = LEG[t] * leg_k * g["limbk"] * (1 + .5 * (ind - .5) - .35 * (pac - .5)) if legs else 0
    d.lr = lerp(1.5, 1.9, m) * limb_k * g["limbk"] * (1 + .3 * (pac - .5) - .15 * (ind - .5))
    d.al = ARM[t] * g["limbk"] * (1 + .25 * (soc - .5)) if arms else 0
    d.ar = lerp(1.15, 1.55, m) * limb_k
    d.by = -d.ll - d.bh * .46 - (.6 if legs and t else 0)
    d.btop = d.by - d.bh / 2
    d.hcy = d.btop - d.hr * d.hy * ((neck if t else .5) - .05 * (ind - .5)) + (.8 if t == 0 else 0)
    d.htop = d.hcy - d.hr * d.hy
    d.side = g["side"]
    # body + head
    if boxy:
        b.R(-d.bw / 2, d.by - d.bh / 2, d.bw / 2, d.by + d.bh / 2, r=d.bw * .22, mat=BODY, z=10, name="body")
        b.R(-d.hw, d.hcy - d.hr * d.hy, d.hw, d.hcy + d.hr * d.hy, r=d.hr * .42, mat=BODY, z=20, name="head")
    else:
        b.E(0, d.by, d.bw / 2, d.bh / 2, BODY, 10, "body")
        if pear and t:
            b.E(0, d.by + d.bh * .22, d.bw / 2 * (1 + pear), d.bh * .32, BODY, 10, "body")
        b.E(0, d.hcy, d.hw, d.hr * d.hy, BODY, 20, "head")
    if g["belly"]:
        b.E(0, d.by + d.bh * .1, d.bw * .3 * (1 + pear * .6), d.bh * .36, BELLY, 11, "belly", on=("body",))
    # legs / feet
    hipx = d.bw * .3 * (1 + pear * .5)
    stance = 1 + .5 * (pac - .5)
    d.footx = hipx * stance
    if t == 0:
        b.E(hipx * 1.05, -.9, d.lr * 1.05, .95, BODY, 8, "foot", sym=True)
    elif legs:
        fx = d.footx
        b.C([(hipx, d.by + d.bh * .2), (fx, -d.lr * .8)], [d.lr, d.lr * .92], BODY, 8, "leg", sym=True)
        b.E(fx + d.lr * .25, -d.lr * .72, d.lr * 1.2, d.lr * .75, BODY, 9, "foot", sym=True)
    # arms: sociable creatures raise/open them (wave), patient ones rest them, independent ones hold them in
    d.hands = []
    if arms and t >= 1:
        ang = math.radians(min(78, 30 + 110 * max(0, soc - .5)) - 25 * max(0, pac - .55) - 20 * max(0, ind - .6))
        sx, sy = d.bw * .4, d.by - d.bh * .22
        hx, hy = sx + d.al * math.sin(ang), sy + d.al * math.cos(ang)
        b.C([(sx, sy), (hx, hy)], [d.ar * 1.05, d.ar * .9], arm_mat, 14, "arm", sym=True)
        b.E(hx, hy, d.ar * 1.05, d.ar * 1.0, arm_mat, 15, "hand", sym=True)
        d.hands = [(hx, hy)]
    d.eye_y = d.hcy + d.hr * d.hy * .08
    d.eye_x = d.hw * .44
    d.mouth_y = None
    return d


# --- shared marking patterns ---------------------------------------------------------------------------------
def markings(b, g, d):
    mk, mm = g["mark"], g["mark_mat"]
    hr, hy = d.hr, d.hy
    if mk == "stripes":
        for i in range(3 if d.t >= 2 else 2):
            x = (i - (1 if d.t >= 2 else .5)) * hr * .32
            b.C([(x, d.htop - .5), (x * 1.1, d.htop + hr * .45)], [hr * .09, hr * .05], mm, 21, "mk",
                on=("head",), line=False)
        b.C([(d.bw * .5, d.by - d.bh * .2), (d.bw * .28, d.by - d.bh * .05)], d.bh * .05, mm, 21, "mk",
            sym=True, on=("body",), line=False)
    elif mk == "spots":
        for x, y, r in ((.55, -.45, .16), (-.62, -.3, .12), (.7, .05, .1)):
            b.E(x * hr, d.hcy + y * hr * hy, r * hr, r * hr, mm, 21, "mk", on=("head",), line=False)
        b.E(d.bw * .38, d.by + d.bh * .05, d.bw * .07, d.bw * .07, mm, 21, "mk", sym=True, on=("body",))
    elif mk == "mask":
        b.E(0, d.eye_y, hr * .92, hr * hy * .34, mm, 21, "mk", on=("head",), line=False)
    elif mk == "cap":
        b.E(0, d.htop + hr * .1, hr * .95, hr * hy * .42, mm, 21, "mk", on=("head",), line=False)
    elif mk == "socks":
        b.E(0, -.5, 50, 1.6 if d.t else 1.2, mm, 21, "mk", on=("foot", "leg"), line=False)
        b.E(0, -.5, 50, 1.4, mm, 21, "mk", on=("hand",), line=False)


# --- families -------------------------------------------------------------------------------------------------
def draco(b, g, P, t):
    d = skeleton(b, g, P, t, "draco", head_k=.95, body_k=1.15, limb_k=1.25, leg_k=.8, pear=.15,
                 body_hk=1.05)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    # snout / muzzle
    b.E(0, d.hcy + hr * hy * .6, hr * (.6 + .06 * d.m), hr * hy * (.36 + .05 * d.m), BELLY, 21, "muzzle")
    if t >= 2:
        for sx in (-1, 1):
            b.E(sx * hr * .2, d.hcy + hr * hy * .42, .32, .3, DARK, 22, "nostril", on=("muzzle",), line=False)
    # horns
    hm = BONE if g["f4"] % 2 == 0 else ACC
    L = hr * .85 * fk
    bx, byy = hr * .5, d.hcy - hr * hy * .72
    if g["f1"] == 0:     # swept-out cones
        b.P([(bx - .9, byy + .8), (bx + .9, byy + 1.2), (bx + L * .55, byy - L)], hm, 18, "horn", sym=True,
            keep=True)
    elif g["f1"] == 1:   # curved back
        b.C([(bx, byy + .5), (bx + L * .2, byy - L * .55), (bx + L * .75, byy - L * .85)],
            [1.0, .7, .3], hm, 18, "horn", sym=True, keep=True)
    elif g["f1"] == 2:   # twin short + second pair later
        b.P([(bx - .8, byy + .8), (bx + .8, byy + .9), (bx + .2, byy - L * .7)], hm, 18, "horn", sym=True,
            keep=True)
        if t >= 3:
            b.P([(hr * .9, d.hcy - hr * .2), (hr * .95, d.hcy + .8), (hr + L * .6, d.hcy - L * .35)], hm, 18,
                "horn", sym=True, keep=True)
    else:                # crest fin
        b.P([(-1.2, d.htop + 1), (1.2, d.htop + 1), (0, d.htop - L * 1.0)], ACC, 18, "horn", keep=True)
        b.P([(bx * .9, byy + 1), (bx * .9 + 1.2, byy + 1.3), (bx + L * .5, byy - L * .4)], ACC, 18, "horn",
            sym=True, keep=True)
    # tail
    tl = (3.0 + 5.0 * d.m) * (1 + .2 * (P["independencia"] - .5))
    tr = d.lr * 1.25 * (1 + .3 * d.m)
    p0 = (s * d.bw * .3, d.by + d.bh * .32)
    p1 = (s * (d.bw * .5 + tl * .45), d.by + d.bh * .45)
    p2 = (s * (d.bw * .5 + tl * .9), d.by - tl * .15)
    p3 = (s * (d.bw * .5 + tl * 1.0), d.by - tl * .55)
    b.C([p0, p1, p2, p3], [tr, tr * .8, tr * .5, tr * .3], BODY, 5, "tail")
    tip = p3
    if g["f3"] == 0:
        b.P([(tip[0] - s * 1.6, tip[1] + .3), (tip[0] + s * 1.0, tip[1] + 1.0), (tip[0] + s * .3, tip[1] - 2.2 * fk)],
            ACC, 6, "tailtip", keep=True)
    elif g["f3"] == 1:
        b.E(tip[0], tip[1] - .8, 1.1 + fk * .6, 1.6 + fk * .9, ACC, 6, "tailtip")
    elif g["f3"] == 2 and t >= 1:
        for q, sc in ((p1, 1.0), (p2, .8)):
            b.P([(q[0] - 1.0, q[1] - tr * .6), (q[0] + 1.0, q[1] - tr * .6), (q[0], q[1] - tr * .6 - 1.8 * sc * fk)],
                ACC, 4, "spike", keep=True)
    # wings
    if g["f2"] != 3 and t >= 2:
        ws = hr * (.0, .0, .85, 1.2, 1.55)[t] * (1 + .25 * (P["independencia"] - .5))
        sx, sy = d.bw * .4, d.btop + 1.0
        top, tip = (sx + ws * .6, sy - ws * 1.15), (sx + ws * 1.3, sy - ws * .8)
        pts = [(sx - .5, sy + .8), top, tip, (sx + ws * 1.15, sy - ws * .15), (sx + ws * .9, sy - ws * .38),
               (sx + ws * .7, sy + ws * .1), (sx + ws * .45, sy - ws * .1), (sx + .6, sy + ws * .35)]
        b.P(pts, ACC, 2, "wing", sym=True, keep=True)
        b.C([(sx, sy + .5), top, tip], [.9, .65, .4], BODY, 3, "wingarm", sym=True, keep=True)
        b.P([(top[0] - .6, top[1] + .4), (top[0] + .6, top[1] + .2), (top[0] - .2, top[1] - 1.2)], BONE, 3,
            "wingclaw", sym=True, keep=True)
    # back spikes peeking over the shoulders
    if g["f2"] == 3 and t >= 1:
        for i, k in enumerate((.35, .7)):
            x = d.bw * k * .7
            b.P([(x - 1, d.btop + 1.2), (x + 1, d.btop + 1.5), (x + .4, d.btop - 1.5 * fk - .5)], ACC, 9,
                "spike", sym=True, keep=True)
    # claws
    if t >= 2:
        for x in (.0, .75):
            b.E(d.bw * .3 * (1 + .3 * (P["paciencia"] - .5)) + d.lr * (x + .1), -.35, .42, .5, BONE, 23, "claw",
                sym=True, line=False)
    markings(b, g, d)
    d.mouth_y = d.hcy + hr * hy * .55
    return d


def fera(b, g, P, t):
    d = skeleton(b, g, P, t, "fera", head_k=1.02, body_k=1.0, limb_k=1.12, head_w=1.08, neck=.58)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    ek = GROW[t] * d.ck
    ex, ey = hr * .58, d.hcy - hr * hy * .62
    inner = ACC if g["f4"] % 2 else BELLY
    if g["f1"] == 0:      # pointy
        L = 2.2 + 3.2 * ek
        b.P([(ex - 1.8, ey + 1.4), (ex + 1.6, ey + 1.0), (ex + .9, ey - L)], BODY, 18, "ear", sym=True, keep=True)
        b.P([(ex - .7, ey + .9), (ex + .7, ey + .7), (ex + .7, ey - L * .55)], inner, 19, "earin", sym=True,
            on=("ear",))
    elif g["f1"] == 1:    # round
        r = 1.4 + 1.5 * ek
        b.E(ex + .4, ey - r * .3, r, r, BODY, 18, "ear", sym=True)
        b.E(ex + .4, ey - r * .25, r * .55, r * .55, inner, 19, "earin", sym=True, on=("ear",))
    elif g["f1"] == 2:    # long upright
        L = 3 + 4.5 * ek
        b.C([(ex - .3, ey + .5), (ex + .5, ey - L * .6), (ex + .9, ey - L)], [1.5, 1.4, .9], BODY, 18, "ear",
            sym=True)
        b.C([(ex - .2, ey), (ex + .5, ey - L * .6), (ex + .8, ey - L * .9)], [.6, .6, .35], inner, 19, "earin",
            sym=True, on=("ear",))
    else:                 # floppy
        L = 2.5 + 3 * ek
        b.C([(hr * .7, d.hcy - hr * hy * .55), (hr + 1.0, d.hcy - hr * .2), (hr + 1.2, d.hcy + L * .45)],
            [1.4, 1.5, 1.2], MARK if g["mark_mat"] == MARK else BODY, 21, "ear", sym=True)
    # muzzle + nose
    b.E(0, d.hcy + hr * hy * .45, hr * .5, hr * hy * .33, BELLY, 21, "muzzle", on=("head",))
    b.E(0, d.hcy + hr * hy * .26, hr * .17, hr * .12, DARK, 22, "nose", line=False)
    # cheek tufts
    if t >= 2:
        for k in range(2):
            y = d.hcy + hr * hy * (.15 + k * .35)
            b.P([(hr * .85, y - 1.0), (hr * .85, y + 1.0), (hr + 1.2 + .5 * fk, y + .2)], BODY, 19, "tuft",
                sym=True, keep=True)
    # mane
    if t >= 3 and g["f2"] in (0, 1):
        n = 10
        pts = []
        R1, R2 = hr * 1.18, hr * (1.45 + .15 * fk)
        for i in range(n * 2):
            a = math.pi * i / n
            r = R2 if i % 2 == 0 else R1
            pts.append((math.cos(a) * r, d.hcy + .5 + math.sin(a) * r * .95))
        b.P(pts, ACC if g["f2"] == 0 else MARK, 4, "mane")
    # tail
    tl = 3.0 + 4.5 * d.m
    p0 = (s * d.bw * .3, d.by + d.bh * .38)
    if g["f3"] in (0, 2):
        q1 = (s * (d.bw * .55 + tl * .55), -1.2)
        q2 = (s * (d.bw * .55 + tl * 1.0), d.by + d.bh * .1)
        r2 = 1.3 + 1.0 * d.m
        b.C([p0, q1, q2], [1.0, 1.3, r2], BODY, 5, "tail")
        b.E(q2[0], q2[1] - r2 * .4, r2 * 1.05, r2 * 1.5, ACC if g["f3"] == 2 else BELLY, 6, "tailtip", rot=-.3 * s,
            on=("tail",))
    else:
        b.C([p0, (s * (d.bw * .6 + tl * .5), d.by + d.bh * .1), (s * (d.bw * .6 + tl * .7), d.by - tl * .6),
             (s * (d.bw * .6 + tl * .45), d.by - tl * .95)], [1.2, .9, .7, .5], BODY, 5, "tail")
    if t >= 2 and g["f4"] >= 2:      # forehead mark
        b.P([(0, d.htop + .8), (1.0, d.htop + 2.2), (0, d.htop + 3.6), (-1.0, d.htop + 2.2)], ACC, 23, "gem",
            on=("head",))
    markings(b, g, d)
    d.mouth_y = d.hcy + hr * hy * .45
    return d


def ave(b, g, P, t):
    d = skeleton(b, g, P, t, "ave", head_k=.92, body_k=1.25, body_hk=1.15, limb_k=.62, leg_k=.85, arms=False,
                 neck=.7)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    # beak (accent)
    bw, by0 = hr * .34, d.eye_y + hr * hy * .4
    bl = hr * (.5 + .16 * d.m) * (1 + .4 * (P["independencia"] - .5))
    b.P([(-bw, by0), (bw, by0), (bw * .3, by0 + bl * .8), (0, by0 + bl), (-bw * .3, by0 + bl * .8)], ACC, 24,
        "beak", keep=True)
    b.P([(-bw, by0 + .1), (bw, by0 + .1), (bw * .55, by0 - .9), (-bw * .55, by0 - .9)], ACC, 24, "beak")
    # crest
    L = hr * .7 * fk * (1 + .3 * (P["criatividade"] - .5))
    if g["f1"] == 0:
        for x, a in ((-1.4, -.5), (0, 0), (1.4, .5)):
            b.C([(x * .6, d.htop + 1.2), (x + a * L * .6, d.htop - L * .7), (x + a * L * 1.1, d.htop - L * .9)],
                [.9, .6, .3], ACC if x == 0 else BODY, 18, "crest", keep=True)
    elif g["f1"] == 1:
        b.C([(0, d.htop + 1), (-s * L * .25, d.htop - L * .6), (-s * L * 1.0, d.htop - L * .75),
             (-s * L * 1.4, d.htop - L * .4)], [1.3, 1.0, .7, .35], BODY, 18, "crest", keep=True)
        b.E(-s * L * 1.25, d.htop - L * .55, L * .35, L * .3, ACC, 19, "crest", on=("crest",))
    elif g["f1"] == 2:
        n = 3 + (t >= 3) * 2
        for i in range(n):
            a = (i - (n - 1) / 2) * .38
            tx, ty = math.sin(a) * L * 1.2, d.htop + 1.5 - math.cos(a) * L * 1.15
            b.P([(-1 + a * 2, d.htop + 1.6), (1 + a * 2, d.htop + 1.6), (tx, ty)], ACC if i % 2 == 0 else BODY,
                18, "crest", keep=True)
    else:
        for x in (-1.6, 0, 1.6):
            b.E(x, d.htop + .4 - (0 if x else .6), .9 + .5 * fk, 1.2 + .8 * fk, ACC, 18, "crest")
    # cheek dots
    b.E(hr * .62, d.hcy + hr * hy * .35, hr * .14, hr * .1, ACC, 22, "cheek", sym=True, on=("head",), line=False)
    # wings: folded at the sides; open and raised from perfect on (feathered, scalloped trailing edge)
    if t >= 1:
        ws = hr * (.0, .62, .8, 1.0, 1.25)[t] * (1 + .3 * (P["sociabilidade"] - .5))
        if t <= 2:
            wx, wy = d.bw * .5, d.by - d.bh * .05
            b.C([(wx - ws * .1, wy - ws * .55), (wx + ws * .12, wy + ws * .2), (wx + ws * .25, wy + ws * .95)],
                [ws * .38, ws * .36, .5], BODY, 14, "wing", sym=True, keep=True)
            for k in (0, 1):
                fx = wx + ws * (.05 + .22 * k)
                b.P([(fx - .9, wy + ws * .5), (fx + .9, wy + ws * .45), (fx + ws * .25, wy + ws * (1.25 - .2 * k))],
                    ACC if t == 2 else BODY, 13, "feather", sym=True, keep=True)
        else:                         # open wings: a fan of overlapping feathers, raised
            sx, sy = d.bw * .42, d.by - d.bh * .22
            nf = 4 + (t >= 4)
            for i in range(nf):
                a = math.radians(-5 + i * (60 / (nf - 1)))
                L = ws * (1.7 - .45 * i / (nf - 1))
                cx, cy = sx + math.cos(a) * L * .5, sy - math.sin(a) * L * .5
                b.E(cx, cy, L * .5, ws * .22, ACC if i == 0 else BODY, 8 - i, "wing", sym=True, rot=-a)
    # tail fan
    if t >= 1:
        tl = 2 + 4 * d.m
        for i, a in enumerate((-.5, 0, .5)):
            b.P([(-.9 + a, d.by + d.bh * .3), (.9 + a, d.by + d.bh * .3),
                 (a * tl * 1.6 + s * tl * .4, d.by + d.bh * .3 - tl * (1.1 - abs(a) * .5))],
                ACC if i == 1 else BODY, 2, "tailf", keep=True)
    # talons
    if t >= 1:
        for x in (-.7, .7):
            b.E(d.bw * .3 * (1 + .3 * (P["paciencia"] - .5)) + d.lr * .25 + x * d.lr, -.35, .45, .45, ACC, 23,
                "talon", sym=True, line=False)
    markings(b, g, d)
    d.mouth_y = None        # the beak is the mouth
    d.beak = (by0, bl)
    return d


def inseto(b, g, P, t):
    d = skeleton(b, g, P, t, "inseto", head_k=1.0, body_k=.82, limb_k=.62, leg_k=1.15, body_hk=1.05)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    # antennae
    L = hr * (.8 + .5 * (P["curiosidade"] - .5)) * fk + 1.5
    ax, ay = hr * .32, d.htop + 1.2
    if g["f1"] == 0:
        b.C([(ax, ay), (ax + L * .3, ay - L)], .45, DARK, 17, "ant", sym=True, keep=True)
        b.E(ax + L * .3, ay - L, 1.0 + .3 * fk, 1.0 + .3 * fk, ACC, 18, "antip", sym=True)
    elif g["f1"] == 1:
        b.C([(ax, ay), (ax + L * .2, ay - L * .8), (ax + L * .6, ay - L), (ax + L * .7, ay - L * .7)], .45, DARK,
            17, "ant", sym=True, keep=True)
    elif g["f1"] == 2:
        b.C([(ax, ay), (ax + L * .5, ay - L)], .45, DARK, 17, "ant", sym=True, keep=True)
        b.P([(ax + L * .15, ay - L * .3), (ax + L * .55, ay - L * 1.05), (ax + L * .7, ay - L * .4)], ACC, 16,
            "antf", sym=True, keep=True)
    else:
        b.C([(ax, ay), (ax + L * .1, ay - L * .9), (ax + L * .7, ay - L * 1.15)], [.5, .4, .3], DARK, 17, "ant",
            sym=True, keep=True)
    # mandibles
    if t >= 2 and g["f2"] % 3 == 2:
        my = d.hcy + hr * hy * .8
        b.C([(hr * .32, my - .5), (hr * .4, my + 1.0 * fk), (hr * .12, my + 1.6 * fk)], [.8, .6, .3], BONE, 24,
            "mandible", sym=True, keep=True)
    # thorax bands
    b.C([(-d.bw, d.by - d.bh * .12), (d.bw, d.by - d.bh * .12)], .32 + .1 * d.m, MARK, 12, "band", on=("body",),
        line=False)
    kind = g["f2"] % 3
    # shell plates (beetle) / moth collar / mantis blades
    if kind == 0 and t >= 1:
        b.E(d.bw * .5, d.by - d.bh * .1, d.bw * .32, d.bh * .58, ACC, 6, "shell", sym=True, rot=-.18)
        if t >= 2 and g["f3"] < 2:    # rhino horn
            Lh = hr * .9 * fk
            b.C([(0, d.htop + 1.6), (0, d.htop - Lh * .6), (s * Lh * .35, d.htop - Lh)], [1.4, .9, .35], ACC, 21,
                "horn", keep=True)
    elif kind == 1 and t >= 1:
        b.P([(-d.bw * .45, d.btop + .4), (d.bw * .45, d.btop + .4), (d.bw * .3, d.btop + d.bh * .35),
             (0, d.btop + d.bh * .45), (-d.bw * .3, d.btop + d.bh * .35)], BELLY, 13, "collar", line=True)
    if kind == 2 and t >= 2:
        for hx, hy2 in d.hands:
            b.C([(hx, hy2), (hx + 1.0, hy2 - 2.5 * fk), (hx + .2, hy2 - 4 * fk)], [1.0, .7, .3], BONE, 16, "blade",
                sym=True, keep=True)
    # wings from perfect on
    if t >= 3:
        ws = hr * (1.1 if t == 3 else 1.45)
        sx, sy = d.bw * .2, d.by - d.bh * .35
        mat = GLASS if kind != 1 else ACC
        b.E(sx + ws * .55, sy - ws * .5, ws * .65, ws * .42, mat, 2, "wing", sym=True, rot=-.6, flat=True)
        b.E(sx + ws * .45, sy + ws * .2, ws * .45, ws * .3, mat, 1, "wing", sym=True, rot=.4, flat=True)
        if kind == 1:
            b.E(sx + ws * .62, sy - ws * .55, ws * .17, ws * .17, BODY, 3, "eyespot", sym=True, on=("wing",))
    # middle leg pair
    if t >= 1:
        lx, ly = d.bw * .42, d.by + d.bh * .12
        b.C([(lx, ly), (lx + 1.6 + d.m * 1.6, ly + .6), (lx + 2.2 + d.m * 2.2, ly + 2.2 + d.m)], .5 + .15 * d.m,
            DARK, 7, "leg2", sym=True, keep=True)
    markings(b, g, d)
    d.mouth_y = d.hcy + hr * hy * .5
    return d


def planta(b, g, P, t):
    d = skeleton(b, g, P, t, "planta", head_k=1.0, body_k=1.05, limb_k=.9, leg_k=.45, arm_mat=MARK, pear=.35,
                 neck=.68, body_hk=1.1)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    top = d.htop + .8
    kind = g["f1"]
    leaf = MARK
    # petal ring behind the head (flower kinds), grows with the stage
    if kind in (2, 3) and t >= 2:
        n = 6 + (t >= 4) * 2
        R = hr * (1.05 + .12 * t)
        for i in range(n):
            a = 2 * math.pi * i / n + (math.pi / n if kind == 3 else 0)
            b.E(math.cos(a) * R * .82, d.hcy + math.sin(a) * R * .8, hr * .42, hr * .3, ACC, 4, "petal",
                rot=a, line=False)
    if kind == 0 or (kind in (2, 3) and t < 2):     # sprout pair
        L = 2 + 3.2 * fk
        b.C([(0, top + .6), (0, top - L * .4)], .5, leaf, 17, "stem", keep=True)
        b.E(L * .45, top - L * .45, L * .5, L * .24, leaf, 18, "leaf", sym=True, rot=-.5)
    elif kind == 1:                                  # bud on a stem, opens later
        L = 2.5 + 3 * fk
        b.C([(0, top + .6), (s * .8, top - L * .5), (s * .4, top - L)], .55, leaf, 17, "stem", keep=True)
        b.E(-s * 1.6, top - L * .35, L * .35, L * .18, leaf, 18, "leaf", rot=.5 * s)
        r = 1.3 + 1.0 * fk
        b.E(s * .4, top - L - r * .5, r, r * 1.15, ACC, 19, "bud")
    if kind == 2 and t >= 2:                         # leafy crown
        for i, a in enumerate((-.9, -.3, .3, .9)):
            L = 3 + 2.5 * fk
            b.E(math.sin(a) * L * .7, top - math.cos(a) * L * .55, L * .22, L * .5, leaf, 18, "leaf", rot=a)
    if kind == 3 and t >= 2:
        b.E(0, top + .2, hr * .3, hr * .22, ACC, 19, "pistil")
    # leaf arms (the skeleton already drew MARK-coloured arms; add leaf blades on the hands)
    for hx, hy2 in d.hands:
        b.E(hx + .6, hy2 + .3, d.ar * 1.6, d.ar * .9, leaf, 16, "leafhand", sym=True, rot=.6)
    # roots
    if t >= 1:
        for x in (.6, -.6):
            b.P([(d.bw * .3 + x, -1), (d.bw * .3 + x + .8, -1), (d.bw * .3 + x * 2.6, 0)], leaf, 7, "root",
                sym=True, keep=True)
    # seed spots on the belly
    if t >= 2:
        for x, y in ((-.3, -.1), (.25, .15), (-.05, .35)):
            b.E(x * d.bw * .5, d.by + y * d.bh * .5, .45, .45, ACC, 13, "seed", on=("belly",), line=False)
    markings(b, g, d)
    d.mouth_y = d.hcy + hr * hy * .5
    return d


def espirito(b, g, P, t):
    d = skeleton(b, g, P, t, "espirito", legs=False, head_k=1.04, body_k=.95, limb_k=.85)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    # wispy tail replaces the legs: the creature floats
    tl = 2.5 + 5 * d.m
    by1 = d.by + d.bh * .4
    pts = [(0, by1 - 1), (s * d.bw * .15, by1 + tl * .45), (s * d.bw * .45, by1 + tl * .8),
           (s * (d.bw * .5 + tl * .3), by1 + tl * .7)]
    b.C(pts, [d.bw * .45, d.bw * .28, d.bw * .14, .4], BODY, 9, "wisp", keep=True)
    if t >= 4:
        b.C([(0, by1), (-s * d.bw * .35, by1 + tl * .55), (-s * d.bw * .55, by1 + tl * .45)],
            [d.bw * .3, d.bw * .12, .4], BODY, 8, "wisp", keep=True)
    # crest
    L = hr * .8 * fk
    if g["f1"] == 0:     # flame tuft
        for x, h2, mm in ((-1.6, .7, ACC), (1.6, .7, ACC), (0, 1.0, ACC)):
            b.C([(x * .8, d.htop + 1.5), (x + s * .5, d.htop - L * h2 * .6), (x * 1.2 + s * 1.0, d.htop - L * h2)],
                [1.2, .8, .3], mm, 18, "flame", keep=True)
    elif g["f1"] == 1:   # small horns
        b.C([(hr * .45, d.htop + 1.2), (hr * .6, d.htop - L * .5), (hr * .4, d.htop - L * .8)], [1.0, .6, .3],
            BONE, 18, "horn", sym=True, keep=True)
    elif g["f1"] == 2:   # halo
        n = 14
        R = hr * (.6 + .15 * fk)
        ring = [(math.cos(2 * math.pi * i / n) * R, d.htop - 1.5 - .35 * L + math.sin(2 * math.pi * i / n) * R * .3)
                for i in range(n + 1)]
        b.C(ring, .55, ACC, 3, "halo", keep=True)
    else:                # hood
        b.E(0, d.htop + hr * .35, hr * 1.04, hr * hy * .6, MARK, 21, "hood", on=("head",))
        b.P([(-hr * .5, d.htop + 1), (hr * .5, d.htop + 1), (s * hr * .5, d.htop - L)], MARK, 19, "hood",
            keep=True)
    # floating orbs from perfect on
    if t >= 3:
        for x, y, r in ((d.bw * .9 + 1.5, d.hcy + hr * .2, 1.1), (-(d.bw * .9 + 2), d.by - d.bh * .1, .9)):
            b.E(x, y, r * (1 + .2 * (t - 3)), r * (1 + .2 * (t - 3)), ACC, 30, "orb")
    if t >= 2:   # collar ruff
        n = 7
        pts = []
        for i in range(n * 2 + 1):
            x = -d.bw * .55 + d.bw * 1.1 * i / (n * 2)
            y = d.btop + 1.0 + (1.6 + .4 * fk if i % 2 else 0)
            pts.append((x, y))
        pts += [(d.bw * .5, d.btop - .2), (-d.bw * .5, d.btop - .2)]
        b.P(pts, BELLY, 13, "ruff")
    markings(b, g, d)
    d.mouth_y = d.hcy + hr * hy * .5
    return d


def aquatico(b, g, P, t):
    d = skeleton(b, g, P, t, "aquatico", head_k=1.0, body_k=1.05, limb_k=1.0, leg_k=.65, head_w=1.2, neck=.55,
                 pear=.25)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    hx, hcy = d.hw, d.hcy
    if g["f1"] == 0:       # fan fin ears with ribs
        L = 1.6 + 2.6 * fk
        pts = [(hx - 1.2, hcy - 1.6), (hx + L * .9, hcy - L * 1.0), (hx + L * .55, hcy - L * .38),
               (hx + L * 1.1, hcy - L * .15), (hx + L * .5, hcy + L * .12), (hx + L * .75, hcy + L * .5),
               (hx - 1.0, hcy + 1.3)]
        b.P(pts, ACC, 18, "fin", sym=True, keep=True)
    elif g["f1"] == 1:     # frilly gills
        for k, a in enumerate((-.5, 0, .5)):
            L = 1.6 + 2.4 * fk
            b.C([(hx - .8, hcy - .5 + a * 2.4), (hx + L * math.cos(a), hcy - .5 + a * 2.4 - L * .3 + a * L * .6)],
                [.95, .5], ACC, 18, "gill", sym=True, keep=True)
    elif g["f1"] == 2:     # lure
        L = 3 + 4 * fk
        b.C([(0, d.htop + 1.2), (s * L * .3, d.htop - L * .7), (s * L * .75, d.htop - L * .6)], [.6, .45, .4],
            DARK, 17, "lure", keep=True)
        b.E(s * L * .75, d.htop - L * .6 + 1.0, 1.0 + .3 * fk, 1.1 + .3 * fk, GLASS, 18, "lureb")
    else:                  # head dorsal fin
        L = 2.5 + 3 * fk
        b.P([(-1.8, d.htop + 1.5), (1.6, d.htop + 1.8), (s * 2.0, d.htop - L), (-s * .6, d.htop - L * .6)], ACC,
            18, "dorsal")
    # tail + fluke
    tl = 2.5 + 4 * d.m
    p0 = (s * d.bw * .3, d.by + d.bh * .35)
    p1 = (s * (d.bw * .5 + tl * .5), d.by + d.bh * .45)
    p2 = (s * (d.bw * .5 + tl * .95), d.by + d.bh * .05)
    b.C([p0, p1, p2], [d.lr * 1.2, d.lr * .85, d.lr * .5], BODY, 5, "tail")
    F = 1.6 + 2.4 * d.m
    b.P([(p2[0], p2[1] + .4), (p2[0] + s * F * 1.1, p2[1] - F * 1.3), (p2[0] + s * F * .2, p2[1] - .2),
         (p2[0] - s * F * .3, p2[1] - F * 1.4)], ACC, 6, "fluke", keep=True)
    # arm fins
    for hx2, hy2 in d.hands:
        if t >= 2:
            b.P([(hx2 - .3, hy2 - 1.0), (hx2 + 1.0 + 1.4 * fk, hy2 + .2), (hx2, hy2 + 1.0)], ACC, 13, "armfin",
                sym=True, keep=True)
    if t >= 3:      # back spines over the shoulders
        for k in (.25, .55):
            x = d.bw * k
            b.P([(x - 1.0, d.btop + 1.5), (x + 1.0, d.btop + 1.8), (x + .3, d.btop - 1.2 * fk)], ACC, 9, "spine",
                sym=True, keep=True)
    b.E(0, d.hcy + hr * hy * .42, hr * .62, hr * hy * .3, BELLY, 21, "muzzle", on=("head",))
    markings(b, g, d)
    d.mouth_y = d.hcy + hr * hy * .42
    return d


def maquina(b, g, P, t):
    d = skeleton(b, g, P, t, "maquina", boxy=True, head_k=1.0, body_k=1.0, limb_k=.95, leg_k=.95)
    hr, hy, fk, s = d.hr, d.hy, d.fk, d.side
    # face screen: eyes always sit on a light panel
    b.R(-hr * .78, d.hcy - hr * hy * .52, hr * .78, d.hcy + hr * hy * .62, r=hr * .3, mat=GLASS, z=21,
        name="screen", on=("head",), flat=True)
    # chest panel
    b.R(-d.bw * .28, d.by - d.bh * .28, d.bw * .28, d.by + d.bh * .12, r=.8, mat=ACC, z=12, name="panel",
        on=("body",), flat=True)
    # antennae
    L = 2.2 + 3.2 * fk
    if g["f1"] == 0:
        b.C([(0, d.htop + .6), (0, d.htop - L)], .45, DARK, 17, "ant", keep=True)
        b.E(0, d.htop - L, 1.0 + .2 * fk, 1.0 + .2 * fk, ACC, 18, "antb")
    elif g["f1"] == 1:
        b.C([(hr * .45, d.htop + .6), (hr * .55, d.htop - L)], .45, DARK, 17, "ant", sym=True, keep=True)
        b.E(hr * .55, d.htop - L, .9, .9, ACC, 18, "antb", sym=True)
    elif g["f1"] == 2:
        b.E(hr + .4, d.hcy, 1.2 + .5 * fk, 1.6 + .9 * fk, ACC, 18, "bolt", sym=True)
    else:
        b.P([(-1.4, d.htop + 1), (1.4, d.htop + 1), (s * 1.4, d.htop - L), (-s * .4, d.htop - L * .4)], ACC, 18,
            "fin")
    # joints
    for hx, hy2 in d.hands:
        b.E(d.bw * .42, d.by - d.bh * .22, d.ar * 1.15, d.ar * 1.15, MARK, 16, "joint", sym=True)
    if t >= 3:      # shoulder pads
        b.R(d.bw * .25, d.btop - .8, d.bw * .62, d.btop + d.bh * .22, r=1.0, mat=ACC, z=17, name="pad", sym=True)
    if t >= 4:      # back thrusters
        b.R(d.bw * .35, d.btop - 3.5, d.bw * .62, d.btop + 2, r=.8, mat=MARK, z=3, name="jet", sym=True)
        b.E(d.bw * .485, d.btop - 3.8, .9, 1.0, ACC, 4, "flame", sym=True)
    if t >= 2:      # rivets
        b.E(d.bw * .36, d.by + d.bh * .3, .38, .38, MARK, 13, "rivet", sym=True, on=("body",), line=False)
    if g["mark"] in ("stripes", "cap"):
        b.R(-hr, d.htop - 1, hr, d.htop + hr * .32, mat=g["mark_mat"], z=22, name="mk", on=("head",), flat=True)
    d.mouth_y = d.hcy + hr * hy * .36
    return d


FAMILY_FN = dict(draco=draco, fera=fera, ave=ave, inseto=inseto, planta=planta, espirito=espirito,
                 aquatico=aquatico, maquina=maquina)
