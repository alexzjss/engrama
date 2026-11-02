"""Round 2: 14 archetypes x 4 poses each, detail passes, accessories. 28-grid coords (scaled to canvas)."""
import math
import numpy as np
from core import Canvas, V, mkpal, SIZES, OUT

ARCHS = ["slime", "dragon", "beast", "bird", "bug", "plant", "ghost", "fish", "knight",
         "robot", "golem", "winged", "stack", "serpent"]
CHILD_OK = ["slime", "dragon", "beast", "bird", "bug", "plant", "ghost", "fish", "robot", "stack", "serpent"]
BABIES = ["blob", "chick", "ghostlet", "fishling", "bud", "spark"]


# ---------------------------------------------------------------- helpers
def claw(c, x, y, dx, dy, n=3, sp=1.0, ln=1.7, key="bone"):
    L = math.hypot(dx, dy); dx, dy = dx / L, dy / L; nx, ny = -dy, dx
    for i in range(n):
        o = (i - (n - 1) / 2) * sp; bx, by = x + nx * o, y + ny * o
        c.P([(bx - nx * .55, by - ny * .55), (bx + dx * ln, by + dy * ln), (bx + nx * .55, by + ny * .55)], key, line=False)


def fangs(c, x, y, w, n=2, key="white"):
    for i in range(n):
        xx = x - w / 2 + (w * i / max(n - 1, 1))
        c.P([(xx - .5, y), (xx + .5, y), (xx, y + 1.5)], key, line=False)


def headshape(c, cx, cy, rx, ry, key, hd):
    if hd == 0: c.E(cx, cy, rx, ry, key)
    elif hd == 1: c.R(cx - rx, cy - ry * .85, cx + rx, cy + ry * .85, key, r=ry * .55)
    elif hd == 2:
        c.E(cx, cy - ry * .1, rx, ry * .95, key)
        c.P([(cx - rx * .7, cy + ry * .2), (cx + rx * .7, cy + ry * .2), (cx, cy + ry * 1.2)], key, line=False)
    else:
        c.E(cx, cy, rx * .86, ry, key)
        c.E(cx - rx * .72, cy + ry * .35, rx * .42, ry * .5, key, line=False); c.E(cx + rx * .72, cy + ry * .35, rx * .42, ry * .5, key, line=False)


def sprouts(c, x, y):
    c.L(x, y, x, y - 3, 1.2, "leaf"); c.E(x - 2, y - 3, 2.2, 1.3, "leaf", rot=-.5); c.E(x + 2, y - 3, 2.2, 1.3, "leaf", rot=.5)


def horn_set(c, kind, hx, hy, rx, ry, key="bone"):
    top = hy - ry
    if kind == 0:
        c.P([(hx - rx * .6, top + 1), (hx - rx * 1.05, top - 4), (hx - rx * .1, top + .5)], key, mir=True, mx=hx)
    elif kind == 1:
        c.chain([(hx - rx * .8, top + 1.5, 2.2), (hx - rx * 1.3, top + .5, 1.8), (hx - rx * 1.4, top + 3, 1.2)], key, mir=True, mx=hx)
    elif kind == 2:
        c.P([(hx - 1.3, top + 1), (hx, top - 5), (hx + 1.3, top + 1)], key)
        c.P([(hx - rx * .9, top + 1.5), (hx - rx * 1.2, top - 1), (hx - rx * .5, top + 1)], "acc", mir=True, mx=hx)
    elif kind == 3:
        c.E(hx + rx * 1.05, hy - ry * .1, 1.8, 3.2, "acc", mir=True, mx=hx, rot=.25)
    else:
        c.chain([(hx - rx * .5, top + 1, 1.2), (hx - rx * .9, top - 2, 1), (hx - rx * 1.2, top - 4, .8)], key, mir=True, mx=hx)
        c.chain([(hx - rx * .85, top - 1.4, 1), (hx - rx * .3, top - 3, .8)], key, mir=True, mx=hx)


def spines(c, pts, key="acc"):
    for (x, y, d) in pts:
        c.P([(x - 1.2, y), (x + d, y - 2.6), (x + 1.2, y + 1.2)], key, line=True)


