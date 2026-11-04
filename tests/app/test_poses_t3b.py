"""M14 T3b: poses of planta, espirito, aquatico and maquina."""
import numpy as np
import pytest

from engrama.app.art.vpet import ANIM_FRAMES, POSES, gen
from engrama.app.art.vpet.anim import frame_arrays, poses_for

FAMS = ("planta", "espirito", "aquatico", "maquina")
SEEDS = (1, 2, 3, 4)


def _keys():
    return [k for k in POSES if (k if isinstance(k, str) else k[0]) in FAMS]


def test_pose_lengths_match_frames():
    for key in _keys():
        for anim, poses in POSES[key].items():
            assert len(poses) == len(ANIM_FRAMES[anim]), (key, anim)


def test_rest_frames_stay_rest():
    for key in _keys():
        for anim in ("idle",):
            assert POSES[key][anim][0] == {}
        for anim in ("sick", "evolve", "dead"):
            assert not POSES[key].get(anim)


def _movable(sp):
    return any(p.role in ("arm", "leg", "ear", "antenna", "tail", "fin") for p in sp._build.builder.parts)


@pytest.mark.parametrize("fam", FAMS)
def test_walk_frames_differ_and_are_not_empty(fam):
    for plan in range(3):
        for stage in ("child", "adult", "final"):
            for seed in SEEDS:
                sp = gen.sprite(seed, stage, family=fam, plan=plan)
                frames = frame_arrays(sp, "walk", poses_for(sp, "walk"))
                assert all(f[..., 3].any() for f in frames)
                if _movable(sp):
                    assert len({f.tobytes() for f in frames}) > 1, (fam, plan, stage, seed)


@pytest.mark.parametrize("fam", FAMS)
def test_all_anims_have_visible_frames(fam):
    sp = gen.sprite(2, "adult", family=fam, plan=0)
    for anim in ANIM_FRAMES:
        for f in frame_arrays(sp, anim, poses_for(sp, anim)):
            assert f[..., 3].any()


@pytest.mark.parametrize("fam", FAMS)
def test_face_unchanged_by_poses(fam):
    """Same frame spec with and without pose: eye and mouth boxes identical (the face is stamped from rest)."""
    for plan in range(3):
        sp = gen.sprite(2, "adult", family=fam, plan=plan)
        poses = poses_for(sp, "happy")
        if not poses:
            continue
        a = frame_arrays(sp, "happy", poses)[0]
        b = frame_arrays(sp, "happy", None)[0]       # happy frame 0 has no dy/lean/sq
        f = sp.face
        y0, y1 = f["ey0"], f["ey0"] + f["h"]
        for x0, x1 in ((f["ex0"], f["ex0"] + f["w"]), (f["axis"] - f["ex0"] - f["w"] + 1, f["axis"] - f["ex0"] + 1)):
            assert np.array_equal(a[y0:y1, x0:x1], b[y0:y1, x0:x1]), (fam, plan)
