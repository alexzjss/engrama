"""Animations: face stamps (face.py) plus whole-sprite transforms (shift, squash, lean, tint, fade, lie). No limb
animation."""
import numpy as np

from .core import OUT, posed, render
from .face import stamp_face
from .gen import Sprite

# per-frame params: eyes (normal|closed|happy|sad|sick|dead), mouth (normal|none|open|chew|line|smile|frown|wavy),
# tear (0-2), dy (px, up is negative), sq (vertical scale), lean (px at the top), tint, gray, bright, fade, lie, z (0-2)
ANIM_FRAMES = {
    "idle": [{}, {"sq": .95}],
    "walk": [{"lean": 1}, {"dy": -1}, {"lean": -1}, {"dy": -1}],
    "eat": [{"mouth": "line"}, {"mouth": "open", "sq": .96}, {"mouth": "chew"}],
    "sleep": [{"eyes": "closed", "mouth": "none", "z": 1}, {"eyes": "closed", "mouth": "none", "sq": .95, "z": 2}],
    "happy": [{"eyes": "happy", "mouth": "smile"}, {"eyes": "happy", "mouth": "smile", "dy": -1}],
    "sad": [{"eyes": "sad", "mouth": "frown", "tear": 1, "sq": .97}, {"eyes": "sad", "mouth": "frown", "tear": 2}],
    "sick": [{"eyes": "sick", "mouth": "wavy", "tint": True}, {"eyes": "sick", "mouth": "wavy", "tint": True,
                                                              "sq": .95, "lean": 1}],
    "evolve": [{"eyes": "closed", "mouth": "none", "bright": b} for b in (.2, .45, .7, .92)],
    "old": [{"lean": 1, "sq": .96, "gray": .22, "mouth": "none"},
            {"lean": 1, "sq": .96, "gray": .22, "mouth": "none", "eyes": "closed"}],
    "jump": [{"eyes": "happy", "mouth": "smile", "sq": .9},
             {"eyes": "happy", "mouth": "open", "dy": -3},
             {"eyes": "happy", "mouth": "open", "dy": -5},
             {"eyes": "happy", "mouth": "smile", "dy": -2}],
    "dance": [{"eyes": "happy", "mouth": "smile", "lean": 2, "dy": -1},
              {"eyes": "happy", "mouth": "open", "sq": .94},
              {"eyes": "happy", "mouth": "smile", "lean": -2, "dy": -1},
              {"eyes": "happy", "mouth": "open", "sq": .94}],
    "yawn": [{"sq": .97},
             {"eyes": "closed", "mouth": "open", "dy": -1},
             {"eyes": "closed", "mouth": "open", "dy": -2, "lean": 1},
             {"eyes": "closed", "mouth": "open", "sq": .96}],
    "dig": [{"mouth": "line", "lean": 2, "sq": .92},
            {"mouth": "line", "lean": 3, "sq": .88},
            {"mouth": "line", "lean": 1, "dy": -1}],
    "dead": [{"lie": True, "eyes": "dead", "mouth": "none", "gray": .3, "fade": .85},
             {"lie": True, "eyes": "dead", "mouth": "none", "gray": .4, "fade": .5}],
}

_Z4 = ["ZZZ", "..Z", ".Z.", "ZZZ"]
_Z5 = ["ZZZ", "..Z", ".Z.", "Z..", "ZZZ"]


def _rows(a):
    ys = np.nonzero(a[:, :, 3].any(axis=1))[0]
    return int(ys[0]), int(ys[-1])


def _shift(a, dx, dy):
    if not dx and not dy:
        return a
    n = a.shape[0]
    out = np.zeros_like(a)
    ys0, ys1 = max(0, -dy), min(n, n - dy)
    xs0, xs1 = max(0, -dx), min(n, n - dx)
    out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = a[ys0:ys1, xs0:xs1]
    return out


def _squash(a, f):
    """Scale content vertically by f (<1), keeping the feet on the ground."""
    y0, y1 = _rows(a)
    h = y1 - y0 + 1
    nh = max(2, int(round(h * f)))
    src = y0 + np.minimum(h - 1, (np.arange(nh) * h / nh).astype(int))
    out = np.zeros_like(a)
    out[y1 - nh + 1:y1 + 1] = a[src]
    return out