# ---------------------------------------------------------------- babies
def baby(c, v):
    kind = v.baby
    rx = 9 + (v.body % 3) * .6; ry = 8 + (v.body // 3) * .8
    if kind == "blob":
        c.E(14, 26 - ry * .8, rx, ry, "body", clip=26)
        sprouts(c, 14, 26 - ry * 1.75) if v.ears % 2 == 0 else c.P([(11, 9), (14, 3), (17, 9)], "acc")
        c.E(9, 14, 1.2, 1.8, "white", paint=True, only="body"); c.E(19, 19, 1.5, 1.5, "body2", paint=True, only="body")
        c.head = (14, 18, rx, ry); c.eyepair(14, 19, 4); c.mouth(14, 22.5, 3)
    elif kind == "chick":
        c.E(14, 18.5, rx, ry, "body"); c.E(14, 21, 5.5, 4.5, "belly", paint=True)
        c.P([(12, 20), (16, 20), (14, 23)], "gold"); c.E(5, 19, 2.2, 3, "body2", mir=True, rot=.4)
        c.P([(12, 11), (14, 5), (16, 11)], "acc") if v.ears % 2 else c.E(14, 10, 1.5, 2.2, "acc")
        c.L(12, 25, 12, 27, 1.4, "gold"); c.L(16, 25, 16, 27, 1.4, "gold"); c.eyepair(14, 17, 4)
    elif kind == "ghostlet":
        c.P([(5, 15), (5, 25), (8, 22.5), (11, 26), (14, 23), (17, 26), (20, 22.5), (23, 25), (23, 15)], "body")
        c.E(14, 15, 9, 9, "body", clip=16); c.E(4, 18, 2, 1.5, "body", mir=True, rot=.4)
        c.P([(14, 3), (11, 8), (17, 8)], "acc") if v.ears % 2 else c.E(14, 5.5, 2, 2, "glow")
        c.eyepair(14, 17, 4); c.mouth(14, 21, 2.4)
    elif kind == "fishling":
        c.E(13, 17, 8.5, 7.5, "body"); c.P([(20, 17), (27, 11), (26, 17), (27, 23)], "acc")
        c.P([(9, 11), (13, 5), (17, 11)], "acc"); c.E(12, 21, 5, 3, "belly", paint=True, only="body")
        c.eye1(9, 16, -1); c.eye1(15, 16, 1); c.E(23, 6, 1.4, 1.4, "white"); c.E(5, 7, 1, 1, "white")
    elif kind == "bud":
        c.E(14, 19.5, 8, 6.8, "belly"); c.E(14, 13, 9.5, 5.2, "leaf", clip=15.5)
        c.R(13, 3, 15, 9, "leaf"); c.E(14, 3.5, 2.6, 2.6, "acc"); c.E(14, 3.5, 1, 1, "gold", line=False)
        c.chain([(14, 12, .7), (14, 15, .7)], "dark", paint=True)
        c.eyepair(14, 19, 3.6); c.mouth(14, 22.5, 2.4)
    else:
        c.E(14, 18.5, 8, 7.8, "body"); c.P([(7, 13), (6, 5), (12, 11)], "body", mir=True); c.P([(8, 12), (7.2, 7), (10.5, 11)], "glow", mir=True, line=False)
        c.E(14, 21, 4.5, 4, "belly", paint=True); c.E(5, 22, 2.3, 1.8, "body2", mir=True)
        c.E(14, 4, 1.2, 1.2, "glow"); c.eyepair(14, 18, 4); c.mouth(14, 22, 2.4)


# ---------------------------------------------------------------- slime
def slime(c, v):
    t = v.t; p = v.pose; w = 9 + v.body % 3; h = 8 + (v.body // 3) * 1.2
    top = 26 - h * 1.8
    if t >= 3:
        c.P([(7, top + 6), (4, top - 2), (11, top + 2)], "glow", mir=True)
        c.P([(12, top + 1), (14, top - 5), (16, top + 1)], "acc")
    ey = 18.5
    if p == 0:
        c.E(14, 26 - h * .8, w, h, "body", clip=26); c.E(5, 25.2, 1.7, 1.8, "body", mir=True, clip=26.5)
        ey = 18.5 - (t >= 3) * 1.5
    elif p == 1:  # droplet
        top = 3; c.E(14, 19, 9, 7.4, "body", clip=26)
        c.P([(7.5, 17), (14, 2), (20.5, 17)], "body", line=False); c.P([(6, 18), (22, 18), (22, 24), (6, 24)], "body", line=False)
        ey = 19
    elif p == 2:  # twin stack
        top = 9; c.E(14, 21, w + 1, 5.5, "body", clip=26); c.E(14, 12.5, 7, 6.2, "body")
        ey = 12.5; c.E(3.5, 23, 1.6, 1.6, "body", mir=True, line=False)
    else:         # jelly with raised tentacle arms
        c.chain([(5.5, 20, 3), (2, 15, 2.6), (3.5, 9.5, 1.8)], "body", mir=True)
        c.E(14, 20.2, w, h * .85, "body", clip=26); top = 26 - h * 1.7; ey = 19
        for x in (8, 14, 20): c.P([(x - 1.5, 25.6), (x, 28), (x + 1.5, 25.6)], "body", line=False)
    if p in (0, 2):
        k = v.ears; ty = top + 1
        if k == 0: sprouts(c, 14, ty)
        elif k == 1: c.L(14, ty, 14, ty - 3, 1, "dark"); c.E(14, ty - 4, 1.8, 1.8, "glow")
        elif k == 2: c.P([(10, ty + 1), (11, ty - 3), (14, ty), (17, ty - 3), (18, ty + 1)], "gold")
        elif k == 3: c.P([(11, ty + 1), (12, ty - 2), (14, ty - 5), (16, ty - 2), (17, ty + 1)], "acc")
        else: c.P([(7, ty + 4), (7, ty - 2), (12, ty + 1)], "body", mir=True)
    if t >= 2 and p != 3: c.E(2.8, 20, 2, 1.8, "body", mir=True)
    c.E(14, 21.5, w * .55, h * .38, "belly", paint=True, only="body")
    c.E(8.5, top + 5, 1.2, 1.8, "white", paint=True); c.E(10.5, top + 3.6, .6, .6, "white", paint=True)
    for (x, y) in ((18, 22), (20.5, 19.5)): c.E(x, y, .9, .9, "white", paint=True, only="body")  # bubbles
    if t >= 3: c.E(14, 21.8, 2.6, 2.6, "glow"); c.E(13.2, 21, .7, .7, "white", line=False)
    c.head = (14, top + 5, w, h); c.eyepair(14, ey, 4); c.mouth(14, ey + 3.6, 3.2)


# ---------------------------------------------------------------- dragon
def dragon(c, v):
    t = v.t; p = v.pose; hd = v.hd; tl = v.tail
    wings = t >= 3
    def tip(x, y, d=1):
        if tl == 0: c.P([(x - 1.5, y + 2), (x + d, y - 4), (x + 2, y + 2)], "acc")
        elif tl == 1: c.P([(x - 1.5, y + 2), (x + d, y - 4), (x + 2, y + 2)], "glow"); c.P([(x - .8, y + 1.5), (x + d, y - 2), (x + 1.2, y + 1.5)], "gold", line=False)
        elif tl == 2: c.E(x, y, 2.6, 2.6, "bone"); c.P([(x - 1, y - 2), (x, y - 4), (x + 1, y - 2)], "bone", line=False)
        else: c.P([(x - 2, y + 2), (x + d, y - 3), (x + 2, y + 1)], "acc2"); c.P([(x - 2, y + 2), (x + 2, y - 1), (x + 3, y + 3)], "acc2")
    if p == 0:  # upright
        if wings:
            c.P([(17, 14), (27.5, 3), (25.5, 9), (27.5, 12), (24, 14.5), (26.5, 18), (17, 19)], "acc")
            c.chain([(17.5, 14, 1.2), (27, 3.5, .9)], "bone", line=False)
            c.P([(10, 14), (4, 8), (5.5, 12), (3.5, 14), (6, 16), (10, 18)], "acc")
        c.chain([(17, 21, 4), (21, 24, 3.2), (25, 21, 2.2), (26.5, 16.5, 1.2)], "body"); tip(26.3, 14.5, 1)
        c.E(10, 25, 3.2, 1.9, "body"); c.E(17.5, 25, 3.2, 1.9, "body"); claw(c, 8, 26, -.6, .8, 3, .9); claw(c, 15.6, 26, -.6, .8, 3, .9)
        c.E(13.5, 19, 6.6, 6.6, "body"); c.E(12.5, 20, 3.8, 5, "belly", paint=True, only="body")
        for y in (17.5, 19.5, 21.5, 23.5): c.R(10, y, 15, y + .5, "body2", paint=True, only="belly")
        c.chain([(9, 17, 2.4), (6.5, 20.5, 1.8)], "body"); claw(c, 5.6, 21.6, -.6, 1, 3, .9)
        c.chain([(18, 17, 2.4), (21, 20, 1.8)], "body"); claw(c, 21.6, 21, .6, 1, 3, .9)
        if t >= 2: spines(c, [(17.5, 13, 2.5), (19.5, 15.5, 2.5), (20.5, 18.5, 2.5)])
        hx, hy = 12, 9.5; horn_set(c, v.ears, hx, hy, 6.2, 5.2)
        headshape(c, hx, hy, 6.2, 5.2, "body", hd); c.E(7.3, 11.5, 3.8, 2.8, "body"); c.E(7.8, 12.8, 3.2, 1.3, "belly", paint=True)
        c.mark(5.2, 10.8); c.head = (hx, hy, 6.2, 5.2); c.neck = (13, 15, 9)
        c.eye1(9.6, 8.6, -1); c.eye1(14.4, 8.6, 1); fangs(c, 7.5, 13.4, 3, 2) if v.g["mouth"] in (1, 2) else None
    elif p == 1:  # crouched quadruped (faces left)
        if wings: c.P([(14, 12), (23, 1), (26, 9), (24, 11), (26, 14), (17, 16)], "acc"); c.chain([(14.5, 12, 1.2), (22.5, 1.5, .9)], "bone", line=False)
        c.chain([(21, 19, 4), (25, 21, 3), (27, 16, 2), (26, 11, 1.2)], "body"); tip(26, 10.5, 0)
        c.R(21, 20, 24, 26, "body2", line=False); c.R(10, 20, 13, 26, "body2", line=False)
        c.E(15.5, 17.5, 9, 6, "body"); c.E(13, 20.2, 6, 3, "belly", paint=True, only="body")
        c.R(18, 19, 21.5, 25.5, "body", line=False, r=1.2); c.R(7.5, 19, 11, 25.5, "body", line=False, r=1.2)
        c.E(8.5, 25.8, 2.5, 1.2, "body"); c.E(19.5, 25.8, 2.5, 1.2, "body")
        claw(c, 6.2, 26.3, -1, .4, 3, .8); claw(c, 17.2, 26.3, -1, .4, 3, .8)
        spines(c, [(11, 12, 2), (14.5, 11.5, 2.5), (18, 12.5, 2.5), (21.5, 14.5, 2.5)])
        hx, hy = 6.5, 13; horn_set(c, v.ears, hx, hy, 5.2, 4.4)
        headshape(c, hx + .5, hy, 5.2, 4.4, "body", hd); c.E(2.8, 14.8, 3.3, 2.5, "body"); c.E(3.2, 16.2, 2.8, 1.1, "belly", paint=True)
        c.mark(1, 14.2); c.head = (hx, hy, 5.2, 4.4); c.neck = (10, 17, 8)
        c.eye1(7, 12, -1); fangs(c, 3.8, 16.6, 2.6, 2) if v.g["mouth"] in (1, 2) else None
    elif p == 2:  # serpentine neck, long tail
        if wings: c.P([(16, 15), (25, 5), (26, 12), (22, 16)], "acc"); c.chain([(16.5, 15, 1), (24.5, 5.5, .8)], "bone", line=False)
        c.chain([(18, 22, 4), (23, 24.5, 3), (27, 22, 1.8)], "body"); tip(27, 20.5, 1) if False else None
        c.E(11, 25.2, 2.8, 1.5, "body"); c.E(19, 25.2, 2.8, 1.5, "body"); claw(c, 9.3, 26, -.5, .8, 3, .8); claw(c, 17.3, 26, -.5, .8, 3, .8)
        c.E(15, 21, 6.4, 5.2, "body"); c.E(14.5, 22.5, 3.6, 3.4, "belly", paint=True, only="body")
        c.chain([(14, 18, 4.2), (10.5, 13.5, 3.4), (12.5, 8.5, 3)], "body")
        c.chain([(14, 18, 2), (10.5, 13.5, 1.6), (12.5, 8.5, 1.3)], "belly", paint=True, only="body")
        c.chain([(14.2, 20, 1), (11, 15, .8)], "body2", paint=True, only="body")
        hx, hy = 11, 5; horn_set(c, v.ears, hx, hy, 4.2, 3.6)
        headshape(c, hx, hy, 4.4, 3.7, "body", hd); c.E(6.8, 6.3, 3, 2.1, "body"); c.mark(4.6, 5.8)
        c.head = (hx, hy, 4.4, 3.7); c.neck = (12, 10, 7); c.eye1(9.2, 4.5, -1); c.eye1(13, 4.5, 1)
        spines(c, [(15, 16, 2), (12.8, 11, 2), (14.8, 6.5, 1.5)]) if t >= 2 else None
    else:  # bulky brute
        if wings: c.P([(20, 12), (27.5, 3), (26, 10), (27.5, 14), (21, 17)], "acc"); c.P([(8, 12), (.5, 3), (2, 10), (.5, 14), (7, 17)], "acc")
        c.chain([(18, 22, 5), (23, 24, 3.4), (26, 22.5, 2)], "body")
        c.E(9.5, 25, 3.8, 2, "body"); c.E(18.5, 25, 3.8, 2, "body"); claw(c, 7.5, 26.2, -.5, .8, 3, 1); claw(c, 16.5, 26.2, -.5, .8, 3, 1)
        c.E(14, 17.5, 9, 7.6, "body"); c.E(14, 19.5, 5.2, 5.4, "belly", paint=True, only="body")
        for y in (16.5, 18.5, 20.5, 22.5): c.R(10, y, 18, y + .6, "body2", paint=True, only="belly")
        c.E(4.5, 17.5, 3.4, 5, "body", mir=True); claw(c, 3.5, 22, -.2, 1, 3, 1.1); claw(c, 24.5, 22, .2, 1, 3, 1.1)
        c.E(6.2, 11.5, 3.5, 3.2, "acc", mir=True)
        hx, hy = 14, 8; horn_set(c, v.ears, hx, hy, 5.4, 4.4)
        headshape(c, hx, hy, 5.6, 4.5, "body", hd); c.E(14, 10.5, 3.6, 2.3, "belly", paint=True)
        c.head = (hx, hy, 5.6, 4.5); c.neck = (14, 12.5, 9); c.eyepair(14, 7.4, 3.2); c.mouth(14, 11.6, 4.5)
        spines(c, [(9, 6, -2.5), (19, 6, 2.5)]) if t >= 2 else None


# ---------------------------------------------------------------- beast
def beast(c, v):
    t = v.t; p = v.pose; tl = v.tail; hd = v.hd
    def ears(hx, hy, rx, ry, sx=1):
        k = v.ears; top = hy - ry
        if k == 0: c.P([(hx - rx * .85, top + 1.2), (hx - rx * .6, top - 4.5), (hx - rx * .05, top + .4)], "body", mir=True, mx=hx); c.P([(hx - rx * .7, top + .8), (hx - rx * .6, top - 2.2), (hx - rx * .3, top + .5)], "acc", mir=True, mx=hx, line=False)
        elif k == 1: c.E(hx - rx * .75, top + .8, 2.4, 2.4, "body", mir=True, mx=hx); c.E(hx - rx * .75, top + .8, 1.2, 1.2, "acc", mir=True, mx=hx, line=False)
        elif k == 2: c.chain([(hx - rx * .5, top + 1, 2.6), (hx - rx * .75, top - 5, 1.9)], "body", mir=True, mx=hx)
        elif k == 3: c.P([(hx - 1, top + 1), (hx, top - 5.5), (hx + 1, top + 1)], "bone"); c.E(hx - rx * .85, top + 2, 2, 2.3, "body2", mir=True, mx=hx)
        else: c.E(hx - rx * 1.05, hy + ry * .3, 2.3, 4.4, "body2", mir=True, mx=hx, rot=.2)
    def tail(x, y, up=1):
        if tl == 0: c.E(x + 2.5, y - 4 * up, 4.4, 2.5, "body", rot=-1.0 * up); c.E(x + 4, y - 7 * up, 1.8, 2, "belly", rot=-1.0 * up)
        elif tl == 1: c.chain([(x, y, 2.6), (x + 3.5, y - 3 * up, 2), (x + 5, y - 8.5 * up, 1.2)], "body"); c.P([(x + 3.4, y - 8.5 * up), (x + 5, y - 12 * up), (x + 6.5, y - 8.5 * up)], "acc")
        elif tl == 2: c.chain([(x, y + 1, 2.8), (x + 4, y + 2.5, 2.4), (x + 5, y - 2 * up, 1.8), (x + 2.5, y - 4 * up, 1.6)], "body")
        else:
            for k in range(3 if t >= 3 else 2):
                c.chain([(x, y - .5 + k, 2.2), (x + 3, y - 3.5 * up + k * 2, 1.6), (x + 5, y - 8 * up + k * 4, 1.0)], "body" if k == 1 else "body2")
    if p == 0:  # standing side view
        tail(22, 16.5)
        c.R(11.5, 19, 14.5, 26, "body2", line=False); c.R(21, 19, 24, 26, "body2", line=False)
        c.E(15.5, 16.5, 9.6, 5.8, "body"); c.E(20.5, 18, 4.6, 4.8, "body", line=False)
        c.E(11, 19.5, 5.5, 3, "belly", paint=True, only="body")
        c.R(7.5, 18, 11.2, 25.5, "body", line=False, r=1); c.R(17.5, 19, 21.2, 25.5, "body", line=False, r=1)
        c.R(7.5, 24.6, 11.8, 26.4, "belly", r=.8); c.R(17.5, 24.6, 21.8, 26.4, "belly", r=.8)
        claw(c, 6.8, 26.2, -1, .3, 3, .8); claw(c, 16.8, 26.2, -1, .3, 3, .8)
        hx, hy = 7.5, 10.5; ears(hx + 1, hy, 5.9, 5.1)
        headshape(c, hx + 1, hy + .5, 5.9, 5.1, "body", hd); c.E(3.4, 12.8, 3.2, 2.4, "belly"); c.mark(1.2, 12)
        if t >= 3: c.P([(10, 6), (12, 1.5), (14, 8)], "acc"); c.P([(12.5, 7), (15.5, 3.5), (16.5, 9.5)], "acc"); c.P([(9, 14.5), (11, 17.5), (14, 13)], "acc")
        c.head = (hx, hy, 5.9, 5.1); c.neck = (11, 14, 8); c.eye1(7.4, 9.7, -1)
        c.mouth(4, 14.8, 2.6)
    elif p == 1:  # sitting, front view
        tail(19, 23, 1)
        c.E(7.5, 23.5, 3.8, 3, "body", mir=True)
        c.E(14, 18.5, 6.6, 7.6, "body"); c.E(14, 20, 4, 5.5, "belly", paint=True, only="body")
        c.R(10.2, 19, 12.8, 25.5, "body", mir=True, r=1.1); c.E(11.5, 25.6, 2.2, 1.1, "belly", mir=True); claw(c, 11.5, 26.3, 0, 1, 3, .8) if False else None
        hx, hy = 14, 9.5; ears(hx, hy, 6.2, 5.3)
        headshape(c, hx, hy, 6.4, 5.4, "body", hd); c.E(14, 12.2, 3.2, 2.2, "belly"); c.mark(14, 11.2)
        if t >= 3: c.chain([(7, 12, 2.5), (6, 16, 2)], "acc", mir=True); c.P([(9, 15), (14, 19), (19, 15), (14, 16)], "acc", line=False) if False else None
        c.head = (hx, hy, 6.4, 5.4); c.neck = (14, 14.5, 9); c.eyepair(14, 9, 3.2); c.mouth(14, 13.7, 3)
    elif p == 2:  # prowling low
        tail(24, 14, 1)
        c.chain([(22, 18, 2.4), (24, 22, 2.2), (25.5, 25, 2)], "body2", line=False)
        c.R(12, 18, 14.6, 25.8, "body2", line=False)
        c.E(16, 15.5, 9.8, 4.8, "body"); c.E(13, 18.3, 6, 2.2, "belly", paint=True, only="body")
        c.chain([(19, 17, 3.6), (20, 21.5, 3), (22, 25, 2.4)], "body", line=False); c.chain([(8.5, 17, 3.2), (7.5, 22, 2.6), (5.5, 25.4, 2.2)], "body", line=False)
        c.E(21.8, 25.6, 2.4, 1.1, "belly"); c.E(5.2, 25.6, 2.4, 1.1, "belly"); claw(c, 3.2, 26.2, -1, .3, 3, .8)
        hx, hy = 6, 13.5; ears(hx + 1, hy, 5.1, 4.4)
        headshape(c, hx + 1, hy, 5.2, 4.4, "body", hd); c.E(2.6, 15, 3, 2.1, "belly"); c.mark(.6, 14.5)
        spines(c, [(11, 10.5, 2), (14.5, 10.5, 2.5), (18, 11, 2.5), (21, 12.5, 2.5)], "acc") if t >= 2 else None
        c.head = (hx, hy, 5.2, 4.4); c.neck = (10, 16, 8); c.eye1(6.5, 12.5, -1); fangs(c, 3.6, 16.3, 2.6, 2) if v.g["mouth"] in (1, 2) else None
    else:  # beastman upright
        tail(19.5, 20, 1)
        c.chain([(11, 20, 4.2), (9.5, 24, 3)], "body"); c.chain([(17, 20, 4.2), (18.5, 24, 3)], "body")
        c.E(9, 25.7, 3, 1.2, "belly"); c.E(19.5, 25.7, 3, 1.2, "belly"); claw(c, 7.5, 26.4, -.5, 1, 3, .9); claw(c, 21, 26.4, .5, 1, 3, .9)
        c.E(14, 17, 6.4, 6.4, "body"); c.E(14, 18, 3.8, 4.6, "belly", paint=True, only="body")
        c.chain([(8.5, 14.5, 3.2), (5, 18.5, 2.6)], "body", mir=True); claw(c, 4.2, 19.6, -.5, 1, 3, 1) ; claw(c, 23.8, 19.6, .5, 1, 3, 1)
        hx, hy = 14, 8; ears(hx, hy, 5.2, 4.6)
        headshape(c, hx, hy, 5.2, 4.6, "body", hd); c.E(14, 10.7, 3.2, 2.3, "belly"); c.mark(14, 10)
        if t >= 3: c.E(7, 12.5, 2.8, 2.2, "acc", mir=True)
        c.head = (hx, hy, 5.2, 4.6); c.neck = (14, 12.5, 8); c.eyepair(14, 7.5, 2.9); c.mouth(14, 12, 3)


# ---------------------------------------------------------------- bird
def bird(c, v):
    t = v.t; p = v.pose; k = v.ears; hd = v.hd
    def crest(hx, top):
        if k == 0: c.P([(hx - 1, top + 1), (hx - 2.5, top - 4.5), (hx, top)], "acc"); c.P([(hx, top + 1), (hx, top - 5.5), (hx + 1.8, top)], "acc2"); c.P([(hx + 1, top + 1), (hx + 3.5, top - 3.5), (hx + 2.5, top + 1)], "acc")
        elif k == 1: c.E(hx, top + .5, 2, 2.3, "acc")
        elif k == 2: c.P([(hx - 4, top + 3), (hx, top - 4.5), (hx + 4, top + 3)], "acc")
        elif k == 3: c.E(hx - 2, top + .5, 1.8, 1.8, "red"); c.E(hx, top - .2, 2, 2, "red"); c.E(hx + 2, top + .5, 1.7, 1.7, "red")
        else: c.P([(hx - 4, top + 3), (hx - 6, top - 2), (hx - 2, top + 1)], "body2", mir=True, mx=hx)
    def feathers(x, y, w, n=3, key="body2"):
        for i in range(n): c.P([(x - w / 2, y + i * 2.2), (x + w / 2, y + i * 2.2), (x, y + i * 2.2 + 2.4)], key, line=False, paint=False)
    if p == 0:  # standing front
        if t >= 3: c.P([(11, 22), (14, 28), (17, 22)], "acc"); c.P([(8, 21), (5, 28), (12, 23)], "acc2"); c.P([(20, 21), (23, 28), (16, 23)], "acc2")
        else: c.P([(10, 22), (14, 27.5), (18, 22)], "acc")
        wl = 4 if t < 3 else 6
        c.P([(7.5, 13), (7.5 - wl, 15 - (t >= 3) * 6), (7.5 - wl, 21 + (t >= 3) * 2), (9, 21)], "acc", mir=True)
        c.E(14, 18, 7.4, 7.6, "body"); c.E(14, 20, 4.8, 5.4, "belly", paint=True, only="body")
        feathers(14, 16, 3.5, 3, "belly") if False else None
        c.E(14, 11, 6.2, 5.6, "body"); crest(14, 5.4)
        c.P([(11.8, 12.5), (16.2, 12.5), (14, 16)], "gold"); c.P([(12.3, 12.6), (15.7, 12.6), (14, 13.4)], "gold", line=False)
        c.L(12, 24.5, 12, 26.6, 1.5, "gold"); c.L(16, 24.5, 16, 26.6, 1.5, "gold"); claw(c, 11, 26.5, -.6, .6, 3, .7, 1.2, "gold"); claw(c, 17, 26.5, .6, .6, 3, .7, 1.2, "gold")
        c.head = (14, 11, 6.2, 5.6); c.neck = (14, 16, 8); c.eyepair(14, 10, 3.9)
    elif p == 1:  # perched side
        c.R(1, 24, 27, 26, "wood", r=.8); c.E(24, 24, 2, .8, "leaf", line=False)
        c.P([(15, 18), (26, 25), (24, 27.5), (14, 22)], "acc"); c.P([(14, 20), (23, 27), (20, 27.5)], "acc2", line=False)
        c.E(14, 17.5, 7, 6, "body", rot=.3); c.E(11.5, 19.5, 4.5, 3.5, "belly", paint=True, only="body")
        c.E(15.5, 17, 5, 3.4, "acc", rot=.4); c.P([(12, 17), (14, 21), (19, 20)], "acc2", line=False)
        c.E(8.5, 11, 5, 4.6, "body"); crest(8.5, 6.5)
        c.P([(4.5, 9.8), (1, 12), (4.5, 13.5)], "gold"); c.P([(4.5, 11.6), (1.5, 12), (4.5, 12.8)], "gold", line=False)
        c.L(11.5, 22, 11.5, 24.3, 1.4, "gold"); c.L(15.5, 22, 15.5, 24.3, 1.4, "gold"); claw(c, 10.4, 24.4, -.6, .5, 3, .7, 1.2, "gold")
        c.head = (8.5, 11, 5, 4.6); c.neck = (11, 15, 7); c.eye1(7.2, 10, -1)
    elif p == 2:  # wings up
        c.P([(11, 22), (14, 28), (17, 22)], "acc")
        c.P([(9, 16), (1.5, 1.5), (3.5, 12), (1.5, 14), (5, 16.5), (3, 21), (9, 21)], "acc", mir=True)
        c.P([(8.5, 15), (3, 5), (6, 14)], "acc2", mir=True, line=False)
        c.E(14, 18.5, 6.4, 6.8, "body"); c.E(14, 20.5, 4.2, 4.8, "belly", paint=True, only="body")
        c.E(14, 11.5, 5.2, 4.8, "body"); crest(14, 6.7)
        c.P([(12, 13), (16, 13), (14, 16.4)], "gold")
        c.L(12, 24.5, 12, 26.6, 1.5, "gold"); c.L(16, 24.5, 16, 26.6, 1.5, "gold"); claw(c, 11, 26.5, -.6, .6, 3, .7, 1.2, "gold"); claw(c, 17, 26.5, .6, .6, 3, .7, 1.2, "gold")
        c.head = (14, 11.5, 5.2, 4.8); c.neck = (14, 16, 8); c.eyepair(14, 10.5, 3.3)
    else:  # long-legged heron
        c.P([(17, 14), (24, 12), (27, 18), (19, 19)], "acc"); c.P([(19, 14.5), (25, 14), (22, 18)], "acc2", line=False)
        c.chain([(12.5, 18, 1.4), (12.5, 26, 1.2)], "gold"); c.chain([(16.5, 18, 1.4), (16.5, 26, 1.2)], "gold")
        claw(c, 11.5, 26.5, -.7, .5, 3, .8, 1.5, "gold"); claw(c, 17.5, 26.5, .7, .5, 3, .8, 1.5, "gold")
        c.E(14.5, 15, 6.2, 4.8, "body"); c.E(13.5, 16.5, 4, 3, "belly", paint=True, only="body")
        c.chain([(11, 13, 3), (8, 8.5, 2.4), (9, 4.5, 2.2)], "body"); c.chain([(11, 13, 1.4), (8, 8.5, 1.1)], "belly", paint=True, only="body")
        c.E(9.2, 3.6, 3.2, 2.8, "body"); crest(9.5, 1.8) if k in (0, 2, 4) else None
        c.P([(6.5, 2.8), (.5, 4.2), (6.5, 5.6)], "gold"); c.P([(6.4, 3.7), (2, 4.2), (6.4, 4.8)], "gold", line=False)
        c.head = (9.2, 3.6, 3.2, 2.8); c.neck = (10, 9, 5); c.eye1(9, 3.2, -1, big=False)


# ---------------------------------------------------------------- bug
def bug(c, v):
    t = v.t; p = v.pose; k = v.ears
    if p == 0:  # beetle
        for y0, y1, x1 in ((17, 15.5, 4), (20, 21.5, 3), (22.5, 25.5, 5.5)):
            c.L(9, y0, x1, y1, 1.4, "dark", mir=True, line=False)
        c.E(14, 18, 8.4, 7.6, "body"); c.R(13.5, 11, 14.5, 25, "dark", paint=True, only="body")
        c.E(14, 9.5, 4.7, 3.8, "body2")
        if k in (0, 3): c.P([(12.5, 7), (14, 0.5 if t >= 3 else 2.5), (15.5, 7)], "bone")
        elif k == 1: c.chain([(12, 6.5, 1), (10, 2.5, 1)], "dark", mir=True); c.E(10, 2.2, 1.3, 1.3, "glow", mir=True)
        elif k == 2: c.chain([(11, 7.5, 2), (7, 4, 1.6), (6, 7, 1)], "bone", mir=True)
        else: c.E(10, 6.5, 1.6, 2.4, "leaf", mir=True, rot=.4)
        c.P([(10.5, 11), (8, 10), (10.8, 12.8)], "bone", mir=True)
        c.head = (14, 9.5, 4.7, 3.8); c.eyepair(14, 9.4, 2.8, big=False)
        if t >= 2: c.P([(6, 14), (3, 9), (8.5, 12)], "acc", mir=True)
        c.E(8.5, 15, 1.7, 1.7, "glow", paint=True, only="body"); c.E(19.5, 17, 1.7, 1.7, "glow", paint=True, only="body"); c.E(10, 21, 1.4, 1.4, "glow", paint=True, only="body")
    elif p == 1:  # butterfly
        c.P([(13, 13), (2, 2.5), (0.5, 12), (11, 17)], "acc", mir=True); c.P([(13, 16), (3, 18), (4.5, 25.5), (13, 22)], "acc2", mir=True)
        c.E(6, 8, 2, 2, "white", paint=True, mir=True); c.E(7, 21, 1.6, 1.6, "white", paint=True, mir=True); c.E(4, 12, 1.2, 1.2, "dark", paint=True, mir=True)
        c.chain([(11, 13, .8), (3.5, 4.5, .8)], "dark", paint=True, mir=True); c.chain([(11, 16, .8), (5, 22, .8)], "dark", paint=True, mir=True)
        c.E(14, 16.5, 2.4, 8, "body"); c.E(14, 8.5, 3.5, 3.3, "body2")
        c.chain([(13, 6, .7), (10.5, 2, .7)], "dark", mir=True, line=False); c.E(10.5, 1.8, 1, 1, "gold", mir=True)
        c.head = (14, 8.5, 3.5, 3.3); c.eyepair(14, 8.6, 1.6, big=False)
    elif p == 2:  # wasp
        c.P([(11, 12), (4, 6), (3, 12), (10, 15)], "white", mir=True, line=True)
        for y0, y1, x1 in ((15, 13.5, 8), (17, 18, 7.5), (19, 22, 8.5)): c.L(12, y0, x1, y1, 1.3, "dark", mir=True, line=False)
        c.E(14, 21, 5, 5.4, "body"); c.R(9, 20, 19, 21.5, "dark", paint=True, only="body"); c.R(9, 23, 19, 24.3, "dark", paint=True, only="body")
        c.P([(12, 25.5), (14, 28), (16, 25.5)], "dark")
        c.E(14, 14.5, 3.9, 3.3, "body2"); c.E(14, 9, 4.4, 3.8, "body")
        c.chain([(12.5, 6, .8), (10, 1.5, .8)], "dark", mir=True, line=False); c.E(14, 18, 2.2, 1.5, "body2")
        c.P([(11.5, 11.5), (14, 13.5), (16.5, 11.5)], "bone"); c.head = (14, 9, 4.4, 3.8); c.eyepair(14, 9, 2.6, big=False)
    else:  # scorpion
        for x0, y0, x1, y1 in ((9, 20, 3, 22), (9, 22, 4, 26), (19, 20, 25, 22), (19, 22, 24, 26)):
            c.L(x0, y0, x1, y1, 1.4, "dark", line=False)
        c.chain([(19, 20, 3.2), (24, 17, 2.8), (25, 11, 2.4), (21, 6.5, 2)], "body"); c.P([(19.5, 6.5), (16.5, 8.5), (19.5, 9)], "acc"); c.E(21, 7, 1.8, 1.8, "acc")
        c.E(14, 21, 7.5, 4.8, "body"); c.R(10, 19, 10.6, 24, "body2", paint=True); c.R(14, 18, 14.6, 25, "body2", paint=True); c.R(18, 19, 18.6, 24, "body2", paint=True)
        c.chain([(8, 16, 2), (4, 12, 1.8), (6, 8, 1.8)], "body", mir=False); c.chain([(20, 16, 2), (24, 12, 1.8)], "body") if False else None
        c.E(5.5, 6.5, 3, 3, "acc"); c.P([(4, 8), (6.5, 9), (7, 4)], "acc", line=False)
        c.chain([(20, 16, 2), (24, 12, 1.8), (22, 8.5, 1.8)], "body") if False else None
        c.E(14, 15.5, 5, 3.6, "body2")
        c.head = (14, 15.5, 5, 3.6); c.eyepair(14, 15, 2.2, big=False)


# ---------------------------------------------------------------- plant
def plant(c, v):
    t = v.t; p = v.pose; k = v.ears
    if p == 0:  # flower
        c.L(14, 15, 14, 24, 3.2, "leaf"); c.P([(12, 22), (4, 18), (3, 23), (12, 24)], "leaf", mir=True)
        c.chain([(11.5, 22.5, .6), (5, 20, .6)], "dark", paint=True, mir=True)
        c.E(11.5, 25.5, 2.4, 1.5, "wood", mir=True)
        n = 8 if t < 3 else 10
        for i in range(n):
            a = i * 2 * math.pi / n; c.E(14 + 6.3 * math.cos(a), 10 + 5.7 * math.sin(a), 2.8, 2.8, "acc")
        if t >= 3:
            for i in range(6):
                a = i * 2 * math.pi / 6 + .5; c.E(14 + 4.6 * math.cos(a), 10 + 4.2 * math.sin(a), 2.2, 2.2, "acc2")
        c.E(14, 10, 4.8, 4.5, "belly"); c.head = (14, 10, 6, 6); c.eyepair(14, 10, 2.2); c.mouth(14, 12.8, 2.4)
    elif p == 1:  # mushroom
        c.E(14, 20.5, 5.5, 6, "belly"); c.E(11.5, 25.7, 2.6, 1.3, "wood", mir=True)
        c.E(14, 10.5, 11.5, 7.5, "acc", clip=14); c.R(2.5, 13.2, 25.5, 15, "belly", r=.8)
        for x in range(4, 25, 2): c.R(x, 14.9, x + .5, 16.2, "body2", line=False)
        c.E(9, 9, 2, 1.8, "white", paint=True, only="acc"); c.E(17.5, 7.5, 1.6, 1.6, "white", paint=True, only="acc"); c.E(21, 11.5, 1.3, 1.3, "white", paint=True, only="acc")
        if t >= 4: c.E(14, 2.5, 2.2, 1.8, "acc2"); c.R(13.2, 3.5, 14.8, 5, "belly")
        c.E(3.5, 19, 2, 1.6, "belly", mir=True) if t >= 2 else None
        c.head = (14, 10, 10, 6); c.eyepair(14, 19, 2.6); c.mouth(14, 22.5, 2.4)
    elif p == 2:  # cactus
        c.R(8.5, 6, 19.5, 24, "leaf", r=4)
        c.chain([(8.5, 16, 3), (4, 16, 3), (3.5, 10.5, 3)], "leaf"); c.chain([(19.5, 14, 3), (24, 14, 3), (24.5, 9, 3)], "leaf") if t >= 2 else None
        c.E(14, 5.5, 3.2, 2.6, "acc"); c.E(14, 5.2, 1.2, 1, "gold", line=False)
        for x in (10.5, 13, 15.5, 18): c.R(x, 7, x + .4, 22, "body2", paint=True, only="leaf") if False else None
        c.R(9, 22.5, 19, 26.5, "wood", r=1)
        c.R(11, 11, 12, 12, "bone", paint=True); c.R(17, 18, 18, 19, "bone", paint=True); c.R(10.5, 16, 11.5, 17, "bone", paint=True)
        c.head = (14, 12, 5, 6); c.eyepair(14, 14, 2.6)
    else:  # tree ent
        c.chain([(10, 22, 3), (8, 26, 2.4)], "wood", mir=True); c.E(7, 26.2, 3, 1, "wood", mir=True)
        c.chain([(9, 14, 3), (4, 10, 2.4), (2.5, 5, 2)], "wood", mir=True)
        for x, y in ((2, 4), (3.5, 7)): c.E(x, y, 2.6, 2, "leaf", mir=True)
        c.E(14, 18, 6.4, 8.4, "wood"); c.chain([(10, 12, .6), (11, 18, .6), (10, 23, .6)], "dark", paint=True)
        c.E(14, 7, 8.8, 6.2, "leaf"); c.E(7.5, 8.5, 4, 3.4, "leaf"); c.E(20.5, 8.5, 4, 3.4, "leaf"); c.E(14, 3.5, 5.5, 3, "leaf")
        c.E(14, 3, 1.6, 1.6, "acc"); c.E(8, 5, 1.4, 1.4, "acc"); c.E(20, 5, 1.4, 1.4, "acc")
        c.chain([(8, 8, .5), (12, 5, .5)], "dark", paint=True, only="leaf"); c.chain([(16, 5, .5), (20, 8, .5)], "dark", paint=True, only="leaf")
        c.head = (14, 12, 6, 4); c.eyepair(14, 15, 2.5); c.mouth(14, 19.5, 3)


# ---------------------------------------------------------------- ghost
def ghost(c, v):
    t = v.t; p = v.pose; k = v.ears
    if p == 1:  # flame spirit
        c.P([(14, 1), (19, 8), (22, 14), (22, 21), (18, 25.5), (10, 25.5), (6, 21), (6, 14), (9, 8)], "acc")
        c.P([(14, 8), (18, 14), (18.5, 20), (15, 24), (10.5, 22), (9.5, 16)], "glow", line=False)
        c.E(14, 18.5, 5, 5.5, "gold", line=False); c.E(3.5, 18, 1.8, 1.4, "acc", mir=True, rot=.4)
        c.head = (14, 12, 6, 6); c.eyepair(14, 17.5, 2.8); c.mouth(14, 21.4, 2.4)
    elif p == 2:  # reaper cloak with hood, scythe
        c.L(24.5, 26, 24.5, 2, 1.1, "wood"); c.P([(24.5, 2), (19, 1), (20.5, 4.5), (24.5, 4)], "metal")
        c.P([(14, 3), (21, 8), (23, 25.5), (19, 23), (16, 26.5), (13, 23.5), (10, 26.5), (7, 23), (5, 25.5), (7, 8)], "dark")
        c.E(14, 10, 6.8, 6.8, "dark"); c.E(14, 11, 4.8, 4.6, "glow", line=False) if False else None
        c.E(14, 11.5, 4.6, 4.2, "ice", line=False); c.E(14, 11, 4.3, 3.6, "dark", line=False, clip=None) if False else None
        c.E(4.5, 18, 1.4, 1.4, "bone", mir=False); c.E(23, 18, 1.4, 1.4, "bone") if False else None
        c.E(14, 17, 3, 1.6, "acc", paint=False) if t >= 3 else None
        c.head = (14, 10, 6.8, 6.8); c.eyekind = "led"; c.eyepair(14, 11.5, 2.2)
    elif p == 3:  # lantern orb
        c.chain([(14, 1, .8), (14, 6, .8)], "wood"); c.E(14, 1.6, 2.4, 1.2, "gold")
        c.P([(8, 20), (20, 20), (24, 26), (4, 26)], "dark"); c.E(8, 22.5, 1.8, 1.4, "bone", mir=True)
        c.E(14, 13, 8.5, 8, "glow"); c.E(14, 13, 6.6, 6.2, "gold", line=False); c.R(5.5, 18, 22.5, 19.3, "dark", line=False)
        c.R(13.4, 6.5, 14.6, 20, "dark", line=False) if False else None
        c.head = (14, 13, 8, 8); c.eyekind = "cute"; c.eyepair(14, 13.5, 3.2); c.mouth(14, 16.5, 3)
    else:  # classic sheet
        if k == 3 and t >= 2: c.E(14, 12, 10.5, 10, "dark", clip=22)
        c.P([(5, 15), (5, 25.5), (8, 22.8), (11, 26.5), (14, 23), (17, 26.5), (20, 22.8), (23, 25.5), (23, 15)], "body")
        c.E(14, 14.5, 9, 9.5, "body", clip=16); c.E(4, 19, 2.1, 1.5, "body", mir=True, rot=.5)
        c.chain([(8, 18, .7), (8.5, 24, .7)], "belly", paint=True, only="body"); c.chain([(20, 18, .7), (19.5, 24, .7)], "belly", paint=True, only="body")
        if k == 1 and t >= 2: c.E(14, 5.5, 8.5, 1.8, "dark"); c.P([(9.5, 5), (14, -.5), (18.5, 5)], "dark")
        elif k == 2: c.P([(8, 7), (6, 2.5), (11, 5.5)], "bone", mir=True)
        elif k == 4: c.P([(10, 6), (14, -1), (18, 6)], "acc"); c.P([(12, 6), (14, 2), (16, 6)], "gold", line=False)
        elif k == 0: c.E(14, 5, 1.8, 1.8, "glow")
        c.head = (14, 12, 8, 7); c.eyepair(14, 14, 3.6); c.mouth(14, 18, 3.6)
        if t >= 3: c.P([(23, 11), (25.5, 3), (26.5, 25)], "wood")
        if t >= 4: c.E(3, 5, 1.6, 1.6, "acc2"); c.E(25, 8, 1.6, 1.6, "acc2")


# ---------------------------------------------------------------- fish
def fish(c, v):
    t = v.t; p = v.pose; k = v.ears
    if p == 0:
        c.P([(21, 15), (27.5, 8.5), (26, 15.5), (27.5, 22)], "acc"); c.chain([(21.5, 15, .5), (27, 9, .5)], "dark", paint=True); c.chain([(21.5, 15.5, .5), (26.5, 21.5, .5)], "dark", paint=True)
        c.P([(9, 10), (14, 3 if t < 3 else 1), (19, 10)], "acc")
        c.E(13, 15.5, 10, 7, "body"); c.E(12.5, 19.3, 8.5, 3, "belly", paint=True, only="body")
        for i in range(4): c.E(11 + i * 2.3, 14 + (i % 2), 1.3, 1.1, "body2", paint=True, only="body")
        c.P([(12, 17), (16, 22), (10.5, 21)], "glow"); c.E(10, 25, 2, 1.5, "acc"); c.E(17, 25, 2, 1.5, "acc")
        c.E(4.7, 18.5, 1.6, .7, "red"); c.R(7.5, 11, 8.1, 20, "body2", paint=True, only="body")
        c.head = (8, 14, 5, 5); c.eye1(7.5, 13, -1); c.E(25, 4, 1.5, 1.5, "white"); c.E(3, 6, 1.1, 1.1, "white")
        if t >= 3: c.P([(11, 8), (13, 1), (15, 8)], "glow")
    elif p == 1:  # shark
        c.P([(19, 20), (27, 15), (25, 22), (27, 27)], "acc"); c.P([(10, 8), (14, 0.5), (18, 8)], "body2")
        c.E(14, 17, 8, 8.5, "body"); c.E(14, 20.5, 5.8, 5, "belly", paint=True, only="body")
        c.P([(8, 20), (3, 25), (8.5, 24)], "body2", mir=True); c.E(10, 26, 2.4, 1.4, "body2", mir=True)
        for i in range(4): c.P([(9.5 + i * 3, 19.5), (11 + i * 3, 19.5), (10.3 + i * 3, 21.8)], "white", line=False)
        for i in range(3): c.R(8 + i * 5, 12, 9 + i * 5, 14, "body2", paint=True) if False else None
        c.head = (14, 13, 7, 6); c.eyepair(14, 13, 3.6)
    elif p == 2:  # jelly
        for i, x in enumerate((7, 11, 17, 21)):
            c.chain([(x, 14, 2.2), (x + (1.6 if i % 2 else -1.6), 19, 2), (x, 25, 1.4)], "acc" if i % 2 else "acc2")
        c.E(14, 11.5, 9.8, 8.5, "body", clip=15); c.E(9, 7, 1.6, 1.3, "white", paint=True, only="body")
        c.E(14, 14.5, 7, 1.4, "acc", paint=True, only="body")
        for x in (7, 14, 21): c.E(x, 7 + abs(x - 14) * .2, 1, 1, "glow", paint=True, only="body")
        c.head = (14, 11, 9, 6); c.eyepair(14, 11.5, 4)
        if t >= 3: c.P([(12, 3), (14, -1), (16, 3)], "gold")
    else:  # seahorse
        c.chain([(15, 14, 3.5), (17, 19, 3.8), (16, 24, 2.8), (12, 26, 2), (10, 23.5, 1.6)], "body")
        c.E(10, 23.4, 1.6, 1.6, "acc"); c.chain([(16.5, 16, 1.2), (17.5, 20, 1.2), (16, 24, 1)], "belly", paint=True, only="body")
        for y in (14, 17, 20, 23): c.P([(18.5, y), (22, y - 1.6), (21, y + 1.6)], "glow") if False else None
        spines(c, [(18, 10, 2.5), (18.8, 14, 2.5), (19.5, 18, 2.5)], "acc") if True else None
        c.P([(12, 17), (7, 19), (10.5, 21)], "glow")
        c.E(14, 8.5, 5.3, 4.8, "body"); c.chain([(12, 9, 2.6), (6, 10.3, 2.2), (2, 10.4, 1.8)], "body")
        c.P([(12, 4.5), (13, -.5), (16, 3)], "acc"); c.chain([(14, 12, 3), (14.5, 14, 3.4)], "body", line=False)
        c.head = (14, 8.5, 5.3, 4.8); c.eye1(11.5, 7.6, -1); c.eye1(15.2, 7.6, 1)


# ---------------------------------------------------------------- knight
def knight(c, v):
    t = v.t; p = v.pose; w = v.tail % 4; k = v.ears
    cape = v.branch in ("lendario", "companheiro") or t >= 3
    def helmet(hx, hy, rx, ry):
        if k == 0: c.E(hx, hy - ry - 1, 1.2, 3, "acc")
        elif k == 1: c.P([(hx - 3.5, hy - ry + 1), (hx - 6.5, hy - ry - 4.5), (hx - 2, hy - ry - 1.5)], "bone", mir=True, mx=hx)
        elif k == 2: c.P([(hx - .7, hy - ry + 1), (hx - .5, hy - ry - 6), (hx + .5, hy - ry - 6), (hx + 1.7, hy - ry + 1)], "acc2")
        elif k == 3: c.E(hx, hy - ry + .5, rx * 1.1, 2.6, "gold", line=False)
        else: c.P([(hx - 4.5, hy - ry + 2), (hx - 9, hy - ry - 4), (hx - 3.5, hy - ry + 4)], "white", mir=True, mx=hx)
        c.E(hx, hy, rx, ry, "metal"); c.R(hx - rx * .85, hy, hx + rx * .85, hy + ry * .75, "metal", line=False)
        c.R(hx - rx * .65, hy - ry * .3, hx + rx * .65, hy + ry * .35, "dark", line=False)
    if p == 0 or p == 2:
        if cape: c.P([(8, 11), (20, 11), (23, 24), (5, 24)], "acc")
        if w == 0: c.L(23.5, 24, 23.5, 7, 1.6, "metal"); c.R(21.5, 15, 25.5, 16.3, "gold"); c.P([(22.7, 8), (23.5, 3), (24.3, 8)], "metal"); c.L(23.5, 15, 23.5, 8, .5, "white", line=False)
        elif w == 1: c.E(5, 17, 3.2, 4.3, "acc"); c.E(5, 17, 1.4, 1.9, "gold", line=False)
        elif w == 2: c.L(24, 26, 24, 3, 1.1, "wood"); c.P([(22.6, 6), (24, .5), (25.4, 6)], "metal")
        else: c.L(22, 20, 26, 6, 1.4, "dark"); c.E(26, 5.5, 2.4, 2.4, "glow")
        c.R(10, 21, 13.2, 26.5, "metal", r=1); c.R(14.8, 21, 18, 26.5, "metal", r=1)
        c.R(9.4, 25, 13.4, 27, "dark", r=.8); c.R(14.6, 25, 18.6, 27, "dark", r=.8)
        sq = (p == 2)
        c.R(9 - sq * 1.2, 12, 19 + sq * 1.2, 21.8, "metal", r=2.2); c.R(11, 14, 17, 19.5, "body", r=1.5)
        c.chain([(14, 14.5, .6), (14, 19.5, .6)], "dark", paint=True)
        c.E(14, 16.7, 1.5, 1.5, "glow", line=False); c.R(9.2, 20, 18.8, 21.8, "gold", line=False)
        c.chain([(8, 14.5, 2.6), (6.5, 19, 2.2)], "metal", mir=True); c.E(6.3, 20, 1.5, 1.5, "body2", mir=True)
        c.E(7.8, 13.2, 3.1 + sq, 2.6 + sq * .5, "metal", mir=True)
        if t >= 2: c.P([(5, 12), (3, 7), (9, 11)], "acc2", mir=True)
        helmet(14, 7.5, 5.3, 5.2); c.head = (14, 7.5, 5.3, 5.2); c.neck = (14, 12.5, 8)
    elif p == 1:  # wide stance greatsword
        if cape: c.P([(7, 11), (21, 11), (25, 25), (3, 25)], "acc")
        c.chain([(11, 20, 3.6), (8, 25.5, 3)], "metal"); c.chain([(17, 20, 3.6), (20, 25.5, 3)], "metal"); c.R(5.5, 25, 10, 27, "dark", r=.8); c.R(18, 25, 22.5, 27, "dark", r=.8)
        c.R(9.5, 12, 18.5, 21, "metal", r=2.2); c.R(11.5, 14, 16.5, 19, "body", r=1.5); c.E(14, 16.5, 1.4, 1.4, "glow", line=False)
        c.R(9.3, 19.5, 18.7, 21.2, "gold", line=False)
        c.L(14, 27, 14, 5, 1.8, "metal"); c.R(10.5, 17, 17.5, 18.3, "gold"); c.L(14, 22, 14, 6, .6, "white", line=False); c.P([(12.8, 5), (14, .5), (15.2, 5)], "metal")
        c.chain([(8.5, 14.5, 2.6), (11.5, 18, 2.2)], "metal", mir=True); c.E(7.5, 13.4, 3.3, 2.7, "metal", mir=True)
        helmet(14, 7.5, 5.3, 5.2); c.head = (14, 7.5, 5.3, 5.2); c.neck = (14, 12.5, 8)
    else:  # robed battle-mage knight
        c.L(23, 26, 23, 4, 1.1, "wood"); c.E(23, 3.3, 2.4, 2.4, "glow"); c.E(22.4, 2.7, .7, .7, "white", line=False)
        c.P([(11, 12), (17, 12), (21, 26.5), (7, 26.5)], "acc"); c.P([(12.5, 14), (15.5, 14), (16, 26), (12, 26)], "gold", line=False)
        c.R(11, 24, 17, 26.5, "dark", line=False)
        c.chain([(10.5, 14, 2.6), (7, 19, 2.2)], "acc", mir=True); c.E(6.4, 19.8, 1.6, 1.6, "belly", mir=True)
        c.E(8.3, 13, 3, 2.4, "metal", mir=True)
        c.E(14, 8, 4.8, 4.6, "belly"); c.P([(7.5, 10), (14, -1), (20.5, 10)], "acc"); c.E(14, 9, 7.5, 1.4, "acc")
        c.head = (14, 8, 4.8, 4.6); c.neck = (14, 12.5, 8); c.eyekind = None; c.eyepair(14, 9.4, 2.2, big=True)
        return
    c.eyekind = "led" if v.branch != "sombrio" else None
    c.eyepair(14, 8.2, 2.1, big=False)


# ---------------------------------------------------------------- robot
def robot(c, v):
    t = v.t; p = v.pose; k = v.ears
    c.eyekind = "led"
    if p == 0:  # biped
        if k == 0: c.L(14, 4, 14, .8, 1, "dark"); c.E(14, 1.2, 1.6, 1.4, "glow")
        elif k == 1: c.L(9.5, 4, 8, .8, 1, "dark", mir=True); c.E(8, 1.2, 1.4, 1.4, "glow", mir=True)
        elif k == 2: c.E(14, 2.5, 4.5, 1.6, "acc"); c.L(14, 4, 14, 2.5, 1, "dark")
        elif k == 3: c.E(7.8, 8, 2.2, 3.2, "acc", mir=True)
        else: c.P([(9, 5), (6, -.5), (11.5, 4)], "acc", mir=True)
        c.R(10, 21.5, 13, 26, "metal"); c.R(15, 21.5, 18, 26, "metal"); c.R(9, 25, 13.6, 26.8, "dark"); c.R(14.4, 25, 19, 26.8, "dark")
        c.R(8.5, 12, 19.5, 22, "metal", r=1.5); c.R(11, 14, 17, 19, "acc", r=1); c.E(14, 16.5, 1.2, 1.2, "white", line=False)
        for y in (13.5, 20.5): c.R(9, y, 19, y + .5, "dark", paint=True, only="metal")
        c.chain([(8, 14.5, 2.8), (5, 18.5, 2.4)], "metal", mir=True); c.E(4.3, 19.7, 1.8, 1.8, "acc", mir=True)
        c.R(8, 3.5, 20, 12, "metal", r=2.2); c.R(9.5, 5.6, 18.5, 9.6, "dark", line=False)
        c.head = (14, 7.5, 6, 4); c.neck = (14, 12.5, 8); c.eyepair(14, 7.6, 2.8, big=False)
        if t >= 3: c.R(3, 10, 8, 13.5, "dark", mir=True); c.R(2.5, 8.5, 4.5, 11, "glow", mir=True)
    elif p == 1:  # orb
        c.L(14, 3, 14, 7, 1, "dark")
        c.P([(3, 4), (14, 6), (25, 4), (14, 8.5)], "metal") if t >= 2 else None
        c.E(14, 15, 9.3, 9.3, "metal"); c.E(14, 15.5, 6, 5.2, "dark", line=False)
        c.R(4, 20.5, 24, 22, "acc", paint=True, only="metal"); c.E(8, 11, 1.4, 1.2, "white", paint=True, only="metal")
        c.E(10, 25.5, 2.2, 1.2, "dark"); c.E(18, 25.5, 2.2, 1.2, "dark")
        c.E(3, 16, 2, 2, "glow", mir=True) if t >= 2 else None
        c.head = (14, 14, 8, 8); c.eyepair(14, 15.4, 2.2, big=False)
    elif p == 2:  # tank
        c.chain([(19, 14, 3), (27, 12, 2.6)], "metal") if t >= 2 else None
        c.R(3, 21, 25, 26.8, "dark", r=2.2)
        for x in (6.5, 11, 17, 21.5): c.E(x, 24, 1.8, 1.8, "metal", line=False)
        c.R(6.5, 12.5, 21.5, 21.5, "metal", r=1.5); c.R(8.5, 14.5, 19.5, 17, "acc", paint=True, only="metal")
        c.E(14, 12, 6.2, 4.6, "metal", clip=12.5); c.R(10.5, 8.6, 17.5, 11, "dark", line=False)
        c.L(14, 7, 14, 2.5, 1, "dark"); c.E(14, 2.2, 1.5, 1.5, "glow")
        c.head = (14, 10, 6, 4); c.eyepair(14, 9.8, 2.2, big=False)
        if t >= 3: c.R(5, 10, 8, 14, "dark", mir=True)
    else:  # spider walker
        for i, (x1, y1) in enumerate(((2, 8), (1, 15), (2, 22), (3, 27))):
            c.chain([(10, 15 + i * .8, 2), (x1 + 1, y1 - 3, 1.8), (x1, y1, 1.4)], "metal", mir=True, line=False)
        c.E(14, 16, 8.6, 6.6, "metal"); c.E(14, 14, 5.6, 4.6, "dark", line=False)
        c.E(14, 8.8, 4, 3, "acc"); c.L(14, 6, 14, 2, 1, "dark"); c.E(14, 1.6, 1.4, 1.4, "glow")
        c.R(5, 18, 23, 19, "acc", paint=True, only="metal")
        c.head = (14, 14, 6, 5); c.eyepair(14, 14, 2.3, big=False)


# ---------------------------------------------------------------- golem
def golem(c, v):
    t = v.t; p = v.pose; arm = v.tail % 3; hk = v.ears
    def head(hx, hy, rx, ry):
        if hk == 1: c.P([(hx - rx * .6, hy - ry + 1), (hx - rx * .9, hy - ry - 4), (hx - 1, hy - ry + .5)], "bone", mir=True, mx=hx)
        elif hk == 2: c.P([(hx - rx * .7, hy - ry + 1), (hx - rx * .6, hy - ry - 5), (hx - 1, hy - ry - 2), (hx, hy - ry - 6.5), (hx + 1, hy - ry - 2), (hx + rx * .6, hy - ry - 5), (hx + rx * .7, hy - ry + 1)], "glow")
        elif hk == 3: c.E(hx, hy - ry, rx * .9, 2, "leaf")
        c.E(hx, hy, rx, ry, "metal")
    if p == 0:  # boulder
        if t >= 4: c.P([(8, 9), (5, 1), (11, 6)], "glow", mir=True); c.P([(12, 6), (14, -1), (16, 6)], "acc2")
        c.R(8, 22, 12.5, 26.5, "metal"); c.R(15.5, 22, 20, 26.5, "metal")
        c.P([(6, 13), (9, 9), (19, 9), (22, 13), (23.5, 22), (19.5, 25), (8.5, 25), (4.5, 22)], "metal")
        c.P([(9.5, 13.5), (18.5, 13.5), (17.5, 21), (10.5, 21)], "body2", paint=True, only="metal")
        if arm == 0: c.E(3.6, 19, 3.6, 4.2, "metal", mir=True); c.E(3.2, 21, 2, 1.4, "body2", mir=True, line=False)
        elif arm == 1: c.chain([(5, 14, 3.2), (3, 19, 3)], "metal", mir=True); c.P([(.5, 19), (3, 25), (5.5, 19)], "glow", mir=True)
        else: c.E(3, 16, 2.4, 2.4, "metal", mir=True); c.E(2.2, 22, 2.8, 3.4, "metal", mir=True)
        c.E(5.6, 11.8, 3.6, 3, "metal", mir=True); head(14, 7.4, 4.4, 3.8); c.R(10.5, 5.6, 17.5, 6.6, "body2", paint=True, only="metal")
        c.P([(12, 17), (14, 14), (16, 17), (14, 20.5)], "glow")
        for (x, y) in ((8, 16), (20, 17), (12, 23), (17, 22.5)): c.chain([(x, y, .6), (x + 1.5, y + 1.5, .6)], "dark", paint=True, only="metal")
        c.head = (14, 7.4, 4.4, 3.8); c.neck = (14, 11.5, 9)
        if hk == 4: c.eye1(14, 7.6, -1, big=True)
        else: c.eyepair(14, 8, 2.1, big=False)
        if t >= 3: c.P([(2, 8), (3.5, 4), (5.5, 8)], "glow", mir=True)
    elif p == 1:  # totem blocks
        c.R(7, 18, 21, 26.5, "metal", r=1); c.R(8.5, 10.5, 19.5, 18.5, "metal", r=1);
        c.R(9, 2.5, 19, 10.5, "metal", r=1); c.P([(11, 2.5), (14, -1), (17, 2.5)], "glow") if hk != 2 else c.P([(10, 2.5), (11, -1.5), (14, 1), (17, -1.5), (18, 2.5)], "glow")
        for y in (11, 19): c.R(8.5, y, 19.5, y + .8, "dark", line=False)
        c.R(2, 11, 6.5, 16, "metal", r=1); c.R(21.5, 11, 26, 16, "metal", r=1); c.R(1, 17, 5, 22, "metal", r=1); c.R(23, 17, 27, 22, "metal", r=1)
        c.R(11, 21, 17, 24, "glow", paint=True, only="metal"); c.chain([(10, 13, .6), (18, 15, .6)], "acc", paint=True, only="metal")
        c.head = (14, 6.5, 5, 4); c.neck = (14, 11, 8); c.eyepair(14, 6.8, 2.4, big=False)
    elif p == 2:  # crystal hulk
        c.P([(6, 12), (2, 3), (9, 9)], "glow", mir=True); c.P([(11, 7), (14, -1), (17, 7)], "acc"); c.P([(8, 22), (3, 17), (6, 12)], "glow", mir=True)
        c.R(8, 22, 12.5, 26.5, "metal"); c.R(15.5, 22, 20, 26.5, "metal")
        c.P([(14, 8), (22, 13), (20, 24), (14, 26), (8, 24), (6, 13)], "metal")
        c.E(5, 18, 3.4, 4.5, "metal", mir=True); c.P([(2, 20), (4, 26), (6, 20)], "glow", mir=True)
        c.P([(14, 11), (17.5, 17), (14, 23), (10.5, 17)], "glow"); c.P([(14, 13), (15.8, 17), (14, 21)], "white", line=False)
        head(14, 7.2, 4.2, 3.6); c.head = (14, 7.2, 4.2, 3.6); c.neck = (14, 11, 8); c.eyepair(14, 7.8, 2, big=False)
    else:  # floaters: head, torso and fists apart
        c.E(5, 22, 3, 3, "metal", mir=True); c.E(3.5, 16, 1.3, 1.3, "glow", mir=True)
        c.P([(8, 13), (10, 11), (18, 11), (20, 13), (20.5, 20), (17, 23.5), (11, 23.5), (7.5, 20)], "metal")
        c.P([(12, 15), (14, 13), (16, 15), (14, 20)], "glow")
        c.E(14, 25.3, 5, 1.1, "dark", line=False) if False else None
        head(14, 5.4, 4.4, 3.8); c.head = (14, 5.4, 4.4, 3.8); c.neck = (14, 10, 8); c.eyepair(14, 5.8, 2.1, big=False)
        for (x, y) in ((4, 12), (24, 12), (2, 8), (26, 8)): c.P([(x - 1, y + 1), (x, y - 1.5), (x + 1, y + 1)], "glow")


# ---------------------------------------------------------------- winged
def winged(c, v):
    t = v.t; p = v.pose
    demon = v.branch == "sombrio" or (v.branch not in ("lendario", "companheiro") and v.body % 2)
    if p == 0:
        if demon:
            c.P([(17, 11), (27.5, 2), (25.5, 8), (27.5, 12), (24, 13.5), (26, 18), (17, 17)], "dark", mir=True)
            c.chain([(17.5, 12, 1), (27, 2.5, .8)], "red", mir=True, line=False)
            c.chain([(18, 20, 1.4), (23, 24, 1.2), (26, 21, 1)], "dark"); c.P([(25, 20.5), (27.5, 17.5), (27.6, 22)], "red")
        else:
            c.P([(17, 11), (27.5, 5), (27.5, 12), (24.5, 18), (17, 17)], "white", mir=True); c.P([(19, 14), (26.5, 10), (26, 15), (22.5, 19)], "bone", mir=True, line=False)
            c.P([(23.5, 7), (27.5, 5), (27.5, 8)], "acc", mir=True, line=False)
            for i in range(3): c.chain([(18, 12 + i * 2, .5), (26 - i * 1.5, 8 + i * 3, .5)], "ice", paint=True, mir=True, only="white")
        c.R(10.5, 21, 13.2, 26.5, "body2", r=1); c.R(14.8, 21, 17.5, 26.5, "body2", r=1)
        c.E(11.3, 26.4, 2.4, 1, "dark", line=False); c.E(16.7, 26.4, 2.4, 1, "dark", line=False)
        if not demon and t >= 2: c.P([(9.5, 17), (18.5, 17), (20.5, 26.5), (7.5, 26.5)], "bone"); c.R(9.5, 24, 18.5, 25, "gold", line=False)
        c.R(10, 12, 18, 21.5, "body", r=2.5); c.R(11.5, 14, 16.5, 19, "belly", paint=True, only="body")
        c.chain([(9.5, 14, 2.2), (6.5, 18.5, 1.9)], "body", mir=True); c.E(6, 19.7, 1.5, 1.5, "belly", mir=True)
        if demon: claw(c, 5.4, 20.6, -.5, 1, 3, .8, 1.4, "red"); claw(c, 22.6, 20.6, .5, 1, 3, .8, 1.4, "red")
        if t >= 3: c.R(9, 19.5, 19, 20.8, "gold", line=False)
        if demon:
            c.P([(9.5, 6), (6, 0), (11, 4)], "bone", mir=True)
            if t >= 3: c.L(24, 26, 24, 4, 1.2, "dark"); c.P([(22.5, 5.5), (24, 1), (25.5, 5.5)], "metal")
        else: c.E(14, 1.3, 5.5, 1.5, "gold", line=True)
        c.E(14, 7.5, 4.8, 4.5, "body"); c.head = (14, 7.5, 4.8, 4.5); c.neck = (14, 12.5, 8); c.eyepair(14, 8, 2.4); c.mouth(14, 11, 2.6)
    elif p == 1:  # imp crouch, big head
        c.P([(17, 14), (26, 6), (26, 12), (23, 17)], "dark", mir=True)
        c.chain([(16, 22, 1.6), (22, 25, 1.4), (26, 21.5, 1.2)], "dark"); c.P([(25, 21), (27.5, 18), (27.6, 23)], "red")
        c.E(9.5, 25.2, 3.2, 1.6, "body", mir=True); claw(c, 7, 26.2, -.5, .6, 3, .9, 1.4, "bone"); claw(c, 21, 26.2, .5, .6, 3, .9, 1.4, "bone")
        c.E(14, 21, 5.6, 4.8, "body"); c.E(14, 22, 3.2, 3.2, "belly", paint=True, only="body")
        c.chain([(9, 19.5, 2.6), (5.5, 23.5, 2.2)], "body", mir=True); claw(c, 4.8, 24.6, -.4, 1, 3, .9, 1.4, "bone")
        c.P([(8, 9), (4, 2), (11, 6)], "bone", mir=True)
        c.E(14, 12.5, 8, 6.8, "body"); c.E(14, 15, 5, 2.8, "belly", paint=True, only="body")
        c.E(5.5, 12, 2.4, 3.2, "body", mir=True, rot=.3, line=False)
        c.head = (14, 12.5, 8, 6.8); c.neck = (14, 18, 8); c.eyepair(14, 11.6, 3.8); c.mouth(14, 15.5, 5)
    elif p == 2:  # harpy: wings up, talons
        c.P([(10.5, 15), (1.5, 2), (3, 12), (1, 15), (5, 17), (3, 21), (10, 21)], "acc" if not demon else "dark", mir=True)
        c.P([(9.5, 14.5), (3.5, 5), (6, 14)], "acc2" if not demon else "red", mir=True, line=False)
        c.chain([(11.5, 20, 3.2), (10.5, 25, 2.2)], "body", mir=True); claw(c, 9.5, 26, -.7, .5, 3, .8, 1.6, "gold"); claw(c, 18.5, 26, .7, .5, 3, .8, 1.6, "gold")
        c.R(10, 12.5, 18, 21.5, "body", r=2.5); c.R(11.8, 14.5, 16.2, 19.5, "belly", paint=True, only="body")
        c.chain([(9.8, 14, 2.2), (8, 18, 1.9)], "body", mir=True)
        c.E(14, 7.5, 4.6, 4.4, "body"); c.P([(10, 4), (14, -1), (18, 4)], "acc") if not demon else c.P([(9.5, 5), (6, 0), (11, 4)], "bone", mir=True)
        c.head = (14, 7.5, 4.6, 4.4); c.neck = (14, 12.5, 8); c.eyepair(14, 8, 2.3); c.mouth(14, 11, 2.4)
    else:  # seraph orb with wing pairs
        for i, (dy, ln) in enumerate(((-6, 12), (0, 13), (6, 11))):
            c.P([(17, 14), (17 + ln * .9, 14 + dy - 2), (17 + ln, 14 + dy + 2), (17, 15.5)], "white" if i != 1 else "bone", mir=True)
        c.E(14, 14, 6.6, 6.6, "white"); c.E(14, 14, 3.8, 3.8, "glow", paint=True, only="white")
        c.E(14, 6.5, 4.5, 1.2, "gold"); c.E(14, 24, 2.4, 1.2, "gold") if False else None
        c.head = (14, 14, 6, 6); c.eyekind = "white"; c.eye1(14, 14, -1, big=True)


# ---------------------------------------------------------------- stack
def stack(c, v):
    t = v.t; p = v.pose; k = v.ears
    def hat(hx, hy, rx):
        if k == 0: c.R(hx - 6, hy - 5.4, hx + 6, hy - 4, "dark"); c.R(hx - 3.6, hy - 10.5, hx + 3.6, hy - 5, "dark"); c.R(hx - 3.6, hy - 7, hx + 3.6, hy - 5.6, "acc", line=False)
        elif k == 1: c.E(hx, hy - 5, 6.3, 3.4, "acc", clip=hy - 3.5); c.E(hx, hy - 9, 1.8, 1.8, "white")
        elif k == 2: c.P([(hx - 6.5, hy - 3.5), (hx, hy - 11.5), (hx + 6.5, hy - 3.5)], "acc2"); c.E(hx, hy - 3.7, 8, 1.4, "acc2")
        elif k == 3: c.P([(hx - 5, hy - 3.5), (hx - 5, hy - 8), (hx - 2.5, hy - 5.5), (hx, hy - 10), (hx + 2.5, hy - 5.5), (hx + 5, hy - 8), (hx + 5, hy - 3.5)], "gold")
        else: c.E(hx - 4.5, hy - 7, 1.8, 4.3, "body", mir=True, mx=hx, rot=.2)
    if p == 0:  # snowman
        c.chain([(8, 17, 1.1), (2.5, 14, 1.1)], "wood", mir=True, line=False); c.chain([(4.5, 15.5, .9), (3.5, 12, .9)], "wood", mir=True, line=False)
        c.E(14, 19.7, 8.2, 6.8, "body"); c.E(14, 9.8, 5.9, 5.4, "body")
        for y in (18, 20.5, 23): c.mark(14, y, "dark")
        hat(14, 9.8, 5.9); c.R(12.7, 11.3, 15.3, 13, "acc"); c.P([(15, 11.5), (19, 12.2), (15, 13)], "acc", line=False) if False else None
        c.head = (14, 9.8, 5.9, 5.4); c.neck = (14, 15, 9); c.eyepair(14, 8.6, 2.9, big=False); c.mouth(14, 14.5, 4)
        c.E(14, 15, 7.5, 1.6, "acc", line=True) if t >= 3 and v.branch == "base" else None
    elif p == 1:  # pumpkin scarecrow
        c.chain([(14, 4, .8), (14, 8, .8)], "leaf") if False else None
        c.E(14, 18.5, 9.6, 7.8, "acc"); c.E(8, 18.5, 3.2, 7.2, "acc2", line=False, mir=True, mx=14) if False else None
        c.R(13.4, 11, 14.6, 25.5, "body2", paint=True, only="acc"); c.chain([(8.5, 12.5, .6), (7, 20, .6), (9, 25, .6)], "body2", paint=True, only="acc"); c.chain([(19.5, 12.5, .6), (21, 20, .6), (19, 25, .6)], "body2", paint=True, only="acc")
        c.R(13, 8.5, 15, 12, "leaf"); c.chain([(15, 9, 1), (19, 7.5, .8), (18, 4.5, .8)], "leaf")
        c.E(14, 7.8, 8.6, 1.5, "wood"); c.R(9, 1.5, 19, 7.8, "wood", r=1.2); c.R(9, 5.2, 19, 6.6, "acc2", line=False)
        c.chain([(5, 22, 1.2), (2.5, 25, 1)], "wood", mir=True, line=False) if False else None
        c.head = (14, 17, 8, 6); c.neck = (14, 12, 8); c.eyepair(14, 16.5, 3.8); c.mouth(14, 21, 7)
    elif p == 2:  # layered cake
        c.R(3.5, 19, 24.5, 26.5, "acc", r=2.4); c.R(5.5, 12.5, 22.5, 19.2, "belly", r=2.2); c.R(8, 7, 20, 12.7, "acc2", r=2)
        for x in (7, 11.5, 16.5, 21): c.E(x, 19.2, 1.5, 2.2, "white", line=False)
        for x in (10, 14, 18): c.R(x - .4, 3.5, x + .4, 7.2, "bone"); c.E(x, 2.6, .9, 1.4, "glow")
        c.chain([(4.5, 24, .6), (23.5, 24, .6)], "body2", paint=True, only="acc")
        c.head = (14, 16, 8, 4); c.neck = (14, 12, 8); c.eyepair(14, 15.4, 4, big=False); c.mouth(14, 18.2, 3.5)
    else:  # winged totem
        c.P([(17, 14), (27, 8), (26, 16), (17, 19)], "acc", mir=True); c.P([(18, 15), (25, 11), (24, 16)], "glow", mir=True, line=False)
        c.R(7.5, 19, 20.5, 26.5, "metal", r=2); c.R(8.5, 11.5, 19.5, 19.2, "belly", r=2); c.R(9.5, 4, 18.5, 11.7, "acc", r=2)
        c.P([(9.5, 5), (8, .5), (12, 4)], "bone", mir=True); c.R(10, 21.5, 18, 23.5, "dark", line=False)
        c.R(13.4, 22, 14.6, 25, "glow", line=False)
        c.head = (14, 8, 5, 4); c.neck = (14, 12, 8); c.eyepair(14, 7.6, 2.6, big=False); c.mouth(14, 10, 3)
        c.eyepair(14, 15, 3, big=False)


# ---------------------------------------------------------------- serpent
def serpent(c, v):
    t = v.t; p = v.pose; k = v.ears
    if p == 0:  # cobra coil
        if t >= 3: c.P([(11, 14), (3, 6), (5, 11), (2.5, 13), (6, 15), (11, 18)], "acc", mir=True)
        c.E(14, 23, 10.5, 3.6, "body"); c.E(14, 23.8, 7, 1.6, "belly", paint=True, only="body"); c.E(14, 18.5, 8, 3.3, "body2")
        c.chain([(20, 22, 3), (25, 20, 2.4), (26.5, 16, 1.4)], "body"); c.chain([(14, 18, 5), (14, 12.5, 4.6)], "body")
        c.R(12.5, 14, 15.5, 20, "belly", paint=True, only="body")
        for y in (14.5, 16.5, 18.5): c.R(12.5, y, 15.5, y + .5, "body2", paint=True, only="belly")
        hx, hy = 14, 8
        if k % 2 == 0: c.E(14, 8.5, 9, 6, "acc"); c.E(14, 9, 6.2, 4.2, "body2", line=False); c.E(8, 8, 1.4, 1.4, "glow", paint=True, only="acc"); c.E(20, 8, 1.4, 1.4, "glow", paint=True, only="acc")
        else: c.P([(10, 5), (7, .5), (12, 4)], "bone", mir=True)
        c.E(hx, hy, 5, 4.2, "body"); c.E(hx, hy + 2.8, 3.6, 1.8, "belly", paint=True)
        fangs(c, 14, 11, 3.6, 2); c.head = (hx, hy, 5, 4.2); c.eyepair(14, 7.5, 2.5)
        if t >= 3: c.P([(10.5, 5), (14, -1), (17.5, 5)], "gold")
    elif p == 1:  # sea serpent waves (faces left)
        pts = [(24, 20), (20.5, 23.5), (16, 21), (12, 24), (8, 21), (7, 16)]
        c.chain([(26.5, 17, 1.6), (24, 20, 2.6), (20.5, 23.5, 3.4), (16, 21, 4), (12, 24, 4.4), (8, 21, 4.4), (7.5, 16, 4.4), (8, 12, 4.2)], "body")
        c.chain([(20.5, 24.2, 1.2), (16, 22, 1.5), (12, 25, 1.6), (8, 22, 1.6), (7.5, 17, 1.6)], "belly", paint=True, only="body")
        for (x, y) in ((22, 20), (18, 20), (14, 22), (10, 22)): c.P([(x - 1.4, y), (x + .6, y - 2.8), (x + 1.6, y)], "acc") if False else None
        spines(c, [(22.5, 19, 1.5), (18.5, 19.5, 1.5), (14.5, 21, 1.5), (10.5, 20.5, 1.5)], "acc")
        c.P([(25.8, 17), (28, 14), (27.2, 19.5)], "acc")
        hx, hy = 9, 8.5
        c.E(hx, hy, 5.4, 4.4, "body"); c.E(4.3, 10, 3.4, 2.4, "body"); c.E(4.8, 11.3, 2.8, 1.1, "belly", paint=True)
        c.P([(8, 4.5), (9.5, -.5), (12, 4)], "acc"); c.P([(12, 6), (16.5, 4), (14, 9)], "acc", line=False)
        c.head = (hx, hy, 5.4, 4.4); c.neck = (8, 13, 7); c.eye1(8.5, 7.8, -1); fangs(c, 4.6, 11.7, 2.4, 2)
    elif p == 2:  # wyrm with arms standing
        c.chain([(18, 24, 3), (24, 24, 2.4), (26.5, 20, 1.4)], "body")
        c.E(13, 24, 9, 3.4, "body"); c.E(13, 24.6, 6, 1.4, "belly", paint=True, only="body")
        c.chain([(13, 20, 6.4), (14, 14, 6)], "body"); c.chain([(13, 20, 3), (14, 14, 3)], "belly", paint=True, only="body")
        c.chain([(9.5, 15, 2.2), (6, 19.5, 1.9)], "body", mir=True); claw(c, 5.2, 20.6, -.5, 1, 3, .9); claw(c, 22.8, 20.6, .5, 1, 3, .9)
        if t >= 3: c.P([(10, 14), (3, 6), (5, 12), (3, 14)], "acc", mir=True)
        hx, hy = 14, 8; horn_set(c, k, hx, hy, 5, 4.2)
        c.E(hx, hy, 5.2, 4.4, "body"); c.E(14, 10.5, 3.2, 2, "belly", paint=True)
        c.head = (hx, hy, 5.2, 4.4); c.neck = (14, 13, 8); c.eyepair(14, 7.6, 2.7); c.mouth(14, 11.3, 3.4)
    else:  # caterpillar stack
        for i, (cy, r) in enumerate(((23.2, 5), (18.2, 4.6), (13.4, 4.4))):
            c.E(14, cy, r + 1, r, "body" if i % 2 else "body2")
            c.E(14 - r - .5, cy + 1.8, 1.6, 1.4, "acc", mir=True)
        c.E(14, 8, 5.4, 4.6, "body"); c.chain([(12, 4, .8), (9, -.5, .7)], "dark", mir=True, line=False); c.E(9, -.3, 1.1, 1.1, "glow", mir=True)
        c.P([(8, 7), (5, 3), (9.5, 4)], "acc", mir=True) if t >= 3 else None
        c.E(14, 21.5, 3, 2.8, "belly", paint=True, only="body2") if False else None
        c.head = (14, 8, 5.4, 4.6); c.neck = (14, 12, 8); c.eyepair(14, 7.6, 2.7); c.mouth(14, 11, 3)


ARCH_FN = dict(slime=slime, dragon=dragon, beast=beast, bird=bird, bug=bug, plant=plant, ghost=ghost,
               fish=fish, knight=knight, robot=robot, golem=golem, winged=winged, stack=stack, serpent=serpent)


# ---------------------------------------------------------------- overlays, texture, draw
def sparkle(c, x, y, key="gold"):
    c.mark(x, y, key, 1)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)): c.mark(x + dx / c.f, y + dy / c.f, key, 0)


