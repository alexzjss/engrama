from dataclasses import replace

import pygame
import pytest

from engrama.app.art import sprites
from engrama.app.art.sprites import ANIMS, SIZES, Look, frames
from engrama.vocab import BRANCHES


@pytest.fixture(autouse=True, scope="module")
def _pg():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield


BASE = Look(seed=5, body=2, eyes=1, ears=2, tail=1, pattern=1)
PAIRS = [(st, br) for st, brs in BRANCHES.items() for br in brs]


def raw(s):
    return pygame.image.tobytes(s, "RGBA")


def mean_value(s):
    a = pygame.surfarray.array3d(s).reshape(-1, 3)
    al = pygame.surfarray.array_alpha(s).reshape(-1)
    return float(a[al > 0].max(axis=1).mean())


def test_sizes():
    assert SIZES == {"egg": 16, "baby": 16, "child": 24, "adult": 28, "perfect": 32, "final": 32}
    for a in ("evolve", "old", "dead"):
        assert a in ANIMS


@pytest.mark.parametrize("stage,branch", PAIRS)
def test_each_branch_draws(stage, branch):
    look = replace(BASE, branch=branch, lineage=("brincalhao",))
    for anim in ANIMS:
        fr = frames(look, stage, anim)
        assert 2 <= len(fr) <= 4
        for f in fr:
            assert f.get_size() == (SIZES[stage],) * 2
            assert pygame.surfarray.array_alpha(f).sum() > 0


def test_stages_without_branch_all_anims():
    for st in SIZES:
        for anim in ANIMS:
            assert 2 <= len(frames(BASE, st, anim)) <= 4


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
    a = frames(replace(BASE, branch="futuro_x"), "adult", "idle")
    b = frames(BASE, "adult", "idle")
    assert [raw(x) for x in a] == [raw(x) for x in b]
    assert raw(frames(replace(BASE, branch="lendario"), "adult", "idle")[0]) == raw(b[0])


def test_look_from_old_dict():
    look = Look.from_dict({"seed": 3, "body": 1})
    assert look.branch == "base" and look.lineage == ()
    look = Look.from_dict({"branch": "artista", "lineage": ["curioso", "artista"]})
    assert look.branch == "artista" and look.lineage == ("curioso", "artista")
    assert Look.from_dict({"lineage": 5}).lineage == ()


def test_cache_key_has_branch():
    sprites._cache.clear()
    frames(replace(BASE, branch="artista"), "adult", "idle")
    frames(replace(BASE, branch="tecnico"), "adult", "idle")
    keys = list(sprites._cache)
    assert len(keys) == 2
    assert any("artista" in k for k in keys) and any("tecnico" in k for k in keys)


def test_cache_bounded():
    sprites._cache.clear()
    for s in range(sprites._CACHE_MAX + 20):
        frames(replace(BASE, seed=s, body=s % 6), "baby", "idle")
    assert len(sprites._cache) <= sprites._CACHE_MAX


def test_evolve_brightens_and_dead_fades():
    ev = [mean_value(f) for f in frames(BASE, "adult", "evolve")]
    assert ev == sorted(ev) and ev[-1] > ev[0]
    d = frames(BASE, "adult", "dead")
    assert pygame.surfarray.array_alpha(d[1]).max() < pygame.surfarray.array_alpha(d[0]).max()
