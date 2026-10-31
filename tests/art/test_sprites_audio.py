import hashlib
import random
from dataclasses import dataclass

import pygame
import pytest

from engrama.art import sprites
from engrama.art.sprites import ANIMS, food_icon, make_egg_crack, make_frames
from engrama.audio.growl import Growler


@dataclass
class G:
    seed: int = 1
    body: int = 0
    eyes: int = 1
    ears: int = 2
    tail: int = 0
    pattern: int = 1
    palette: tuple = ((40, 30, 60), (240, 140, 120), (190, 90, 100), (250, 220, 120))
    voice_pitch: float = 300.0
    branch: str = "x"


def rand_genome(seed: int) -> G:
    r = random.Random(seed)
    pal = tuple(tuple(r.randrange(256) for _ in range(3)) for _ in range(4))
    return G(seed, r.randrange(6), r.randrange(4), r.randrange(5), r.randrange(4), r.randrange(4), pal)


def h(surface: pygame.Surface) -> str:
    return hashlib.md5(pygame.image.tobytes(surface, "RGBA")).hexdigest()


def opaque(s: pygame.Surface) -> int:
    return sum(s.get_at((x, y)).a > 0 for x in range(s.get_width()) for y in range(s.get_height()))


@pytest.fixture(autouse=True, scope="module")
def _pg():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield


@pytest.mark.parametrize("stage,size", [("egg", 16), ("baby", 16), ("child", 24), ("adult", 24), ("perfect", 24), ("final", 24)])
def test_frames_sizes_and_alpha(stage, size):
    for anim in ANIMS:
        frames = make_frames(G(), stage, anim)
        assert 2 <= len(frames) <= 4
        for f in frames:
            assert f.get_size() == (size, size)
            assert f.get_flags() & pygame.SRCALPHA
            assert f.get_at((0, 0)).a == 0
            assert opaque(f) > 0


def test_frames_deterministic():
    a = [h(f) for f in make_frames(rand_genome(5), "baby", "walk")]
    sprites._cache.clear()
    b = [h(f) for f in make_frames(rand_genome(5), "baby", "walk")]
    assert a == b


@pytest.mark.parametrize("stage", ["baby", "child"])
def test_frames_mirrored(stage):
    for eyes in range(4):
        for ears in range(5):
            for body in range(6):
                g = G(seed=eyes * 100 + ears * 10 + body, eyes=eyes, ears=ears, body=body, tail=0)
                f = make_frames(g, stage, "idle")[0]
                flipped = pygame.transform.flip(f, True, False)
                assert pygame.image.tobytes(f, "RGBA") == pygame.image.tobytes(flipped, "RGBA")


def test_different_seeds_differ():
    hashes = {h(make_frames(rand_genome(s), "baby", "idle")[0]) for s in range(20)}
    assert len(hashes) >= 15


def test_child_differs_from_baby():
    g = rand_genome(3)
    baby, child = make_frames(g, "baby", "idle")[0], make_frames(g, "child", "idle")[0]
    assert baby.get_size() != child.get_size()
    assert opaque(child) > opaque(baby) * 1.5


def test_egg_crack_levels():
    g = rand_genome(9)
    shots = [make_egg_crack(g, lv) for lv in range(4)]
    assert all(s.get_size() == (16, 16) for s in shots)
    assert len({h(s) for s in shots}) == 4


def test_food_icons():
    for fid in "carne fruta peixe bolinho pacote cookie bug cache byte ram".split():
        icon = food_icon(fid)
        assert icon.get_size() == (8, 8)
        assert opaque(icon) > 0


def test_growler_silent_ok():
    gr = Growler()
    assert isinstance(gr.ok, bool)
    for kind in ("happy", "ask", "bleh", "hatch", "evolve", "talk"):
        gr.growl(300.0, kind)
    gr.set_muted(True)
    gr.growl(300.0, "happy")
    gr.growl(300.0, "nonsense")