def overlay(c, v):
    t = v.t; b = v.branch
    if t >= 4: sparkle(c, 3.2, 3.2, "gold"); sparkle(c, 25, 5.5, "acc2")
    if t < 2: return
    hx, hy, rx, ry = c.head; top = hy - ry
    a = v.g["accy"]
    if b == "base" or t < 2:
        pass
    if a == 1 and b == "base" and v.arch not in ("ghost", "knight", "robot"):
        c.E(hx, hy - ry * .55, 1.3, 1.3, "glow", line=True)
    elif a == 2 and b == "base" and v.arch not in ("bird", "fish", "bug"):
        nx, ny, nw = c.neck; c.chain([(nx - nw * .4, ny, 1.6), (nx, ny + .6, 1.6), (nx + nw * .4, ny, 1.6)], "gold")
    elif a == 3 and b == "base":
        c.E(hx - rx * .6, hy + ry * .35, 1.5, 1.1, "acc", line=False, mir=True, mx=hx)
    if b == "companheiro":
        nx, ny, nw = c.neck
        c.chain([(nx - nw * .45, ny, 2.4), (nx, ny + .8, 2.4), (nx + nw * .45, ny, 2.4)], "acc")
        c.chain([(nx + nw * .3, ny + 1, 2), (nx + nw * .38, ny + 5, 1.8)], "acc")
        c.E(hx - rx * .62, hy + ry * .3, 1.5, 1.1, "acc", line=False, mir=True, mx=hx)
    elif b == "sombrio":
        if v.arch not in ("dragon", "winged", "knight", "beast", "bug", "serpent", "golem"):
            c.P([(hx - rx * .6, top + 1), (hx - rx * 1.1, top - 4.5), (hx - rx * .1, top + .5)], "dark", mir=True, mx=hx)
        c.E(hx - rx * .55, hy + ry * .35, 1.4, 1.0, "glow", line=False, mir=True, mx=hx) if False else None
    elif b == "lendario":
        ct = max(top, 6.5) if True else top
        hx2 = min(max(hx, 6), 22)
        c.R(hx2 - min(rx, 5), ct - 2.6, hx2 + min(rx, 5), ct - .6, "gold", line=True)
        pts = [(hx2 - 5, ct - 2.2), (hx2 - 5, ct - 5.6), (hx2 - 2.6, ct - 3.6), (hx2, ct - 6.8), (hx2 + 2.6, ct - 3.6), (hx2 + 5, ct - 5.6), (hx2 + 5, ct - 2.2)]
        c.P(pts, "gold"); c.E(hx2, ct - 3.2, .8, .8, "red", line=False)
    elif b == "artista":
        c.E(hx + 1.5, top + .5, rx * .85, 1.8, "acc"); c.E(hx - .5, top - 1, 1, 1, "acc2")
    elif b == "tecnico":
        c.L(hx + rx * .6, top + 1, hx + rx * .9, top - 3, 1, "dark"); c.E(hx + rx * .9, top - 3.3, 1.4, 1.4, "glow")


