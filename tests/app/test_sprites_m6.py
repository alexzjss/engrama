import time
from dataclasses import replace

import numpy as np
import pygame
import pytest

from engrama.app.art import sprites, vpet
from engrama.app.art.sprites import ANIMS, SIZES, Look, frames
from engrama.app.art.vpet import anim as vanim
from engrama.app.art.vpet import render
from engrama.app.art.vpet.plan import genes
from engrama.vocab import BRANCHES


@pytest.fixture(autouse=True, scope="module")
def _pg():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield


BASE = Look(seed=5, body=2, eyes=1, ears=2, tail=1, pattern=1)
PAIRS = [(st, br) for st, brs in BRANCHES.items() for br in brs]
STAGES = ("baby", "child", "adult", "perfect", "final")


def look(seed: int) -> Look:
    return Look(seed=seed, body=seed % 6, eyes=(seed // 2) % 4, ears=seed % 5, tail=(seed // 3) % 4,
                pattern=seed % 4, palette=((40, 30, 60), (60 + seed * 9 % 190, 200 - seed * 13 % 120, 90 + seed * 7 % 150),
                                           (90, 90, 90), (200, 200, 60)))


def raw(s):
    return pygame.image.tobytes(s, "RGBA")


def area(s):
    return int((pygame.surfarray.array_alpha(s) > 0).sum())


def mean_value(s):
    a = pygame.surfarray.array3d(s).reshape(-1, 3)
    al = pygame.surfarray.array_alpha(s).reshape(-1)
    return float(a[al > 0].max(axis=1).mean())


def test_sizes():
    assert SIZES == {"egg": 16, "baby": 24, "child": 32, "adult": 40, "perfect": 44, "final": 48}
    for a in ("evolve", "old", "dead"):
        assert a in ANIMS


@pytest.mark.parametrize("arch", vpet.ARCHS)
def test_every_archetype_pose_and_anim_draws(arch):
    g = genes(look(7))
    for pose in range(4):
        sp = render.build(g, "adult", arch, pose=pose)
        for an in ANIMS:
            fr = vanim.frame_arrays(sp, an)
            assert 2 <= len(fr) <= 4
            for a in fr:
                assert a.shape == (40, 40, 4)
                assert int((a[:, :, 3] > 0).sum()) > 50


@pytest.mark.parametrize("kind", vpet.BABIES)
def test_every_baby_kind_draws(kind):
    g = genes(look(3))
    sp = render.build(g, "baby", "slime", kind=kind)
    for an in ANIMS:
        assert all(a.shape == (24, 24, 4) for a in vanim.frame_arrays(sp, an))


@pytest.mark.parametrize("stage,branch", PAIRS)
def test_each_branch_draws(stage, branch):
    lk = replace(BASE, branch=branch, lineage=("brincalhao",))
    for an in ANIMS:
        fr = frames(lk, stage, an)
        assert 2 <= len(fr) <= 4
        for f in fr:
            assert f.get_size() == (SIZES[stage],) * 2
            assert area(f) > 0


def test_stages_without_branch_all_anims():
    for st in SIZES:
        for an in ANIMS:
            assert 2 <= len(frames(BASE, st, an)) <= 4


@pytest.mark.parametrize("stage", ["child", "adult", "perfect", "final"])
def test_branches_differ(stage):
    imgs = {br: raw(frames(replace(BASE, branch=br), stage, "idle")[0]) for br in BRANCHES[stage]}
    imgs["base"] = raw(frames(BASE, stage, "idle")[0])
    assert len(set(imgs.values())) == len(imgs)


def test_neglect_branch_darker():
    comp = mean_value(frames(replace(BASE, branch="companheiro"), "adult", "idle")[0])
    somb = mean_value(frames(replace(BASE, branch="sombrio"), "adult", "idle")[0])
    assert somb < comp


def test_unknown_branch_falls_back():
    a = frames(replace(BASE, branch="futuro_x", lineage=("zzz",)), "adult", "idle")
    b = frames(BASE, "adult", "idle")
    assert [raw(x) for x in a] == [raw(x) for x in b]
    # a branch of another stage does not apply either
    assert raw(frames(replace(BASE, branch="lendario"), "adult", "idle")[0]) == raw(b[0])


def test_look_from_old_dict():
    lk = Look.from_dict({"seed": 3, "body": 1})
    assert lk.branch == "base" and lk.lineage == ()
    lk = Look.from_dict({"branch": "artista", "lineage": ["curioso", "artista"]})
    assert lk.branch == "artista" and lk.lineage == ("curioso", "artista")
    assert Look.from_dict({"lineage": 5}).lineage == ()


def test_cache_key_has_branch():
    sprites._cache.clear()
    frames(replace(BASE, branch="artista"), "adult", "idle")
    frames(replace(BASE, branch="tecnico"), "adult", "idle")
    keys = list(sprites._cache)
    assert len(keys) == 2
    assert any("artista" in k for k in keys) and any("tecnico" in k for k in keys)


def test_cache_key_has_seed_stage_lineage_anim():
    sprites._cache.clear()
    frames(replace(BASE, branch="artista", lineage=("curioso",)), "adult", "walk")
    (key,) = list(sprites._cache)
    assert BASE.seed in key and "adult" in key and "walk" in key and ("curioso",) in key


def test_cache_bounded():
    sprites._cache.clear()
    for s in range(sprites._CACHE_MAX + 20):
        frames(replace(BASE, seed=s, body=s % 6), "baby", "idle")
    assert len(sprites._cache) <= sprites._CACHE_MAX
    assert len(vpet._SPRITES) <= vpet._SPRITES_MAX


def test_evolve_brightens_and_dead_fades():
    ev = [mean_value(f) for f in frames(BASE, "adult", "evolve")]
    assert ev == sorted(ev) and ev[-1] > ev[0]
    d = frames(BASE, "adult", "dead")
    assert pygame.surfarray.array_alpha(d[1]).max() < pygame.surfarray.array_alpha(d[0]).max()


def test_anim_frames_differ():
    for an in ("walk", "eat", "sleep", "happy", "sad", "sick", "old"):
        fr = frames(BASE, "adult", an)
        assert len({raw(f) for f in fr}) >= 2, an
    assert raw(frames(BASE, "adult", "sick")[0]) != raw(frames(BASE, "adult", "idle")[0])


# ---- archetype choice


def test_archetype_pure_function():
    for seed in range(1, 12):
        for st in STAGES:
            lin = ("curioso", "tecnico", "virtuoso", "mestre")
            a = vpet.archetype(seed, st, lin)
            assert a == vpet.archetype(seed, st, lin)
    # earlier stages do not depend on later branches
    assert vpet.archetype(4, "adult", ("curioso", "tecnico")) == vpet.archetype(4, "adult", ("curioso", "tecnico", "virtuoso"))


def test_lineage_bias_changes_shape():
    seen = set()
    for seed in range(1, 21):
        seen.add(vpet.archetype(seed, "adult", ("curioso", "tecnico")) != vpet.archetype(seed, "adult", ("curioso", "companheiro")))
    assert True in seen
    robots = sum(vpet.archetype(s, "adult", ("curioso", "tecnico")) == "robot" for s in range(1, 201))
    others = sum(vpet.archetype(s, "adult", ("curioso", "companheiro")) == "robot" for s in range(1, 201))
    assert robots > others * 2


def test_form_changes_in_an_evolution_for_most_seeds():
    changed = 0
    for seed in range(1, 21):
        lin = ("curioso", "explorador", "aventureiro", "mestre")
        chain = [vpet.archetype(seed, st, lin) for st in STAGES]
        changed += any(a != b for a, b in zip(chain, chain[1:]))
    assert changed >= 17


def test_twenty_adult_seeds_give_ten_archetypes():
    assert len({vpet.archetype(s, "adult", ()) for s in range(1, 21)}) >= 10


# ---- visual quality


def body_and_idle(lk, stage):
    sp = vpet.build_sprite(lk, stage)
    idle = vpet.creature_frames(lk, stage, "idle")[0]
    return sp, idle


def test_eyes_visible_in_every_idle():
    for seed in range(1, 41):
        lk = look(seed)
        for stage in STAGES:
            sp, idle = body_and_idle(lk, stage)
            body = sp.body
            diff = np.abs(idle[:, :, :3].astype(int) - body[:, :, :3].astype(int)).sum(axis=2) > 90
            assert int((diff & (body[:, :, 3] > 0)).sum()) >= 3, (seed, stage)
            for x, y, _, _ in sp.canvas.eye_cells():
                x, y = x + sp.ox, y + sp.oy
                assert 0 <= x < sp.n and 0 <= y < sp.n and idle[y, x, 3] > 0, (seed, stage)


def test_higher_stages_are_bigger():
    for seed in range(1, 21):
        lk = look(seed)
        a = {st: area(frames(lk, st, "idle")[0]) for st in STAGES}
        assert a["final"] > a["adult"], seed
        assert a["adult"] > a["child"] * 1.1, seed
        assert a["child"] > a["baby"] * 1.1, seed
        assert a["perfect"] > a["adult"] * .85, seed


def test_creature_stays_inside_canvas_with_room_to_hop():
    for seed in range(1, 15):
        for stage in STAGES:
            sp = vpet.build_sprite(look(seed), stage)
            al = sp.body[:, :, 3] > 0
            ys, xs = np.nonzero(al)
            assert ys.max() == sp.n - 1 and ys.min() >= 2 and xs.min() >= 1 and xs.max() <= sp.n - 2, (seed, stage)


def test_sprite_cost_is_small():
    t0 = time.perf_counter()
    n = 0
    for seed in range(100, 130):
        for stage in STAGES:
            frames(look(seed), stage, "idle")
            n += 1
    assert (time.perf_counter() - t0) / n < 0.03
