"""vpet2 core: palette, vector parts, rasteriser with directional shading, cleanup and outline.

Design space: x centred on 0 (front view, mirrored pairs), y grows downwards, ground at y = 0.
A creature is a list of Part; `render` fits it to an N x N canvas and returns an RGBA array plus anchors.
"""
import colorsys
import math

import numpy as np

OUT = (46, 26, 22)                 # fixed warm dark outline
LIGHT = np.array((-.48, -.66, .58))
LIGHT = LIGHT / np.linalg.norm(LIGHT)

# material ids
BODY, BELLY, ACC, MARK, BONE, DARK, GLASS, GOLD = range(8)


def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1, max(0., min(1., s)), max(0., min(1., v)))
    return np.array((round(r * 255), round(g * 255), round(b * 255)), np.uint8)


def _toward(h, t, f):
    d = ((t - h + .5) % 1) - .5
    return (h + d * f) % 1


def ramp(h, s, v):
    """(highlight, base, shade) with hue shift: light toward warm yellow, shade toward cool violet."""
    hi = _hsv(_toward(h, .14, .12), s * .62, min(1, v * 1.1 + .1))
    base = _hsv(h, s, v)
    sh = _hsv(_toward(h, .72, .16), min(1, s * 1.1 + .1), v * .62)
    return hi, base, sh


def palette(hue, sat, val, acc_hue, acc_sat=.85):
    """Material -> 3 tones. Body: 3 tones; belly = lighter tones of the same hue; mark = darker body; accent: 1 hue."""
    hi, base, sh = ramp(hue, sat, val)
    light = _hsv(_toward(hue, .14, .2), sat * .32, 1.0)
    deep = _hsv(_toward(hue, .72, .2), min(1, sat * 1.1 + .1), val * .48)
    a_hi, a, a_sh = ramp(acc_hue, acc_sat, .97)
    P = np.zeros((8, 4, 3), np.uint8)
    P[BODY, :3] = (hi, base, sh)
    P[BELLY, :3] = (light, _hsv(_toward(hue, .14, .2), sat * .45, .97), hi)
    P[ACC, :3] = (a_hi, a, a_sh)
    P[MARK, :3] = (base, sh, deep)
    P[BONE, :3] = (_hsv(.12, .06, 1), _hsv(.11, .14, .96), _hsv(.08, .26, .78))
    P[DARK, :3] = (sh, deep, np.array(OUT, np.uint8))
    P[GLASS, :3] = (_hsv(acc_hue, .12, 1), _hsv(acc_hue, .3, 1), _hsv(_toward(acc_hue, .66, .1), .45, .9))
    P[GOLD, :3] = (_hsv(.15, .35, 1), _hsv(.12, .8, 1), _hsv(.07, .85, .78))
    # tone 3: specular glint, a near-white tint of the material's highlight
    P[:, 3] = (P[:, 0].astype(np.int16) + 2 * 255) // 3
    return P


class Part:
    __slots__ = ("kind", "a", "mat", "z", "name", "on", "line", "flat", "keep")

    def __init__(self, kind, a, mat, z, name, on=None, line=True, flat=False, keep=False):
        self.kind, self.a, self.mat, self.z, self.name = kind, a, mat, z, name
        self.on, self.line, self.flat, self.keep = on, line, flat, keep

    def bbox(self):
        k, a = self.kind, self.a
        if k == "E":
            cx, cy, rx, ry, rot = a
            r = max(rx, ry) if rot else None
            return (cx - (r or rx), cy - (r or ry), cx + (r or rx), cy + (r or ry))
        if k == "C":
            pts, rs = a
            return (min(p[0] - r for p, r in zip(pts, rs)), min(p[1] - r for p, r in zip(pts, rs)),
                    max(p[0] + r for p, r in zip(pts, rs)), max(p[1] + r for p, r in zip(pts, rs)))
        if k == "P":
            xs = [p[0] for p in a]; ys = [p[1] for p in a]
            return min(xs), min(ys), max(xs), max(ys)
        if k == "R":
            return a[:4]


