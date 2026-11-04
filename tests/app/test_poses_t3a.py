"""Limb poses of draco, fera, ave and inseto (M14 T3a)."""
import numpy as np
import pytest

from engrama.app.art import vpet
from engrama.app.art.vpet import anim
from engrama.app.art.vpet.anim import ANIM_FRAMES, frame_arrays
from tests.app.test_sprite_golden import SEEDS, _look

FAMILIES = ("draco", "fera", "ave", "inseto")
CASES = [(s, vpet.family_of(s), vpet.plan_of(s)) for s in SEEDS if vpet.family_of(s) in FAMILIES]
STAGES = ("child", "final")
IDS = [f"{f}{p}" for _, f, p in CASES]


def _posed_and_rest(seed, stage, a):
    sp = vpet.build_sprite(_look(seed), stage)
    return sp, frame_arrays(sp, a, anim.poses_for(sp, a)), frame_arrays(sp, a, None)


def test_every_plan_has_poses():
    assert len(CASES) == 12
    for _, f, p in CASES:
        table = anim.POSES.get((f, p)) or anim.POSES.get(f)
        assert table, (f, p)
        for a, poses in table.items():
            assert len(poses) == len(ANIM_FRAMES[a]), (f, p, a)


@pytest.mark.parametrize("seed,fam,plan", CASES, ids=IDS)
def test_walk_frames_differ(seed, fam, plan):
    for stage in STAGES:
        _, posed, _ = _posed_and_rest(seed, stage, "walk")
        keys = {a.tobytes() for a in posed}
        assert len(keys) >= 3, (fam, plan, stage)


@pytest.mark.parametrize("seed,fam,plan", CASES, ids=IDS)
def test_no_empty_frames_and_idle_rest(seed, fam, plan):
    for stage in STAGES:
        sp = vpet.build_sprite(_look(seed), stage)
        for a in ANIM_FRAMES:
            for fr in frame_arrays(sp, a, anim.poses_for(sp, a)):
                assert fr[:, :, 3].any(), (fam, plan, stage, a)
        idle = frame_arrays(sp, "idle", anim.poses_for(sp, "idle"))
        assert np.array_equal(idle[0], frame_arrays(sp, "idle", None)[0])
        for a in ("sick", "evolve", "dead"):
            assert all(np.array_equal(x, y) for x, y in zip(frame_arrays(sp, a, anim.poses_for(sp, a)),
                                                            frame_arrays(sp, a, None)))


@pytest.mark.parametrize("seed,fam,plan", CASES, ids=IDS)
def test_face_stays_put(seed, fam, plan):
    for stage in STAGES:
        sp = vpet.build_sprite(_look(seed), stage)
        f = sp.face
        x0, x1 = f["ex0"], f["axis"] - f["ex0"]
        y0, y1 = f["ey0"], f["ey0"] + f["h"] + 2
        x0, x1 = min(x0, x1), max(x0, x1)
        for a, frames in ANIM_FRAMES.items():
            posed = frame_arrays(sp, a, anim.poses_for(sp, a))
            rest = frame_arrays(sp, a, None)
            for i, spec in enumerate(frames):
                if any(spec.get(k) for k in ("dy", "sq", "lean", "lie")):
                    continue
                box = (slice(y0, y1 + 1), slice(x0, x1 + 1))
                changed = (posed[i][box] != rest[i][box]).any(axis=2).mean()
                # eyes and mouth are stamped from the rest render; only a floppy ear or wing may brush the skin around
                assert changed <= .2, (fam, plan, a, i, changed)


@pytest.mark.parametrize("seed,fam,plan", CASES, ids=IDS)
def test_eye_stamp_never_covered(seed, fam, plan):
    """Pixels stamped as eyes/mouth in the rest render are identical in every posed frame without dy/sq/lean/lie."""
    for stage in STAGES:
        sp = vpet.build_sprite(_look(seed), stage)
        f = sp.face
        x0, x1 = sorted((f["ex0"], f["axis"] - f["ex0"]))
        box = (slice(f["ey0"], f["my0"] + 3), slice(x0, x1 + 1))
        for a, frames in ANIM_FRAMES.items():
            posed = frame_arrays(sp, a, anim.poses_for(sp, a))
            rest = frame_arrays(sp, a, None)
            for i, spec in enumerate(frames):
                if any(spec.get(k) for k in ("dy", "sq", "lean", "lie")):
                    continue
                stamped = (rest[i][box] != sp.body[box]).any(axis=2)
                assert np.array_equal(posed[i][box][stamped], rest[i][box][stamped]), (fam, plan, stage, a, i)
