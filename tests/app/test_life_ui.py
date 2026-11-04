import json

import pygame

from engrama import vocab
from engrama.app import i18n
from engrama.app.art import sprites
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud
from engrama.app.ui import scene as scene_mod

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


class FakeGrowler:
    def growl(self, pitch, kind):
        pass


def snap(**kw):
    kw.setdefault("look", LOOK)
    kw.setdefault("stage", "adult")
    return Snapshot(**kw)


def make(s):
    posts, holder = [], {"s": s}
    w = Window(lambda: holder["s"], lambda k, d=None: posts.append((k, d)), growler=FakeGrowler())
    return w, posts, holder


def capture(fn):
    seen = []
    hud.add_text_hook(seen.append)
    try:
        fn()
    finally:
        hud.remove_text_hook(seen.append)
    return seen


def test_hud_shows_branch_and_signs():
    i18n.set_lang("pt")
    w, _, _ = make(snap(branch="artista", sick=True, old=True))
    seen = capture(lambda: w.frame(1.0))
    assert i18n.t("branch.artista") in seen
    assert i18n.t("ui.life.sick") in seen
    assert i18n.t("ui.life.old") in seen
    assert not any(c.isdigit() for s in seen for c in s)
    w2, _, _ = make(snap(branch="base"))
    assert i18n.t("branch.base") in capture(lambda: w2.frame(1.0))


def test_grave_warning_text():
    i18n.set_lang("en")
    w, _, _ = make(snap(sick=True, grave=True))
    seen = capture(lambda: w.frame(1.0))
    assert i18n.t("ui.life.grave") in seen
    w2, _, _ = make(snap(sick=True))
    assert i18n.t("ui.life.grave") not in capture(lambda: w2.frame(1.0))
    i18n.set_lang("pt")


def _recorded_anims(monkeypatch):
    calls = []
    real = sprites.frames

    def spy(look, stage, anim):
        calls.append(anim)
        return real(look, stage, anim)

    monkeypatch.setattr(sprites, "frames", spy)
    return calls


def test_evolve_anim_window(monkeypatch):
    calls = _recorded_anims(monkeypatch)
    w, _, h = make(snap(wall=100.0, evolved_at=99.0))
    w.frame(1.0)
    assert calls[-1] == "evolve"
    h["s"] = snap(wall=104.5, evolved_at=99.0)
    w.frame(1.0)
    assert calls[-1] != "evolve"
    h["s"] = snap(wall=100.0, sick=True, old=True)
    w.frame(1.0)
    assert calls[-1] == "sick"
    h["s"] = snap(wall=100.0, old=True)
    w.frame(1.0)
    assert calls[-1] == "old"
    h["s"] = snap(wall=100.0, sick=True, asleep=True)
    w.frame(1.0)
    assert calls[-1] == "sleep"


def test_dead_scene_and_skip(monkeypatch):
    calls = _recorded_anims(monkeypatch)
    w, _, h = make(snap(dead=True, death_cause="old_age", evolved_at=float("-inf")))
    skipped = []
    w.farewell_text = "Adeus, amigo"
    w.on_farewell_skip = lambda: skipped.append(1)
    seen = capture(lambda: w.frame(10.0))
    assert calls[-1] == "dead"
    assert "Adeus, amigo" not in seen          # not before the bubble delay
    w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1))
    assert skipped == []
    seen = capture(lambda: w.frame(10.0 + scene_mod.FAREWELL_BUBBLE_AT + 0.5))
    assert "Adeus, amigo" in seen
    w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1))
    assert skipped == [1]
    # fade then outline only: renders without error and reports done
    w.frame(10.0 + scene_mod.FAREWELL_FADE_START + 1.0)
    w.frame(10.0 + scene_mod.FAREWELL_FADE_END + 1.0)
    assert w.scene.farewell_done
    # no callback / empty text: clicking is harmless
    w.on_farewell_skip = None
    w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1))


def test_medicine_menu_posts_and_hidden_for_egg():
    w, posts, h = make(snap(stage="egg"))
    w.open_panel("food")
    w.frame(1.0)
    assert len(w.panel._rects) == len(vocab.FOOD_IDS)
    h["s"] = snap(stage="child")
    w.frame(1.0)
    assert len(w.panel._rects) == len(vocab.FOOD_IDS) + 1
    r = w.panel._rects[-1]
    w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
    assert ("food", {"food": vocab.MEDICINE_ID}) in posts
    assert w.eat_until == 0.0
    assert sprites.food_icon(vocab.MEDICINE_ID).get_size() == (8, 8)


def test_branch_i18n_covers_vocab():
    ids = {b for bs in vocab.BRANCHES.values() for b in bs} | {"base"}
    for lang in ("pt", "en"):
        tab = json.loads((i18n._DIR / f"{lang}.json").read_text(encoding="utf-8"))
        assert {f"branch.{b}" for b in ids} <= set(tab)
