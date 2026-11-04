"""M14 T1: pose engine (part roles, pivots, posed render)."""
import copy
import math

import numpy as np
import pytest

from engrama.app.art.vpet import anim, gen
from engrama.app.art.vpet.core import BODY, Builder, palette, posed, render
from engrama.app.art.vpet.gen import STAGES

from tests.app.test_sprite_golden import SEEDS

PAL = palette(.3, .6, .8, .6)


def _snap(b):
    return [(p.kind, copy.deepcopy(p.a), p.role, p.pivot, p.side) for p in b.parts]


def _toy():
    b = Builder()
    b.E(0, -10, 6, 7, BODY, 10, "body")
    b.C([(5, -8), (5, -3), (5, 0)], 1.5, BODY, 9, "leg", sym=True, role="leg", pivot=(5, -8))
    return b


def test_capsule_rotates_about_pivot():
    b = Builder()
    b.C([(0, 0), (0, 5)], 1, role="leg", pivot=(0, 0))
    p = posed(b, {"leg": {"rot": 90}}).parts[0]
    (x0, y0), (x1, y1) = p.a[0]
    assert (x0, y0) == pytest.approx((0, 0), abs=1e-9)
    assert (x1, y1) == pytest.approx((-5, 0), abs=1e-9)     # clockwise on screen: down -> left
    assert p.a[1] == [1, 1]


def test_polygon_ellipse_rect_and_default_pivot():
    b = Builder()
    b.P([(0, 0), (4, 0), (4, 2), (0, 2)], role="wing", pivot=(0, 0))
    b.E(4, 0, 2, 1, role="ear", pivot=(0, 0))
    b.R(0, 0, 2, 4, role="tail")
    q = posed(b, {"wing": {"rot": 90}, "ear": {"rot": 90, "dy": 1}, "tail": {"rot": 90, "dx": 1, "dy": 2}})
    assert q.parts[0].a[1] == pytest.approx((0, 4), abs=1e-9)
    cx, cy, rx, ry, rot = q.parts[1].a
    assert (cx, cy) == pytest.approx((0, 5), abs=1e-9) and (rx, ry) == (2, 1)
    assert rot == pytest.approx(math.pi / 2)
    assert q.parts[2].a == (1, 2, 3, 6, 0.0)                  # R only translates, never rotates


def test_alt_flips_mirrored_side():
    b = _toy()
    q = posed(b, {"leg": {"rot": 20, "dy": 1, "alt": True}})
    legs = [p for p in q.parts if p.role == "leg"]
    assert [p.side for p in legs] == [1, -1]
    ys = [p.a[0][0][1] for p in legs]                       # pivot is the first point: it only moves by dy
    assert ys[0] == pytest.approx(-8 + 1) and ys[1] == pytest.approx(-8 - 1)
    # without alt both sides move the same way (mirrored geometry gets mirrored rotation only through x)
    q2 = posed(b, {"leg": {"dy": 1}})
    assert all(p.a[0][0][1] == pytest.approx(-7) for p in q2.parts if p.role == "leg")


def test_sym_sets_side_and_mirrors_pivot():
    b = _toy()
    legs = [p for p in b.parts if p.role == "leg"]
    assert [p.side for p in legs] == [1, -1]
    assert legs[0].pivot == (5, -8) and legs[1].pivot == (-5, -8)
    assert b.parts[0].side == 0 and b.parts[0].role is None


def test_posed_does_not_mutate_input():
    b = _toy()
    before = _snap(b)
    q = posed(b, {"leg": {"rot": 30, "dx": 1, "dy": 1, "alt": True}})
    assert _snap(b) == before
    assert q is not b and q.rest is b
    assert _snap(q) != before


def test_flip_mirrors_pivots_and_keeps_side():
    b = _toy()
    b.flip()
    legs = [p for p in b.parts if p.role == "leg"]
    assert legs[0].pivot == (-5, -8) and legs[1].pivot == (5, -8)
    assert [p.side for p in legs] == [1, -1]
    # a flipped creature moves as the mirror image of the unflipped one
    u = _toy()
    pose = {"leg": {"rot": 25, "dx": 1, "dy": .5, "alt": True}}
    pu, pf = posed(u, pose), posed(b, pose)
    for a, c in zip(pu.parts, pf.parts):
        if a.role == "leg":
            assert np.allclose([(-x, y) for x, y in a.a[0]], c.a[0])


def test_toy_render_pose_vs_rest():
    b = _toy()
    rest, info = render(b, 32, .9, pal=PAL)
    same, _ = render(posed(b, {}), 32, .9, pal=PAL)
    assert np.array_equal(rest, same)
    moved, info2 = render(posed(b, {"leg": {"rot": 35, "alt": True}}), 32, .9, pal=PAL)
    assert not np.array_equal(rest, moved)
    assert info2["s"] == info["s"] and info2["ox"] == info["ox"]      # same fit as the rest render


def test_px_offsets():
    b = _toy()
    s = render(b, 32, .9, pal=PAL)[1]["s"]
    q = posed(b, {"leg": {"dx": 2, "px": True}}, s)
    assert q.parts[1].a[0][0][0] == pytest.approx(5 + 2 / s)


def _combos():
    seen = {}
    for sd in SEEDS:
        sp = gen.sprite(sd, "adult")
        seen[(sp.family, sp.plan)] = sd
    return seen


def test_rest_pose_is_bit_identical_everywhere():
    combos = _combos()
    assert len(combos) == 24
    for (fam, plan), sd in combos.items():
        for st in STAGES:
            sp = gen.sprite(sd, st, family=fam, plan=plan)
            bd = sp._build
            a, _ = render(posed(bd.builder, {}), bd.n, bd.fill, pal=bd.pal, n_base=bd.n_base)
            assert np.array_equal(a, sp.body), (fam, plan, st)
            assert a.tobytes() == sp.body.tobytes()


def test_frame_arrays_poses_hook(monkeypatch):
    sp = gen.sprite(SEEDS[0], "adult")
    n = len(anim.ANIM_FRAMES["walk"])
    base = anim.frame_arrays(sp, "walk")
    assert all(np.array_equal(x, y) for x, y in zip(base, anim.frame_arrays(sp, "walk", [{}] * n)))
    with pytest.raises(ValueError):
        anim.frame_arrays(sp, "walk", [{}])
    monkeypatch.setitem(anim.POSES, sp.family, {"walk": [{"x": {}}] * n})
    assert anim.poses_for(sp, "walk") is not None
    monkeypatch.setitem(anim.POSES, (sp.family, sp.plan), {"walk": [{"y": {}}] * n})
    assert anim.poses_for(sp, "walk")[0] == {"y": {}}
    assert anim.poses_for(sp, "eat") is None