def apply_pattern(c, v):
    r = v.rng; N = c.N
    base = c.keys.index("body"); pk = np.array(c.pk + [-1])
    cur = np.where(c.ov >= 0, c.ov, pk[c.pid]); body = (cur == base) & (c.pid >= 0)
    if body.sum() < 30: return
    ys, xs = np.nonzero(body)
    m = np.zeros((N, N), bool)
    z = 2 if N >= 40 else 1
    if v.pat == 1:
        for _ in range(6):
            i = r.randrange(len(xs)); x, y = xs[i], ys[i]; m[y:y + z + 1, x:x + z + 1] = True
    elif v.pat == 2:
        y0, y1 = ys.min(), ys.max()
        for y in range(y0 + 3, y1, 5 + z): m[y:y + z, :] = True
    elif v.pat == 3:
        y1 = ys.max(); m[int(y1 - (y1 - ys.min()) * .3):, :] = True
    c.ov[m & body] = c.keys.index("body2")


def texture(c, v):
    N = c.N
    if N < 32: return
    base = c.keys.index("body"); pk = np.array(c.pk + [-1])
    cur = np.where(c.ov >= 0, c.ov, pk[c.pid]); body = (cur == base) & (c.pid >= 0)
    inner = body.copy()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        sh = np.zeros_like(body)
        ys0, ys1 = max(0, -dy), N - max(0, dy); xs0, xs1 = max(0, -dx), N - max(0, dx)
        sh[ys0:ys1, xs0:xs1] = body[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
        inner &= sh
    yy, xx = np.mgrid[0:N, 0:N]; t = v.g["tex"]; m = np.zeros((N, N), bool)
    s = 3 if N < 44 else 4
    if t == 1:   # scales: staggered dashes
        row = (yy // s) % 2; m = (yy % s == 1) & (((xx + row * (s // 2 + 1)) % (s + 2)) < 2)
    elif t == 2:  # fur ticks
        m = ((xx + (yy // 5) * 2) % 5 == 0) & (yy % 5 < 2)
    elif t == 3:  # plates seams
        m = (yy % (s + 3) == 0) & (xx % 9 < 5)
    elif t == 4:  # speckles
        for _ in range(8):
            i = c.v.rng.randrange(N * N); y, x = divmod(i, N); m[y, x:x + 2] = True
    c.ov[m & inner] = c.keys.index("body2")


def _touch(c):
    f = c.pid >= 0
    return f[0].any() or f[:, 0].any() or f[:, -1].any() or f[-1].any()


def draw(g, t, arch, branch="base", baby_kind=None, pose=None):
    N = SIZES[t]
    g = dict(g)
    if pose is not None: g["pose"] = pose
    sx0, sy0 = [(1, 1), (1.05, .94), (.94, 1.06), (1.05, 1.0), (1.06, .92), (.92, 1.06)][g["body"]] if t else (1, 1)
    for k in (1.0, .95, .9, .85, .8):
        v = V(g, t, branch, arch if t else "baby"); v.pose = g["pose"]; v.hd = g["hd"]
        pal = mkpal(g, branch, arch if t else "slime")
        c = Canvas(N, pal, v); c.sx, c.sy = sx0 * k, sy0 * k
        if t == 0:
            v.baby = baby_kind or BABIES[(g["seed"] + g["body"]) % len(BABIES)]; baby(c, v)
        else:
            ARCH_FN[arch](c, v)
            hx, hy, rx, ry = c.head; c.head = (c.tx(hx), c.ty(hy), rx * c.sx, ry * c.sy)
            nx, ny, nw = c.neck; c.neck = (c.tx(nx), c.ty(ny), nw * c.sx)
            c.sx = c.sy = 1.0
            overlay(c, v)
            if t >= 2 and v.pat > 0: apply_pattern(c, v)
            texture(c, v)
        if not _touch(c) or k == .8: break
    return c.render()
