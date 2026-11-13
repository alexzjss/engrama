"""M18: the terrarium backdrop by the hour, the home that grows with the creature, emotes from the PAD."""
import pygame
import pytest
from engrama.app.art import emotes, home, sprites, terrain
from engrama.app.snapshot import Snapshot
from engrama.app.ui.scene import Scene

SIZE = (200, 150)
LOOK = {"seed": 3}


@pytest.fixture(autouse=True)
def _display():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield


def snap(**kw):
    kw.setdefault("look", LOOK)
    return Snapshot(**kw)


def raw(s: pygame.Surface) -> bytes:
    return pygame.image.tobytes(s, "RGB")


def draw(scene: Scene, s: Snapshot, now: float = 1.0) -> bytes:
    surf = pygame.Surface(SIZE)
    scene.draw(surf, s, now)
    return raw(surf)


def test_backdrop_is_a_pure_function_of_size_hour_and_seed():
    a, shadow_a = terrain.backdrop(SIZE, 10.0, 3)
    b, shadow_b = terrain.backdrop(SIZE, 10.0, 3)
    assert raw(a) == raw(b) and shadow_a == shadow_b
    assert raw(a) != raw(terrain.backdrop(SIZE, 10.0, 4)[0])
    assert a.get_size() == SIZE


def test_day_and_night_differ_and_the_night_is_darker():
    def mean(s):
        return sum(raw(s)) / (SIZE[0] * SIZE[1] * 3)
    day, night = terrain.backdrop(SIZE, 12.0)[0], terrain.backdrop(SIZE, 23.5)[0]
    assert mean(night) < mean(day) * 0.6
    assert terrain.is_night(23.5) and terrain.is_night(3.0) and not terrain.is_night(12.0)
    for hour in (0.0, 5.9, 6.5, 12.0, 18.9, 19.0, 23.99, 24.0, 30.0):   # every hour renders, also past midnight
        assert terrain.backdrop((160, 120), hour)[0].get_size() == (160, 120)


def test_scene_follows_the_hour_and_redraws_only_per_quarter():
    sc = Scene(SIZE)
    hour = [10.0]
    sc.hour_fn = lambda: hour[0]
    first = draw(sc, snap(stage="child"))
    bg = sc._bg
    hour[0] = 10.2
    assert draw(sc, snap(stage="child")) == first and sc._bg is bg     # same quarter: cached
    hour[0] = 22.0
    assert draw(sc, snap(stage="child")) != first and sc._bg is not bg


def test_home_only_gains_things_as_the_creature_grows():
    stages = ("baby", "child", "adult", "perfect", "final")
    sets = [set(home.items_for(s)) for s in stages]
    assert all(a <= b for a, b in zip(sets, sets[1:])) and sets[0] and len(sets[-1]) > len(sets[0])
    assert home.items_for("egg") == ("nest",)
    look = sprites.look_of(LOOK)
    for kind in home.SPOTS:
        img = home.item(kind, look.palette)
        assert img is home.item(kind, look.palette) and img.get_width() >= 7
    other = sprites.look_of({"seed": 3, "palette": [[0, 0, 0], [10, 200, 10], [0, 0, 0], [10, 10, 200]]})
    assert raw(home.item("bed", other.palette)) != raw(home.item("bed", look.palette))   # the creature's own colours


def test_asleep_with_a_bed_she_sleeps_on_it():
    sc = Scene(SIZE)
    sc.hour_fn = lambda: 23.0
    draw(sc, snap(stage="adult", asleep=True))
    bed_x = int(SIZE[0] * home.SPOTS["bed"][0])
    assert abs(sc.creature_rect.centerx - bed_x) <= 1
    draw(sc, snap(stage="baby", asleep=True))                           # no bed yet: she sleeps where she is
    assert abs(sc.creature_rect.centerx - SIZE[0] // 2) < 12


def test_ambient_emote_follows_sleep_and_the_pad():
    assert emotes.ambient_kind(True, (0.9, 0.9, 0.0)) == "z"
    assert emotes.ambient_kind(False, (-0.6, 0.6, 0.0)) == "bolt"
    assert emotes.ambient_kind(False, (-0.6, 0.0, 0.0)) == "drop"
    assert emotes.ambient_kind(False, (0.7, 0.5, 0.0)) == "note"
    assert emotes.ambient_kind(False, (0.0, 0.0, 0.0)) == "" and emotes.ambient_kind(False, (-0.9, 0.9, 0.0), sick=True) == ""
    assert emotes.ambient_visible("z", 5.0) and emotes.ambient_visible("note", 1.0)
    assert not emotes.ambient_visible("note", emotes.AMBIENT_ON + 1.0) and not emotes.ambient_visible("", 1.0)


def test_emotes_draw_in_the_terrarium_and_never_in_the_overlay():
    sc = Scene(SIZE)
    sc.hour_fn = lambda: 12.0
    calm, sad = snap(stage="child"), snap(stage="child", pad=(-0.7, 0.0, 0.0))
    assert draw(sc, sad, 1.0) != draw(sc, calm, 1.0)
    assert draw(sc, sad, emotes.AMBIENT_ON + 2.0) == draw(sc, calm, emotes.AMBIENT_ON + 2.0)   # hidden most of the cycle

    def bare(s):
        surf = pygame.Surface(SIZE)
        surf.fill((1, 2, 3))
        sc.draw(surf, s, 1.0, background=False)
        return raw(surf)
    assert bare(sad) == bare(calm)   # the overlay window hugs the body: nothing may be drawn around it


def test_petting_bursts_hearts_for_a_moment():
    sc = Scene(SIZE)
    sc.hour_fn = lambda: 12.0
    s = snap(stage="child")
    plain = draw(sc, s, 10.0)
    sc.burst("heart", 10.0)
    assert draw(sc, s, 10.3) != plain and sc.moving
    draw(sc, s, 10.0 + emotes.BURST_SECONDS + 0.1)
    assert sc._burst is None
