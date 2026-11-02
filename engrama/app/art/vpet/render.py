"""Build one creature (body render + face data) for a stage; fits it into the stage canvas."""
from dataclasses import dataclass

import numpy as np

from .archetypes import ARCH_FN, BABIES, apply_pattern, baby, overlay, texture
from .core import PX, STAGES, Canvas, V, mkpal
from .plan import STYLE, branch_shift

MARGIN = 4           # parts must leave this much room (2 outline + 1 for animation shifts per side)
_BODY_SCALE = {0: (1, 1), 1: (1.05, .94), 2: (.94, 1.06), 3: (1.05, 1.0), 4: (1.06, .92), 5: (.92, 1.06)}


@dataclass
class Sprite:
    canvas: Canvas
    body: np.ndarray    # (N, N, 4) uint8, eyeless, bottom-aligned and centred
    ox: int
    oy: int
    n: int


def _build(g, t, arch, style, bid, kind, pose, k):
    N = PX[t]
    g = dict(g)
    if pose is not None:
        g["pose"] = pose
    sx0, sy0 = _BODY_SCALE[g["body"]] if t else (1, 1)
    v = V(g, t, style, arch if t else "baby", bid)
    v.pose = g["pose"]; v.hd = g["hd"]
    pal = mkpal(g, style, arch if t else "slime", branch_shift(bid))
    c = Canvas(N, pal, v)
    c.sx, c.sy = sx0 * k, sy0 * k
    if t == 0:
        v.baby = kind
        baby(c, v)
    else:
        ARCH_FN[arch](c, v)
        hx, hy, rx, ry = c.head
        c.head = (c.tx(hx), c.ty(hy), rx * c.sx, ry * c.sy)
        nx, ny, nw = c.neck
        c.neck = (c.tx(nx), c.ty(ny), nw * c.sx)
        c.sx = c.sy = 1.0
        overlay(c, v)
        if t >= 2 and v.pat > 0:
            apply_pattern(c, v)
        texture(c, v)
    return c


def _bbox(mask):
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def build(g, stage: str, arch: str, style: str = "base", bid: str = "base", kind: str = "blob", pose=None) -> Sprite:
    t = STAGES.index(stage)
    N = PX[t]
    room = N - MARGIN
    k = 1.0
    c = None
    for _ in range(6):
        c = _build(g, t, arch, style, bid, kind, pose, k)
        x0, y0, x1, y1 = _bbox(c.pid >= 0)
        w, h = x1 - x0 + 1, y1 - y0 + 1
        sc = min(room / w, room / h)
        if 1.0 <= sc <= 1.06 or (sc > 1.0 and k >= 1.3):
            break
        k = max(.5, min(1.3, k * sc * (.99 if sc > 1 else .975)))
    rgb = c.render()
    x0, y0, x1, y1 = _bbox(rgb[:, :, 3] > 0)
    ox = int(round((N - 1) / 2 - (x0 + x1) / 2))
    oy = (N - 1) - y1
    body = np.zeros_like(rgb)
    ys0, ys1 = max(0, -oy), min(N, N - oy)
    xs0, xs1 = max(0, -ox), min(N, N - ox)
    body[ys0 + oy:ys1 + oy, xs0 + ox:xs1 + ox] = rgb[ys0:ys1, xs0:xs1]
    return Sprite(c, body, ox, oy, N)
