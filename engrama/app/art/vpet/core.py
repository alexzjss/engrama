"""Core: palette, canvas (28-grid coords), shading, outline, eyes. Original procedural V-Pet style art."""
import colorsys
import math
import random
import zlib

import numpy as np

OUT = (42, 26, 18)
STAGES = ("baby", "child", "adult", "perfect", "final")
PX = (24, 32, 40, 44, 48)  # canvas size per stage index


def toward(h, t, f):
    d = ((t - h + .5) % 1) - .5
    return (h + d * f) % 1


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1, max(0, min(1, s)), max(0, min(1, v)))
    return (round(r * 255), round(g * 255), round(b * 255))


def ramp(h, s, v):
    base = hsv(h, s, v)
    sh = hsv(toward(h, .74, .14), s * 1.05 + .1, v * .64)
    hl = hsv(toward(h, .13, .2), s * .55, min(1, v * 1.08 + .1))
    return (base, hl, sh)  # tone 0 base, 1 highlight, 2 shade


ARCH_COL = {  # arch: (target hue, mix, s mul, v mul)
    "plant": (.31, .6, 1.0, .95), "ghost": (None, 0, .5, 1.0), "stack": (.55, .35, .6, 1.0),
    "robot": (None, 0, .6, .95), "golem": (.55, .2, .5, .9), "fish": (.55, .3, 1.0, 1.0),
    "serpent": (.3, .25, 1.0, .98),
}


def mkpal(g, branch, arch, shift=0.0):
    h, s, v = g["hue"], g["sat"], g["val"]
    h = (h + shift) % 1
    if branch == "sombrio": h = toward(h, .78, .3); s = min(1, s * .95); v *= .66
    elif branch == "lendario": s *= .8; v = min(1, v * 1.05 + .05)
    elif branch == "companheiro": h = toward(h, .05, .2)
    elif branch == "tecnico": h = toward(h, .55, .35); s *= .85
    elif branch == "artista": s = min(1, s * 1.1)
    elif branch == "explorador": h = toward(h, .1, .15)
    ov = ARCH_COL.get(arch)
    if ov:
        th, mix, sm, vm = ov
        if th is not None: h = toward(h, th, mix)
        s = min(1, s * sm); v = min(1, v * vm)
    off = (1 / 3 if g.get("tri") else .5) * (1 if g["seed"] % 2 else -1)
    acc_h = {"sombrio": .96, "lendario": .12, "companheiro": .0, "tecnico": .5, "explorador": .62}.get(branch, h + off)
    P = {}
    P["body"] = ramp(h, s, v)
    P["body2"] = ramp(h + .03, min(1, s + .1), v * .7)
    P["belly"] = ramp(toward(h, acc_h, .25), .32 if arch != "ghost" else .18, 1.0)
    P["acc"] = ramp(acc_h, .88, 1.0 if branch != "sombrio" else .9)
    P["acc2"] = ramp(h + (.33 if off > 0 else -.33), .8, 1.0)
    P["glow"] = ramp(acc_h, .5, 1.0)
    P["metal"] = ramp(toward(h, .6, .5), .24, .86)
    P["bone"] = ramp(.11, .25, 1.0)
    P["gold"] = ramp(.13, .9, 1.0)
    P["dark"] = ramp(h, .5, .34)
    P["white"] = ((250, 250, 245), (255, 255, 255), (196, 204, 240))
    P["leaf"] = ramp(.30, .75, .78)
    P["wood"] = ramp(.07, .7, .6)
    P["red"] = ramp(0.0, .85, .92)
    P["ice"] = ramp(.55, .3, 1.0)
    return P


class V:  # variation bundle
    def __init__(s, g, t, branch, arch, bid="base"):
        s.g = g; s.t = t; s.branch = branch; s.arch = arch; s.bid = bid
        s.ears = g["ears"]; s.tail = g["tail"]; s.body = g["body"]; s.pat = g["pattern"]; s.eyes = g["eyes"]
        s.rng = random.Random(g["seed"] * 31 + zlib.crc32(arch.encode()) % 977 + t)