class Builder:
    """Collects parts. `sym` adds the mirrored copy (x -> -x)."""

    def __init__(self):
        self.parts = []
        self.anchor = {}

    def flip(self):
        """Mirror the whole creature (3/4 plans face left by default)."""
        for p in self.parts:
            k, a = p.kind, p.a
            if k == "E":
                p.a = (-a[0], a[1], a[2], a[3], -a[4])
            elif k == "C":
                p.a = ([(-x, y) for x, y in a[0]], a[1])
            elif k == "P":
                p.a = [(-x, y) for x, y in a]
            elif k == "R":
                p.a = (-a[2], a[1], -a[0], a[3], a[4])

    def _add(self, kind, a, mat, z, name, sym, mirror_fn, **kw):
        self.parts.append(Part(kind, a, mat, z, name, **kw))
        if sym:
            self.parts.append(Part(kind, mirror_fn(a), mat, z, name, **kw))

    def E(self, cx, cy, rx, ry, mat=BODY, z=10, name="", sym=False, rot=0.0, **kw):
        self._add("E", (cx, cy, rx, ry, rot), mat, z, name, sym, lambda a: (-a[0], a[1], a[2], a[3], -a[4]), **kw)

    def C(self, pts, rs, mat=BODY, z=10, name="", sym=False, **kw):
        if not isinstance(rs, (list, tuple)):
            rs = [rs] * len(pts)
        self._add("C", (list(pts), list(rs)), mat, z, name, sym,
                  lambda a: ([(-x, y) for x, y in a[0]], a[1]), **kw)

    def P(self, pts, mat=BODY, z=10, name="", sym=False, **kw):
        self._add("P", list(pts), mat, z, name, sym, lambda a: [(-x, y) for x, y in a], **kw)

    def R(self, x0, y0, x1, y1, r=0.0, mat=BODY, z=10, name="", sym=False, **kw):
        kw.setdefault("flat", True)
        self._add("R", (x0, y0, x1, y1, r), mat, z, name, sym, lambda a: (-a[2], a[1], -a[0], a[3], a[4]), **kw)


# --- rasterisation ------------------------------------------------------------------------------------------
def _mask_normal(p, X, Y, s, need_n=True):
    """Boolean mask and (nx, ny, nz) normals for one part. s = px per design unit (for min sizes)."""
    k, a = p.kind, p.a
    half = .5 / s                    # half a pixel in design units
    if k == "E":
        cx, cy, rx, ry, rot = a
        rx = max(rx, half * 1.05); ry = max(ry, half * 1.05)
        dx, dy = X - cx, Y - cy
        if rot:
            c, sn = math.cos(rot), math.sin(rot)
            dx, dy = dx * c + dy * sn, -dx * sn + dy * c
        u, v = dx / rx, dy / ry
        q = u * u + v * v
        m = q <= 1.0
        nz = np.sqrt(np.clip(1 - q, 0, 1))
        if rot:
            c, sn = math.cos(rot), math.sin(rot)
            u, v = u * c - v * sn, u * sn + v * c
        return m, (u, v, nz)
    if k == "C":
        pts, rs = a
        es, us, vs = [], [], []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            r0, r1 = max(rs[i], half), max(rs[i + 1], half)
            ddx, ddy = x1 - x0, y1 - y0
            L2 = ddx * ddx + ddy * ddy + 1e-9
            t = np.clip(((X - x0) * ddx + (Y - y0) * ddy) / L2, 0, 1)
            px, py = X - (x0 + t * ddx), Y - (y0 + t * ddy)
            r = r0 + (r1 - r0) * t
            es.append(np.sqrt(px * px + py * py) - r)
            if need_n:
                us.append(px / r); vs.append(py / r)
        if len(es) == 1:
            e = es[0]
            if not need_n:
                return e <= 0, None
            u, v = us[0], vs[0]
        else:
            E = np.stack(es)
            if not need_n:
                return E.min(axis=0) <= 0, None
            j = E.argmin(axis=0)[None]
            e = np.take_along_axis(E, j, 0)[0]
            u = np.take_along_axis(np.stack(us), j, 0)[0]
            v = np.take_along_axis(np.stack(vs), j, 0)[0]
        m = e <= 0
        nz = np.sqrt(np.clip(1 - u * u - v * v, 0, 1))
        return m, (u, v, nz)
    if k == "P":
        m = np.zeros(X.shape, bool)
        n = len(a)
        for i in range(n):
            x0, y0 = a[i]; x1, y1 = a[(i + 1) % n]
            if y0 == y1:
                continue
            cond = ((y0 <= Y) & (Y < y1)) | ((y1 <= Y) & (Y < y0))
            xi = x0 + (Y - y0) * (x1 - x0) / (y1 - y0)
            m ^= cond & (X < xi)
        return m, None
    if k == "R":
        x0, y0, x1, y1, r = a
        cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        r = min(r, hx, hy)
        ddx = np.maximum(np.abs(X - cx) - hx + r, 0); ddy = np.maximum(np.abs(Y - cy) - hy + r, 0)
        return (ddx * ddx + ddy * ddy) <= r * r + 1e-6, None
    raise ValueError(k)


