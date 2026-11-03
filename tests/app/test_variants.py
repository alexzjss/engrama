import dataclasses
import hashlib
import os
import subprocess
import sys

import pygame
import pytest

from engrama.app.art import vpet
from engrama.app.art.items import found_item
from engrama.app.art.sprites import Look
from engrama.app.snapshot import Snapshot
from engrama.app.ui.scene import Scene
from engrama.app.ui.variants import VARIANT_RULES, VariantCtx, pick_variant
from engrama.vocab import ACTIONS, VARIANTS

COLORKEY = (255, 0, 255)
STAGES = ("baby", "child", "adult", "perfect", "final")
LOOK = Look(seed=5, body=2, eyes=1, ears=2, tail=1, pattern=1)


@pytest.fixture(autouse=True, scope="module")
def _pg():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield


def ctx(**kw):
    base = dict(stage="adult", pad=(0.8, 0.0, 0.0), needs={"sono": 90.0}, overlay=False, cursor_near=True,
                theme="musica", peek_ok=True)
    base.update(kw)
    return VariantCtx(**base)


def test_rules_cover_vocab():
    assert set(VARIANT_RULES) == set(VARIANTS)


def test_deterministic_and_varied():
    a = [pick_variant("play_alone", ctx(), 7, n) for n in range(50)]
    assert a == [pick_variant("play_alone", ctx(), 7, n) for n in range(50)]
    assert len(set(a)) >= 2


def test_deterministic_across_processes():
    code = ("from engrama.app.ui.variants import *;"
            "c=VariantCtx('adult',(0.8,0,0),{'sono':90.0},False,theme='musica');"
            "print('R', [pick_variant('play_alone',c,7,n) for n in range(20)])")
    outs = set()
    for seed in ("1", "2"):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={**os.environ, "PYTHONHASHSEED": seed})
        outs.add(next(ln for ln in r.stdout.splitlines() if ln.startswith("R ")))
    assert len(outs) == 1 and "dance" in outs.pop()


def test_stage_locks():
    for n in range(200):
        assert pick_variant("play_alone", ctx(stage="baby"), 1, n) in ("", "jump")
        assert pick_variant("explore", ctx(stage="child", overlay=True), 1, n) != "peek"
        assert pick_variant("show_something", ctx(stage="child"), 1, n) == ""
        assert pick_variant("idle", ctx(stage="egg"), 1, n) == ""


def test_mode_locks():
    for n in range(200):
        for a in ACTIONS:
            assert pick_variant(a, ctx(overlay=False), 3, n) not in ("nap_clock", "chase", "look_cursor", "peek")
            assert pick_variant(a, ctx(overlay=True), 3, n) not in ("dig",)


def test_conditions():
    seen = {pick_variant("explore", ctx(overlay=True, peek_ok=False), 2, n) for n in range(200)}
    assert "peek" not in seen and "chase" in seen
    seen = {pick_variant("explore", ctx(overlay=True, cursor_near=False), 2, n) for n in range(200)}
    assert not seen & {"chase", "look_cursor"}
    seen = {pick_variant("play_alone", ctx(pad=(0.0, 0, 0), theme=""), 2, n) for n in range(100)}
    assert seen == {""}
    assert "dance" in {pick_variant("play_alone", ctx(pad=(0.0, 0, 0), theme="musica"), 2, n) for n in range(100)}
    assert "yawn" not in {pick_variant("idle", ctx(needs={"sono": 10.0}), 2, n) for n in range(100)}
    assert "found" in {pick_variant("show_something", ctx(), 2, n) for n in range(100)}


def test_asleep():
    for n in range(50):
        assert pick_variant("idle", ctx(asleep=True), 1, n) == ""
        assert pick_variant("sleep", ctx(asleep=True), 1, n) in ("", "nap_clock")
        assert pick_variant("sleep", ctx(asleep=True, overlay=False), 1, n) == ""


