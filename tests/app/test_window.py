import pygame
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window
from engrama.app.ui import hud
from engrama.vocab import ACTIONS, FOOD_IDS

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


def snap(**kw):
    kw.setdefault("look", LOOK)
    return Snapshot(**kw)


class FakeGrowler:
    def __init__(self):
        self.calls = []

    def growl(self, pitch, kind):
        self.calls.append(kind)


def make(s, **kw):
    posts = []
    holder = {"s": s}
    w = Window(lambda: holder["s"], lambda k, d=None: posts.append((k, d)), growler=FakeGrowler(), **kw)
    return w, posts, holder


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def test_frame_renders_headless():
    w, _, h = make(snap())
    for stage in ("egg", "baby", "child"):
        h["s"] = snap(stage=stage, egg_clicks=3)
        for i in range(30):
            w.frame(i * 0.1)
    for a in ACTIONS:
        h["s"] = snap(stage="child", action=a, needs={"fome": 0.9, "sono": 0.7})
        for i in range(30):
            w.frame(i * 0.1)
    w.eat_until = 1e18
    w.frame(1.0)
    for name in ("mind", "food", "models", "settings"):
        w.open_panel(name)
        w.frame(2.0)
    w.close_panel()
    w.dev = True
    w.frame(3.0)


def creature_pos(w):
    r = w.scene.creature_rect
    return (r.centerx * 4, r.centery * 4)


def test_click_on_creature_posts_click_or_pet():
    w, posts, h = make(snap(stage="egg"))
    w.frame(1.0)
    w.handle_event(click(creature_pos(w)))
    assert posts[-1] == ("click", None)
    h["s"] = snap(stage="child")
    w.frame(1.0)
    w.handle_event(click(creature_pos(w)))
    assert posts[-1] == ("pet", None)
    n = len([p for p in posts if p[0] in ("click", "pet")])
    w.handle_event(click((2, 470)))
    assert len([p for p in posts if p[0] in ("click", "pet")]) == n


def test_food_menu_posts_food_event():
    w, posts, _ = make(snap(stage="child"))
    w.frame(1.0)
    w.handle_event(key(pygame.K_F4))
    assert w.panel_name == "food"
    w.frame(1.0)
    w.handle_event(click(w.panel._rects[FOOD_IDS.index("peixe")].center))
    assert ("food", {"food": "peixe"}) in posts
    assert w.panel is None
    w.handle_event(key(pygame.K_F4))
    w.handle_event(key(pygame.K_ESCAPE))
    assert w.panel is None


def test_fps_policy():
    w, _, h = make(snap())
    w.frame(0)
    assert w.target_fps == 20
    w.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    assert w.target_fps == 5
    h["s"] = snap(resting=True)
    w.frame(0)
    assert w.target_fps == 2


def test_rest_key_uses_callback():
    calls = []
    w, _, _ = make(snap(), set_rest=calls.append)
    w.handle_event(key(pygame.K_F3))
    w.handle_event(key(pygame.K_F3))
    assert calls == [True, False]


def test_no_digits_rendered_in_normal_mode():
    seen = []
    hud.add_text_hook(seen.append)
    try:
        w, _, _ = make(snap(stage="child", resting=True,
                            needs={"fome": 0.9, "sono": 0.8, "tedio": 0.7, "carinho": 0.65, "apoio": 0.1},
                            t=12345.0, egg_clicks=2))
        w.frame(1.0)
        w.open_panel("food")
        w.frame(1.0)
        assert seen
        assert not any(c.isdigit() for s in seen for c in s), seen
        n = len(seen)
        w.close_panel()
        w.dev = True
        w.frame(1.0)
        assert any(c.isdigit() for s in seen[n:] for c in s)
    finally:
        hud.remove_text_hook(seen.append)


def test_growl_on_hatch_and_ask():
    w, _, _ = make(snap(stage="baby"))
    w.on_host_event("hatch", {"stage": "baby"})
    w.on_host_event("action_change", {"from": "idle", "to": "ask_attention"})
    w.on_host_event("action_change", {"from": "idle", "to": "sleep"})
    w.on_host_event("evolve", {"from": "baby", "to": "child"})
    w.frame(1.0)
    assert w.growler.calls == ["hatch", "ask", "evolve"]


def test_custom_panel_registry():
    state = {"opened": False, "closed": False}

    class P:
        def draw(self, s, snap):
            pass

        def handle_event(self, e):
            return False

        def on_open(self):
            state["opened"] = True

        def on_close(self):
            state["closed"] = True

    w, _, _ = make(snap())
    w.panels["x"] = lambda win: P()
    w.open_panel("x")
    w.frame(0)
    w.close_panel()
    assert state == {"opened": True, "closed": True}


def test_egg_hint_shown_only_in_egg_stage():
    seen = []
    hud.add_text_hook(seen.append)
    try:
        from engrama.app import i18n
        w, _, h = make(snap(stage="egg"))
        w.frame(1.0)
        hint = i18n.t("ui.egg.hint")
        assert hint != "ui.egg.hint" and hint in seen
        assert not any(c.isdigit() for c in hint)
        seen.clear()
        h["s"] = snap(stage="baby")
        w.frame(1.0)
        assert hint not in seen
    finally:
        hud.remove_text_hook(seen.append)


def test_egg_hint_in_both_languages():
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parents[2] / "engrama" / "app" / "i18n"
    for lang in ("pt", "en"):
        d = json.loads((base / f"{lang}.json").read_text(encoding="utf-8"))
        assert d["ui.egg.hint"] and not any(c.isdigit() for c in d["ui.egg.hint"])


def test_egg_click_center_and_edge_post_click():
    w, posts, _ = make(snap(stage="egg"))
    assert w.size == (640, 480)
    w.frame(1.0)
    r = w.scene.creature_rect
    on_screen = pygame.Rect(r.x * 4, r.y * 4, r.w * 4, r.h * 4)
    for pos in (on_screen.center, (on_screen.left + 1, on_screen.centery), (on_screen.right - 1, on_screen.centery),
                (on_screen.centerx, on_screen.top + 1), (on_screen.centerx, on_screen.bottom - 1)):
        posts.clear()
        w.handle_event(click(pos))
        assert ("click", None) in posts, pos


def test_egg_click_does_not_touch_chat_input():
    w, posts, _ = make(snap(stage="egg"))
    w.chat.text = "oi"
    w.frame(1.0)
    r = w.scene.creature_rect
    w.handle_event(click((r.centerx * 4, r.centery * 4)))
    assert posts.count(("click", None)) == 1
    assert w.chat.text == "oi"


def test_window_no_longer_posts_app_focus():
    w, posts, _ = make(snap())
    w.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    w.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
    assert posts == [] and w.focused is True