def _lean(a, px):
    """Shear: the top moves `px` pixels sideways, the feet stay."""
    y0, y1 = _rows(a)
    h = max(1, y1 - y0)
    out = np.zeros_like(a)
    n = a.shape[0]
    for y in range(y0, y1 + 1):
        d = int(round(px * (y1 - y) / h))
        row = a[y]
        if d > 0:
            out[y, d:] = row[:n - d]
        elif d < 0:
            out[y, :n + d] = row[-d:]
        else:
            out[y] = row
    return out


def _lie(a):
    """Lie on the side (head to the left), resting on the bottom row."""
    n = a.shape[0]
    r = np.rot90(a, 1).copy()
    ys = np.nonzero(r[:, :, 3].any(axis=1))[0]
    xs = np.nonzero(r[:, :, 3].any(axis=0))[0]
    dy = (n - 1) - int(ys[-1])
    dx = int(round((n - 1) / 2 - (xs[0] + xs[-1]) / 2))
    return _shift(r, dx, dy)


def _zs(a, level):
    n = a.shape[0]
    zz = _Z5 if n >= 40 else _Z4
    h, w = len(zz), len(zz[0])
    spots = [(n - w - 3, 2)] if level == 1 else [(n - w - 3, 2), (n - 2 * w - 6, 2 + h + 1)]
    ink = np.zeros((n, n), bool)
    for x, y in spots:
        for j, row in enumerate(zz):
            for k, ch in enumerate(row):
                if ch == "Z" and 0 <= x + k < n and 0 <= y + j < n:
                    ink[y + j, x + k] = True
    rim = np.zeros_like(ink)
    rim[1:] |= ink[:-1]; rim[:-1] |= ink[1:]; rim[:, 1:] |= ink[:, :-1]; rim[:, :-1] |= ink[:, 1:]
    rim &= ~ink
    a[rim] = (*OUT, 255)
    a[ink] = (235, 242, 255, 255)
    return a


def _color(a, p):
    rgb = a[:, :, :3].astype(float)
    alpha = a[:, :, 3].astype(float)
    if p.get("tint"):
        isout = (a[:, :, :3] == np.array(OUT)).all(axis=2)
        mixed = rgb * .55 + np.array((130, 190, 100)) * .45
        rgb = np.where(isout[:, :, None], rgb, mixed)
    g = p.get("gray", 0)
    if g:
        rgb = rgb * (1 - g) + 140 * g
    b = p.get("bright", 0)
    if b:
        rgb = rgb + (255 - rgb) * b
    f = p.get("fade", 1.0)
    out = np.zeros_like(a)
    out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[:, :, 3] = (alpha * f).astype(np.uint8)
    return out


# M14 pose data, filled by the family modules: key (family, plan) or family -> {anim: [pose per frame]}.
# A pose is {role: {"rot", "dx", "dy", "alt"}} (see core.posed); {} = rest.
POSES: dict = {}


def poses_for(sp: Sprite, anim: str):
    """Resolution order: (family, plan) -> family -> None."""
    for key in ((sp.family, sp.plan), sp.family):
        got = POSES.get(key, {}).get(anim)
        if got:
            return got
    return None


def _body(sp: Sprite, pose):
    if not pose:
        return sp.body
    bd = sp._build
    return render(posed(bd.builder, pose, bd.s), bd.n, bd.fill, pal=bd.pal, n_base=bd.n_base, drop=bd.drop)[0]


def frame_arrays(sp: Sprite, anim: str, poses=None) -> list:
    """`poses`: None or one pose per frame of ANIM_FRAMES[anim] (empty pose = rest body, bit-identical)."""
    frames = ANIM_FRAMES[anim]
    if poses is not None and len(poses) != len(frames):
        raise ValueError(f"{anim}: {len(poses)} poses for {len(frames)} frames")
    out = []
    for i, p in enumerate(frames):
        a = stamp_face(_body(sp, poses[i] if poses else None).copy(), sp.face, p.get("eyes", "normal"),
                       p.get("mouth", "normal"), p.get("tear", 0))
        if p.get("sq"):
            a = _squash(a, p["sq"])
        if p.get("lean"):
            a = _lean(a, p["lean"])
        if p.get("dy"):
            top = _rows(a)[0]
            a = _shift(a, 0, max(int(p["dy"] * (2 if sp.n >= 40 else 1)), -top))
        if p.get("lie"):
            a = _lie(a)
        a = _color(a, p)
        if p.get("z"):
            a = _zs(a, p["z"])
        out.append(a)
    return out
