"""M14 pose invariants across every family x body plan (limb animation, engrama.app.art.vpet.poses)."""
import numpy as np
import pytest

from engrama.app.art import vpet
from engrama.app.art.sprites import ANIMS, Look
from engrama.app.art.vpet import anim
from engrama.kernel.genome import Genome

# one seed per (family, plan): the same 24 seeds as the M12 golden test
SEEDS = (1, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 18, 24, 26, 31, 35, 49, 51, 57, 77, 84, 109)
# a few extra seeds for the border and connectivity sweeps (other proportions / lineage-free variants)
EXTRA = (2, 9, 16, 20, 28, 33, 40, 44, 60, 66, 70, 88, 126, 145, 192, 199)
POSED = ("walk", "idle", "eat", "happy", "sleep", "sad", "jump", "dance", "old")
REST_ANIMS = ("sick", "evolve", "dead")

# (family, plan) whose walk is allowed to stay identical to rest at the adult stage: none today. A combination
# must be listed here WITH a reason (e.g. a body with no moving part for the plan) to be exempt.
WALK_ALLOWLIST: dict = {}


def _look(seed):
    return Look.from_dict(Genome.from_seed(seed).to_dict())


def _combo(seed):
    return vpet.family_of(seed), vpet.plan_of(seed)


def _frames(look, stage, name, poses_on=True):
    saved = anim.POSES
    try:
        if not poses_on:
            anim.POSES = {}
        return vpet.creature_frames(look, stage, name)
    finally:
        anim.POSES = saved


def _components(a) -> int:
    """8-connected components of the alpha mask."""
    m = a[:, :, 3] > 0
    seen = np.zeros_like(m)
    n = 0
    h, w = m.shape
    for y, x in zip(*np.nonzero(m)):
        if seen[y, x]:
            continue
        n += 1
        stack = [(y, x)]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            for ny in range(max(0, cy - 1), min(h, cy + 2)):
                for nx in range(max(0, cx - 1), min(w, cx + 2)):
                    if m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
    return n


def _edges(a):
    al = a[:, :, 3] > 0
    return al[0].any(), al[-1].any(), al[:, 0].any(), al[:, -1].any()


def test_seeds_cover_all_24_combos():
    assert {_combo(s) for s in SEEDS} == {(f, p) for f in vpet.FAMILIES for p in range(3)}


@pytest.mark.parametrize("seed", SEEDS)
def test_walk_frames_differ_at_adult(seed):
    combo = _combo(seed)
    frames = vpet.creature_frames(_look(seed), "adult", "walk")
    distinct = {a.tobytes() for a in frames}
    if combo in WALK_ALLOWLIST:
        pytest.skip(WALK_ALLOWLIST[combo])
    assert len(distinct) >= 3, f"{combo}: walk has {len(distinct)} distinct frames"
    # the limbs move, not only the whole-sprite lean/hop: compare with poses disabled
    plain = {a.tobytes() for a in _frames(_look(seed), "adult", "walk", poses_on=False)}
    assert distinct != plain, f"{combo}: walk identical to the unposed walk"


@pytest.mark.parametrize("seed", SEEDS)
def test_no_ink_on_an_edge_the_rest_frame_leaves_free(seed):
    look = _look(seed)
    for stage in ("child", "adult", "final"):
        for name in POSED:
            posed_frames = vpet.creature_frames(look, stage, name)
            rest_frames = _frames(look, stage, name, poses_on=False)
            for i, (a, r) in enumerate(zip(posed_frames, rest_frames)):
                bad = [e for e, (x, y) in enumerate(zip(_edges(a), _edges(r))) if x and not y]
                assert not bad, f"{_combo(seed)} {stage} {name}[{i}] touches edge(s) {bad} (top,bottom,left,right)"


@pytest.mark.parametrize("seed", SEEDS + EXTRA)
def test_no_detached_pixels_after_posing(seed):
    look = _look(seed)
    for stage in ("child", "adult"):
        for name in ("walk", "eat", "happy", "sleep", "jump", "dance"):
            posed_frames = vpet.creature_frames(look, stage, name)
            rest_frames = _frames(look, stage, name, poses_on=False)
            for i, (a, r) in enumerate(zip(posed_frames, rest_frames)):
                assert _components(a) <= _components(r), f"{_combo(seed)} {stage} {name}[{i}] has detached parts"


@pytest.mark.parametrize("seed", SEEDS)
def test_rest_frames_are_unposed(seed):
    """idle frame 0, sick, evolve and dead (and the egg) are byte-identical to the poses-disabled output."""
    look = _look(seed)
    for stage in ("baby", "child", "adult", "perfect", "final"):
        assert (vpet.creature_frames(look, stage, "idle")[0].tobytes()
                == _frames(look, stage, "idle", poses_on=False)[0].tobytes())
        for name in REST_ANIMS:
            if name not in ANIMS:
                continue
            on = vpet.creature_frames(look, stage, name)
            off = _frames(look, stage, name, poses_on=False)
            assert [a.tobytes() for a in on] == [a.tobytes() for a in off], f"{_combo(seed)} {stage} {name}"