@pytest.mark.parametrize("stage", STAGES)
def test_new_anims_exist(stage):
    for an in ("jump", "dance", "yawn", "dig"):
        fr = vpet.creature_frames(LOOK, stage, an)
        assert 2 <= len(fr) <= 4
        for a in fr:
            assert int((a[:, :, 3] > 0).sum()) > 50
            opaque = a[:, :, 3] > 0
            assert not ((a[:, :, 0] == 255) & (a[:, :, 1] == 0) & (a[:, :, 2] == 255) & opaque).any()


def snap(stage="adult", action="idle", **kw):
    return Snapshot(stage=stage, action=action, look=dataclasses.asdict(LOOK), **kw)


def digest(surf):
    return hashlib.md5(pygame.image.tobytes(surf, "RGB")).hexdigest()


def render(variant=None, background=True, item=None, stage="adult", action="idle", now=1.3, fill=None, **kw):
    sc = Scene((160, 120))
    s = pygame.Surface((160, 120))
    s.fill(fill or (1, 2, 3))
    args = {}
    if variant is not None:
        args["variant"] = variant
    if item is not None:
        args["item"] = item
    if background is not True:
        args["background"] = background
    sc.draw(s, snap(stage, action, **kw), now, **args)
    return s


def test_old_calls_identical():
    for stage in ("egg", "baby", "adult"):
        for action in ("idle", "wander", "sleep", "hide"):
            a = render(stage=stage, action=action)
            b = render(variant="", background=True, item="", stage=stage, action=action)
            assert digest(a) == digest(b)


def test_variant_changes_image_and_priorities():
    base = render(action="play_alone", now=0.0)
    for v in ("jump", "dance", "yawn", "dig"):
        assert digest(render(variant=v, action="idle", now=0.0)) != digest(render(action="idle", now=0.0)) or v == "found"
    assert digest(render(variant="dance", action="play_alone", now=0.0)) != digest(base)
    # sick/asleep/dead stay above the variant
    assert digest(render(variant="dance", sick=True)) == digest(render(sick=True))
    assert digest(render(variant="dig", asleep=True)) == digest(render(asleep=True))
    assert digest(render(variant="jump", dead=True)) == digest(render(dead=True))


def test_background_false_keeps_fill():
    fill = COLORKEY
    s = render(variant="jump", background=False, fill=fill)
    sc = Scene((160, 120))
    r = None
    t = pygame.Surface((160, 120))
    t.fill(fill)
    sc.draw(t, snap(), 1.3, variant="jump", background=False)
    r = sc.creature_rect.inflate(30, 30)
    for x in range(0, 160, 3):
        for y in range(0, 120, 3):
            if not r.collidepoint(x, y):
                assert s.get_at((x, y))[:3] == fill
    # nothing the creature/dirt/items draw is the colour key
    for v, it in (("jump", ""), ("dig", ""), ("found", "osso"), ("found", "chip"), ("found", "pedra"),
                  ("found", "arquivo")):
        for stage in STAGES:
            for now in (0.0, 0.3, 0.6, 0.9):
                t = pygame.Surface((160, 120))
                t.fill((1, 2, 3))
                Scene((160, 120)).draw(t, snap(stage), now, variant=v, background=False, item=it)
                for x in range(160):
                    for y in range(120):
                        assert t.get_at((x, y))[:3] != COLORKEY


@pytest.mark.parametrize("kind", ("osso", "chip", "pedra", "arquivo"))
def test_found_item(kind):
    s = found_item(kind)
    assert s.get_size() == (8, 8) and found_item(kind) is s
    assert any(s.get_at((x, y)).a > 0 for x in range(8) for y in range(8))
    assert all(s.get_at((x, y))[:3] != COLORKEY for x in range(8) for y in range(8) if s.get_at((x, y)).a)


def test_found_and_dig_draw_extras():
    plain = render(action="show_something", now=0.5)
    assert digest(render(variant="found", item="osso", action="show_something", now=0.5)) != digest(plain)
    assert digest(render(variant="dig", action="explore", now=0.5)) != digest(render(action="explore", now=0.5))