def _sh(m, dx, dy, fill=False):
    """value of m at (x+dx, y+dy)."""
    out = np.full_like(m, fill)
    H, W = m.shape
    ys0, ys1 = max(0, -dy), min(H, H - dy)
    xs0, xs1 = max(0, -dx), min(W, W - dx)
    out[ys0:ys1, xs0:xs1] = m[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
    return out


def _n4(m):
    return (_sh(m, 1, 0).astype(np.int8) + _sh(m, -1, 0) + _sh(m, 0, 1) + _sh(m, 0, -1))


T_HI, T_SH, T_SPEC = .80, .36, .965


def render(b: Builder, N: int, fill: float, accents=None, out_rgb=OUT, pal=None, n_base=None):
    """Rasterise builder `b` into an (N, N, 4) uint8 RGBA array. Returns (rgba, info)."""
    base = b.parts[:n_base] if n_base else b.parts
    parts = sorted(b.parts, key=lambda p: p.z)   # stable
    bbs = [p.bbox() for p in base if p.on is None]
    x0 = min(q[0] for q in bbs); y0 = min(q[1] for q in bbs)
    x1 = max(q[2] for q in bbs); y1 = max(q[3] for q in bbs)
    avail = N - 4
    s = min(fill * avail / (y1 - y0), avail / (x1 - x0))
    # accessories never shrink the body more than a little (they may not leave the canvas, though)
    allb = [p.bbox() for p in parts if p.on is None]
    ax0 = min(q[0] for q in allb); ay0 = min(q[1] for q in allb); ax1 = max(q[2] for q in allb)
    s = min(s, (N - 3) / (y1 - ay0) if ay0 < y0 else s, avail / max(x1 - x0, ax1 - ax0) * 1.08)
    x0, x1 = min(x0, ax0), max(x1, ax1)
    ox = int(round(N / 2 - s * (x0 + x1) / 2))
    # keep exact mirror symmetry when the bbox is only slightly off-centre
    if abs(ox - N / 2) <= 2 and (N / 2 + s * x1) <= N - 2 and (N / 2 + s * x0) >= 2:
        ox = N // 2
    oy = N - 1 - s * y1   # lowest point lands on the row above the bottom outline
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    X = ((xx + .5 - ox) / s).astype(np.float32)
    Y = ((yy + .5 - oy) / s).astype(np.float32)

    mat = np.full((N, N), -1, np.int8)
    tone = np.ones((N, N), np.int8)
    pid = np.full((N, N), -1, np.int16)
    keep = np.zeros((N, N), bool)
    names = []
    lines = []
    name_ids = {}
    for i, p in enumerate(parts):
        # rasterise only inside the part's pixel bbox (+2 px for the rim tests)
        bx0, by0, bx1, by1 = p.bbox()
        px0 = max(0, int(ox + bx0 * s) - 2); px1 = min(N, int(ox + bx1 * s) + 3)
        py0 = max(0, int(oy + by0 * s) - 2); py1 = min(N, int(oy + by1 * s) + 3)
        if px0 >= px1 or py0 >= py1:
            names.append(p.name)
            continue
        win = (slice(py0, py1), slice(px0, px1))
        ms, nrm = _mask_normal(p, X[win], Y[win], s, need_n=p.on is None and not p.flat)
        pidw, tonew, matw, keepw = pid[win], tone[win], mat[win], keep[win]   # views
        if p.on is not None:          # patch: recolour pixels already owned by the named parts
            ids = [j for j, nm in enumerate(names) if nm in p.on]
            msk = ms & np.isin(pidw, ids)
            matw[msk] = p.mat
            if p.flat:
                tonew[msk] = 1
            names.append(p.name)
            continue
        if not ms.any():
            names.append(p.name)
            continue
        ts = np.ones(ms.shape, np.int8)
        if nrm is None or p.flat:
            ts[ms & ~_sh(ms, 1, 1)] = 2          # bottom-right rim
            ts[ms & ~_sh(ms, -1, -1) & _sh(ms, 1, 1)] = 0  # top-left rim
        else:
            u, v, nz = nrm
            d = u * LIGHT[0] + v * LIGHT[1] + nz * LIGHT[2]
            ts[d > T_HI] = 0
            ts[d < T_SH] = 2
            if p.kind == "E" and min(p.a[2], p.a[3]) * s >= 3.5 and p.mat != DARK:
                ts[(d > T_SPEC) & ms] = 3
        matw[ms] = p.mat
        tonew[ms] = ts[ms]
        pidw[ms] = i
        keepw[ms] = p.keep
        names.append(p.name)
        if p.line:
            lines.append(i)
    occ = mat >= 0
    # contact shadow: pixels right under a part drawn in front of theirs
    above = _sh(pid, 0, -1, -1)
    tone[(pid >= 0) & (above > pid)] = 2

    # --- cleanup: orphans and 1px slivers (except parts marked keep, e.g. horn tips)
    for _ in range(2):
        n4 = _n4(occ)
        kill = occ & (n4 == 0) | (occ & (n4 <= 1) & ~keep)
        if not kill.any():
            break
        occ &= ~kill
        mat[kill] = -1; pid[kill] = -1
    hole = ~occ & (_n4(occ) >= 3)
    if hole.any():                       # pinholes: take the upper/left neighbour's material
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            src = hole & (_sh(mat, dx, dy, -1) >= 0)
            mat[src] = _sh(mat, dx, dy, -1)[src]
            tone[src] = _sh(tone, dx, dy, 1)[src]
            pid[src] = _sh(pid, dx, dy, -1)[src]
            hole &= ~src
        occ = mat >= 0

    # --- tone cleanup: lonely highlight/shade pixels revert to base
    for tv in (0, 2):
        tm = occ & (tone == tv)
        same = (_sh(tm, 1, 0).astype(np.int8) + _sh(tm, -1, 0) + _sh(tm, 0, 1) + _sh(tm, 0, -1))
        tone[tm & (same == 0)] = 1

    rgb = np.zeros((N, N, 3), np.uint8)
    mo = np.where(occ, mat, 0)
    rgb[:] = pal[mo, tone]

    # --- selective inner lines: edge of a front part where it overlaps a different, earlier part
    nparts = len(names)
    uniq = {}
    name_id = np.array([uniq.setdefault(nm, len(uniq)) for nm in names] + [-1])
    is_line = np.zeros(nparts + 1, bool)
    is_line[lines] = True
    counts = np.bincount(pid[pid >= 0].ravel(), minlength=nparts + 1)
    is_line &= np.append(counts[:nparts] >= 6, False)
    pp = np.where(pid >= 0, pid, nparts)          # -1 -> sentinel index
    front = is_line[pp]
    inner = np.zeros((N, N), bool)
    same = {}
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        o = _sh(pid, dx, dy, -1)
        oo = np.where(o >= 0, o, nparts)
        same[(dx, dy)] = o == pid
        inner |= front & (o >= 0) & (o < pid) & ((_sh(mat, dx, dy, -1) != mat) | (name_id[oo] != name_id[pp]))
    thick = same[(1, 0)] & same[(-1, 0)] | same[(0, 1)] & same[(0, -1)]
    inner &= thick
    if inner.any():
        # darker of the two tones, pulled toward the outline: a softer line than the silhouette
        base = pal[mo, 2].astype(np.int16)
        mix = (base * 4 + np.array(out_rgb) * 6) // 10
        rgb[inner] = mix[inner].astype(np.uint8)

    # --- silhouette outline (4-neighbour)
    ring = ~occ & (_n4(occ) > 0)
    a = np.zeros((N, N, 4), np.uint8)
    a[occ, :3] = rgb[occ]
    a[occ, 3] = 255
    a[ring, :3] = out_rgb
    a[ring, 3] = 255

    def to_px(x, y):
        return x * s + ox, y * s + oy
    return a, dict(s=s, ox=ox, oy=oy, to_px=to_px, pid=pid, names=names, occ=occ)
