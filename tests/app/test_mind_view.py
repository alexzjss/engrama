import hashlib
from pathlib import Path

import numpy as np
import pygame
import pytest

from engrama.app.host import Host, to_viz
from engrama.app.snapshot import ModuleView, ProposalView, Snapshot, Viz
from engrama.app.ui import viz_draw
from engrama.app.ui.mind_view import MindView
from engrama.app.ui.viz_draw import VizState, draw_viz
from engrama.clock import SimClock
from engrama.config import Config
from engrama.lab.runtime import Runtime
from engrama.mind.recipe import load_recipe

DEFAULT = Path(__file__).resolve().parents[2] / "recipes" / "default-v1.toml"
RECT = pygame.Rect(0, 0, 200, 120)


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    yield


def surf(w=200, h=120):
    return pygame.Surface((w, h))


def digest(s):
    return hashlib.sha1(pygame.image.tobytes(s, "RGB")).hexdigest()


def test_every_default_recipe_viz_draws():
    rt = Runtime(load_recipe(DEFAULT), 3)
    for _ in range(120):
        rt.tick(1.0, [])
    state = VizState()
    n = 0
    for name, m in rt.scheduler.modules().items():
        for spec in m.viz():
            s = surf()
            draw_viz(s, RECT, to_viz(spec), state)
            assert digest(s) != digest(surf()), (name, spec.kind)   # something was drawn
            n += 1
    assert n >= 7


@pytest.mark.parametrize("viz", [
    Viz("blob", "weird", 1),
    Viz("heatmap", "x", [[float("nan"), float("inf")]]),
    Viz("bars", "y", {}),
    Viz("raster", "r", []),
    Viz("series", "s", {"names": ["a"], "rows": [[1, 2]]}),
    Viz("pad3d", "p", {"pad": [float("nan"), 0, 0]}),
    Viz("table", "t", None),
])
def test_unknown_kind_and_nan_draw_placeholder(viz):
    texts = []
    viz_draw._text_hook = texts.append
    try:
        s = surf()
        draw_viz(s, RECT, viz)
    finally:
        viz_draw._text_hook = None
    assert texts == [viz.title]


def test_table_and_vector_raster():
    st = VizState()
    s = surf()
    draw_viz(s, RECT, Viz("table", "tab", [["a", 1.0], ["b", 2]]))
    h0 = digest(s)
    s2 = surf()
    for v in ([0, 1, 0], [1, 0, 1]):
        draw_viz(s2, RECT, Viz("raster", "vec", v), st)
    assert h0 != digest(surf()) and digest(s2) != digest(surf())


class FakeTime:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _raster_hash(tmp, pets):
    ft = FakeTime()
    h = Host(Config(data_dir=tmp), tmp, DEFAULT, seed=11, clock=SimClock(1.0, now_fn=ft),
             ram_free_mb_fn=lambda: 8000.0)
    try:
        h.want_viz = True
        for i in range(60):
            if pets and i % 3 == 0 and i < 30:
                h.post("pet")
            ft.t += 5.0
            h.pump(1)
        snap = h.snapshot()
        v = next(x for x in snap.viz["temporal.snn"] if x.kind == "raster")
        s = surf(240, 120)
        draw_viz(s, pygame.Rect(0, 0, 240, 120), v, VizState())
        return digest(s)
    finally:
        h.stop()


def test_snn_raster_changes_after_events(tmp_path):
    assert _raster_hash(tmp_path / "a", False) != _raster_hash(tmp_path / "b", True)


def _snap(**kw):
    mods = (ModuleView("policy.utility", "policy.utility", ("drives",), ("proposals",), False, 0.5, 1.0, False),
            ModuleView("policy.qlearning", "policy.qlearning", ("drives",), ("proposals",), True, 0.2, 0.5, False),
            ModuleView("temporal.snn", "temporal.snn", ("events",), ("surprise",), False, 3.0, 1.0, True))
    base = dict(modules=mods, recipe_name="r", recipe_version=1,
                proposals=(ProposalView("eat", 0.9, "hungry stomach"), ProposalView("play", 0.3, "bored")),
                winner="eat",
                viz={"policy.utility": (Viz("bars", "u", {"a": 1.0}),)})
    base.update(kw)
    return Snapshot(**base)


def _texts(snap):
    texts = []
    viz_draw._text_hook = texts.append
    try:
        s = surf(480, 700)
        MindView().draw(s, snap)
    finally:
        viz_draw._text_hook = None
    return texts, s


def test_winner_highlighted_and_reason_shown():
    texts, s = _texts(_snap())
    assert any("hungry stomach" in t and t.lstrip().startswith(">>") for t in texts)
    assert any("bored" in t and not t.lstrip().startswith(">>") for t in texts)
    # highlighting changes pixels vs a snapshot with no winner
    _, s2 = _texts(_snap(winner=""))
    assert digest(s) != digest(s2)


def test_demoted_module_marked():
    texts, _ = _texts(_snap())
    assert any("policy.qlearning" in t and "rebaixado" in t for t in texts)
    assert any("temporal.snn" in t and "desligado" in t for t in texts)
    assert not any("policy.utility" in t and ("rebaixado" in t or "desligado" in t) for t in texts)
    assert any("(sombra)" in t for t in texts)