class Canvas:
    def __init__(s, N, pal, v):
        s.N = N; s.f = N / 28; s.pal = pal; s.v = v
        s.pid = np.full((N, N), -1, np.int16); s.ov = np.full((N, N), -1, np.int16)
        s.parts = []; s.pk = []
        s.keys = list(pal.keys())
        s.yy, s.xx = np.mgrid[0:N, 0:N].astype(float) + .5
        s.eyes = []; s.marks = []; s.mouths = []
        s.head = (14, 8, 5, 5); s.neck = (14, 13, 8)
        s.eyekind = None; s.eyeiris = None
        s.sx = s.sy = 1.0

    # ---- masks (28-grid coordinates)
    def tx(s, x): return 14 + (x - 14) * s.sx
    def ty(s, y): return 26.5 - (26.5 - y) * s.sy

    def mE(s, cx, cy, rx, ry, rot=0, hole=0, clip=None, clipx=None):
        cx, cy, rx, ry = s.tx(cx), s.ty(cy), rx * s.sx, ry * s.sy
        if clip is not None: clip = s.ty(clip)
        if clipx is not None: clipx = s.tx(clipx)
        f = s.f; dx = s.xx - cx * f; dy = s.yy - cy * f
        if rot:
            c, sn = math.cos(rot), math.sin(rot); dx, dy = dx * c + dy * sn, -dx * sn + dy * c
        q = (dx / (rx * f)) ** 2 + (dy / (ry * f)) ** 2
        m = q <= 1.06
        if hole: m &= q >= hole * hole
        if clip is not None: m &= s.yy <= clip * f
        if clipx is not None: m &= s.xx <= clipx * f
        return m

    def mR(s, x0, y0, x1, y1, r=0):
        x0, x1, y0, y1 = s.tx(x0), s.tx(x1), s.ty(y0), s.ty(y1); r *= (s.sx + s.sy) / 2
        f = s.f; cx, cy = (x0 + x1) / 2 * f, (y0 + y1) / 2 * f
        hx, hy = (x1 - x0) / 2 * f, (y1 - y0) / 2 * f
        r = min(r * f, hx, hy)
        if r <= 0:
            return (np.abs(s.xx - cx) <= hx) & (np.abs(s.yy - cy) <= hy)
        dx = np.maximum(np.abs(s.xx - cx) - hx + r, 0); dy = np.maximum(np.abs(s.yy - cy) - hy + r, 0)
        return (dx * dx + dy * dy) <= r * r + .6

    def mP(s, pts):
        pts = [(s.tx(x), s.ty(y)) for x, y in pts]
        f = s.f; P = [(x * f, y * f) for x, y in pts]; m = np.zeros((s.N, s.N), bool)
        for i in range(len(P)):
            x0, y0 = P[i]; x1, y1 = P[(i + 1) % len(P)]
            if y0 == y1: continue
            cond = ((y0 <= s.yy) & (s.yy < y1)) | ((y1 <= s.yy) & (s.yy < y0))
            xi = x0 + (s.yy - y0) * (x1 - x0) / (y1 - y0)
            m ^= cond & (s.xx < xi)
        return m

    def mL(s, x0, y0, x1, y1, w0, w1=None):
        x0, x1, y0, y1 = s.tx(x0), s.tx(x1), s.ty(y0), s.ty(y1); k = (s.sx + s.sy) / 2
        f = s.f; w1 = w0 if w1 is None else w1; w0 *= k; w1 *= k
        ax, ay, bx, by = x0 * f, y0 * f, x1 * f, y1 * f
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((s.xx - ax) * dx + (s.yy - ay) * dy) / L2, 0, 1)
        d = np.hypot(s.xx - (ax + t * dx), s.yy - (ay + t * dy))
        return d <= (w0 + (w1 - w0) * t) * f / 2 + .12

    def put(s, m, key, line=True):
        i = len(s.parts); s.parts.append((key, line)); s.pk.append(s.keys.index(key)); s.pid[m] = i

    def paint(s, m, key, only=None):
        pk = np.array(s.pk + [-1])
        cur = np.where(s.ov >= 0, s.ov, pk[s.pid])
        ok = m & (s.pid >= 0)
        if only is not None: ok &= (cur == s.keys.index(only))
        s.ov[ok] = s.keys.index(key)

    def _emit(s, m, key, line, paint, only):
        s.paint(m, key, only) if paint else s.put(m, key, line)

    def E(s, cx, cy, rx, ry, key, mir=False, mx=14, line=True, paint=False, only=None, **kw):
        for sgn in ((1, -1) if mir else (1,)):
            x = cx if sgn == 1 else 2 * mx - cx
            k = dict(kw)
            if sgn == -1 and "rot" in k: k["rot"] = -k["rot"]
            s._emit(s.mE(x, cy, rx, ry, **k), key, line, paint, only)

    def R(s, x0, y0, x1, y1, key, mir=False, mx=14, line=True, paint=False, only=None, r=0):
        for sgn in ((1, -1) if mir else (1,)):
            a, b = (x0, x1) if sgn == 1 else (2 * mx - x1, 2 * mx - x0)
            s._emit(s.mR(a, y0, b, y1, r), key, line, paint, only)

    def P(s, pts, key, mir=False, mx=14, line=True, paint=False, only=None):
        for sgn in ((1, -1) if mir else (1,)):
            p = pts if sgn == 1 else [(2 * mx - x, y) for x, y in pts]
            s._emit(s.mP(p), key, line, paint, only)

    def L(s, x0, y0, x1, y1, w, key, w1=None, mir=False, mx=14, line=True, paint=False, only=None):
        for sgn in ((1, -1) if mir else (1,)):
            a, b = (x0, x1) if sgn == 1 else (2 * mx - x0, 2 * mx - x1)
            s._emit(s.mL(a, y0, b, y1, w, w1), key, line, paint, only)

    def chain(s, pts, key, mir=False, mx=14, line=True, paint=False, only=None):
        """pts: [(x,y,w)...] thick polyline; drawn as one merged part"""
        m = np.zeros((s.N, s.N), bool)
        for sgn in ((1, -1) if mir else (1,)):
            m = np.zeros((s.N, s.N), bool)
            for a, b in zip(pts, pts[1:]):
                ax, bx = (a[0], b[0]) if sgn == 1 else (2 * mx - a[0], 2 * mx - b[0])
                m |= s.mL(ax, a[1], bx, b[1], a[2], b[2])
            s._emit(m, key, line, paint, only)

    # ---- face
    def eyepair(s, cx, cy, half, big=True):
        cx, cy, half = s.tx(cx), s.ty(cy), half * s.sx
        s.eyes.append((cx - half, cy, -1, big)); s.eyes.append((cx + half, cy, 1, big))

    def eye1(s, x, y, side=-1, big=True):
        x, y = s.tx(x), s.ty(y)
        s.eyes.append((x, y, side, big))

    def mouth(s, x, y, w):
        s.mouths.append((s.tx(x), s.ty(y), w * s.sx))

    def mark(s, x, y, key="dark", tone=0):
        x, y = s.tx(x), s.ty(y)
        s.marks.append((x, y, key, tone))

    # ---- render
    def render(s):
        """Body only (no eyes/mouth/marks): see face()."""
        N = s.N; pid = s.pid; filled = pid >= 0
        pk = np.array(s.pk + [0])
        keyg = np.where(s.ov >= 0, s.ov, pk[pid]); keyg = np.where(filled, keyg, -1)
        pl = np.array([p[1] for p in s.parts] + [False])

        def sh(a, dx, dy, fill):  # value at (x+dx, y+dy)
            out = np.full_like(a, fill)
            ys0, ys1 = max(0, -dy), N - max(0, dy); xs0, xs1 = max(0, -dx), N - max(0, dx)
            out[ys0:ys1, xs0:xs1] = a[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            return out
        P = lambda dx, dy: sh(pid, dx, dy, -1)
        exp = lambda dx, dy: (P(dx, dy) < pid)         # empty or behind
        front = lambda dx, dy: (P(dx, dy) > pid)
        cnt = np.bincount(pid[filled], minlength=len(s.parts) + 1).astype(float)
        sx = np.bincount(pid[filled], weights=s.xx[filled], minlength=len(s.parts) + 1)
        sy = np.bincount(pid[filled], weights=s.yy[filled], minlength=len(s.parts) + 1)
        cx = (sx / np.maximum(cnt, 1))[pid]; cy = (sy / np.maximum(cnt, 1))[pid]
        big = (cnt[pid] > 40)
        lowr = (s.xx + s.yy) > (cx + cy) + .5
        upl = (s.xx + s.yy) <= (cx + cy) - .5
        hl = filled & upl & (exp(0, -1) | exp(-1, 0))
        shd = filled & lowr & (exp(0, 1) | exp(1, 0) | (big & exp(1, 1)))
        shd |= filled & (front(0, -1) | front(-1, 0)) & ~upl
        if N >= 40:
            shd |= filled & lowr & big & exp(2, 2); hl |= filled & upl & big & exp(-1, -1)
        hl &= ~shd
        tone = np.where(shd, 2, np.where(hl, 1, 0))
        for _ in range(2):  # remove isolated tone pixels
            same = np.zeros((N, N), int)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        same += ((sh(tone, dx, dy, -9) == tone) & (P(dx, dy) == pid)).astype(int)
            tone = np.where(filled & (tone > 0) & (same == 0), 0, tone)
        rgb = np.zeros((N, N, 4), np.uint8)
        for ki, kname in enumerate(s.keys):
            m = filled & (keyg == ki)
            for t in range(3):
                mm = m & (tone == t)
                if mm.any(): rgb[mm, :3] = s.pal[kname][t]; rgb[mm, 3] = 255
        ln = np.zeros((N, N), bool)  # internal lines
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nb = P(dx, dy)
            ln |= filled & (nb > pid) & pl[pid] & pl[np.clip(nb, 0, None)] & (cnt[pid] > 7)
        rgb[ln, :3] = OUT
        outl = ~filled & (sh(filled, 1, 0, False) | sh(filled, -1, 0, False) | sh(filled, 0, 1, False) | sh(filled, 0, -1, False))
        rgb[outl, :3] = OUT; rgb[outl, 3] = 255
        return rgb


    # ---- face (eyes, mouth, marks) drawn over the body render; modes change eyes/mouth for animations
    T = {
        ("cute", "t"): ["WK", "KK"], ("cute", "s"): ["WK", "KK", "KK"], ("cute", "l"): ["WKK", "KKK", "KKK"],
        ("white", "t"): ["WK", "KK"], ("white", "s"): ["WW", "WK", "WK"], ("white", "l"): ["WWW", "WKK", "WKK"],
        ("round", "t"): ["WK", "WK"], ("round", "s"): ["WWK", "WKK", "WWK"], ("round", "l"): [".WW.", "WKKW", "WKKW", ".WW."],
        ("fierce", "t"): ["BB", "WI"], ("fierce", "s"): ["BB.", "WIB", "WI."], ("fierce", "l"): ["BBB.", "WIIB", "WIK."],
        ("led", "t"): ["LL"], ("led", "s"): ["LLL", "LLL"], ("led", "l"): ["LLLL", "LLLL"],
        ("cute", "x"): ["WWKK", "WKKK", "KKKK", "KKKK", ".KK."], ("white", "x"): ["WWWW", "WKKW", "WKKK", "WKKK", ".WW."],
        ("round", "x"): [".WWW.", "WWKKW", "WKKKW", "WWKKW", ".WWW."], ("fierce", "x"): ["BBBB.", "WIIIB", "WIKKB", "WIKI.", ".WI.."],
        ("led", "x"): ["LLLLL", "LLLLL"],
    }

    def eye_cells(s):
        """Eye centres in pixels (x, y, side, big) of the canvas, for visibility checks."""
        return [(int(x * s.f), int(y * s.f), side, big) for x, y, side, big in s.eyes]

    def _rows(s, kind, big, mode):
        N = s.N
        key = ("x" if N >= 40 else ("l" if N >= 32 else "s")) if big else ("s" if N >= 40 else "t")
        rows = s.T[(kind, key)]
        w = len(rows[0])
        if mode == "closed":
            return ["K" * w]
        if mode == "happy":
            if w == 2:
                return ["KK"]
            return ["." + "K" * (w - 2) + ".", "K" + "." * (w - 2) + "K"]
        if mode == "sad":
            r = ["B" * w] + [x for x in rows[1:]] if len(rows) > 1 else ["B" * w, "K" * w]
            return r
        if mode == "sick":
            r = ["B" * w] + [x.replace("W", "S") for x in rows[1:]] if len(rows) > 1 else ["B" * w, "S" * w]
            return r
        if mode == "dead":
            return ["K.K", ".K.", "K.K"]
        return rows

    def face(s, rgb, mode="normal", mouth="normal", tear=0, ox=0, oy=0):
        """Draw eyes/mouth/marks onto rgb (modified in place). ox/oy: pixel offset of the body inside the canvas."""
        N = s.N; v = s.v
        kind = s.eyekind or ["cute", "white", "round", "fierce"][v.eyes]
        if v.branch == "sombrio" and kind != "led": kind = "fierce"
        if v.branch == "companheiro" and kind == "fierce": kind = "cute"
        iris = s.eyeiris or {"sombrio": (255, 70, 50), "lendario": (255, 200, 40)}.get(v.branch, s.pal["acc"][2])
        cols = {"K": (30, 18, 36), "W": (255, 255, 255), "B": OUT, "I": iris, "L": s.pal["acc"][1],
                "S": (190, 215, 130)}
        lum = lambda c: .3 * c[0] + .59 * c[1] + .11 * c[2]

        def put(xx, yy, c):
            if 0 <= xx < N and 0 <= yy < N:
                rgb[yy, xx, :3] = c; rgb[yy, xx, 3] = 255

        for x, y, side, big in s.eyes:
            ex, ey = int(x * s.f) + ox, int(y * s.f) + oy
            kk = kind
            win = rgb[max(0, ey - 2):ey + 3, max(0, ex - 3):ex + 4]
            opq = win[:, :, 3] > 0
            dark = bool(opq.any()) and lum(win[opq][:, :3].mean(axis=0)) < 105
            if dark and kind == "cute":
                kk = "white"
            if dark and mode in ("happy", "closed", "dead"):
                cols["K"] = (245, 245, 252)   # dark body: ink lines drawn light so the eyes stay visible
            tp = s._rows(kk, big, mode)
            h = len(tp); w = len(tp[0])
            px = int(round(x * s.f - w / 2)) + ox; py = int(round(y * s.f - h / 2)) + oy
            for j, row in enumerate(tp):
                r = row if side == -1 else row[::-1]
                for i, ch in enumerate(r):
                    if ch not in " .":
                        put(px + i, py + j, cols[ch])
            if mode == "sad" and tear:
                tx = px + (0 if side == -1 else w - 1)
                put(tx, py + h + tear - 1, (130, 200, 255))
                if N >= 40: put(tx, py + h + tear, (130, 200, 255))
            cols["K"] = (30, 18, 36)
        mk = v.g.get("mouth", 0)
        mouths = s.mouths
        if not mouths and mouth != "normal" and s.head:
            hx, hy, rx, ry = s.head
            mouths = [(hx, hy + ry * .55, max(2.4, rx * .8))]
        red, wh = (200, 50, 70), (255, 255, 255)
        for x, y, w in mouths:
            x0 = int(round((x - w / 2) * s.f)) + ox; x1 = int(round((x + w / 2) * s.f)) + ox; yy = int(round(y * s.f)) + oy
            if x1 - x0 < 2: x1 = x0 + 2
            if mouth == "none":
                continue
            if mouth == "open":      # eating: wide dark mouth with a red tongue
                for xx in range(x0, x1):
                    put(xx, yy, OUT); put(xx, yy + 1, red); put(xx, yy + 2, OUT)
                put(x0, yy + 1, OUT); put(x1 - 1, yy + 1, OUT)
                continue
            if mouth == "chew":      # small bite
                for xx in range(x0 + 1, x1 - 1): put(xx, yy, OUT); put(xx, yy + 1, red) if x1 - x0 > 3 else None
                continue
            if mouth == "frown":
                for xx in range(x0 + 1, x1 - 1): put(xx, yy, OUT)
                put(x0, yy + 1, OUT); put(x1 - 1, yy + 1, OUT)
                continue
            if mouth == "wavy":
                for i, xx in enumerate(range(x0, x1)): put(xx, yy + (i % 2), OUT)
                continue
            if mouth == "smile":
                mk2 = 0
            elif mouth == "line":
                mk2 = 9
            else:
                mk2 = mk
            if mk2 == 0:    # smile
                for xx in range(x0 + 1, x1 - 1): put(xx, yy, OUT)
                put(x0, yy - 1, OUT); put(x1 - 1, yy - 1, OUT)
            elif mk2 == 1:  # fangs
                for xx in range(x0, x1): put(xx, yy, OUT)
                put(x0 + 1, yy + 1, wh); put(x1 - 2, yy + 1, wh)
            elif mk2 == 2:  # open
                for xx in range(x0 + 1, x1 - 1):
                    put(xx, yy, OUT); put(xx, yy + 1, red)
                if N >= 40: put(x0 + 1, yy - 1, wh)
            elif mk2 == 9:
                for xx in range(x0, x1): put(xx, yy, OUT)
            else:          # flat with tooth
                for xx in range(x0, x1): put(xx, yy, OUT)
                put(x0 + 1, yy + 1, wh)
        for x, y, key, tone in s.marks:
            xx, yy = int(round(x * s.f - .5)) + ox, int(round(y * s.f - .5)) + oy
            put(xx, yy, OUT if key == "dark" else s.pal[key][tone])
