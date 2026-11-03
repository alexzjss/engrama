"""Animation frames: face templates + whole-sprite transforms (reuses the M6 transform helpers)."""
from engrama.app.art.vpet.anim import ANIM_FRAMES, _color, _lean, _lie, _rows, _shift, _squash, _zs

from .face import stamp_face
from .gen import sprite


def frame_arrays(sp, anim):
    out = []
    for p in ANIM_FRAMES[anim]:
        a = stamp_face(sp.body.copy(), sp.face, p.get("eyes", "normal"), p.get("mouth", "normal"), p.get("tear", 0))
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


def frames(seed, stage, anim, **kw):
    return frame_arrays(sprite(seed, stage, **kw), anim)
