import re
import pygame
from engrama.app import i18n
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud, viz_draw
from engrama.app.ui.mind_view import MindView

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


class FakeGrowler:
    muted = False

    def growl(self, pitch, kind):
        pass

    def set_muted(self, m):
        pass


class FakeProvider:
    def __init__(self):
        self.calls = []
        self._facts = [("idade", "idade: 23")]

    def facts(self):
        return list(self._facts)

    def topics(self):
        return [("musica", True), ("chuva", False)]

    def opinions(self):
        return [("musica", "gosta")]

    def reflections(self):
        return ["gostou de falar de musica"]

    def delete_fact(self, key):
        self.calls.append(("fact", key))
        self._facts = [f for f in self._facts if f[0] != key]

    def delete_topic(self, name):
        self.calls.append(("topic", name))

    def forget_all(self):
        self.calls.append(("all", None))

    def summary(self):
        return {"episodes": 7, "facts": 1, "topics": 2, "opinions": 1, "last_reflection": "refletiu sobre musica"}


def make(provider=None):
    w = Window(lambda: Snapshot(look=LOOK), lambda k, d=None: None, growler=FakeGrowler())
    w.memory_provider = provider
    return w


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def texts(w):
    out = []
    hud.add_text_hook(out.append)
    try:
        w.frame(1.0)
    finally:
        hud.remove_text_hook(out.append)
    return out


def test_lists_sections():
    w = make(FakeProvider())
    w.open_panel("memories")
    out = " | ".join(texts(w))
    assert i18n.t("ui.memories.title") in out
    assert "idade" in out and "musica" in out and "gosta" in out
    assert i18n.t("ui.memories.current") in out


def test_delete_requires_confirm():
    p = FakeProvider()
    w = make(p)
    w.open_panel("memories")
    w.frame(1.0)
    w.handle_event(key(pygame.K_DELETE))
    w.frame(1.0)
    assert p.calls == []
    w.handle_event(key(pygame.K_RETURN))
    assert p.calls == [("fact", "idade")]


def test_delete_cancel_with_escape_does_not_delete():
    p = FakeProvider()
    w = make(p)
    w.open_panel("memories")
    w.frame(1.0)
    w.handle_event(key(pygame.K_DELETE))
    w.panel.handle_event(key(pygame.K_ESCAPE))
    w.panel.handle_event(key(pygame.K_RETURN))
    assert p.calls == []


def test_forget_all_double_confirm():
    p = FakeProvider()
    w = make(p)
    w.open_panel("memories")
    w.frame(1.0)
    w.panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=w.panel._forget_rect.center, button=1))
    w.panel.handle_event(key(pygame.K_RETURN))
    assert p.calls == []
    w.frame(1.0)
    w.panel.handle_event(key(pygame.K_RETURN))
    assert p.calls == [("all", None)]


def test_no_digits_normal_mode():
    w = make(FakeProvider())
    w.open_panel("memories")
    out = texts(w)
    assert not any(c.isdigit() for s in out for c in s)
    w.dev = True
    assert any("23" in s for s in texts(w))


def test_f7_opens_panel():
    w = make(FakeProvider())
    w.handle_event(key(pygame.K_F7))
    assert w.panel_name == "memories"
    w.handle_event(key(pygame.K_F7))
    assert w.panel_name is None


def test_no_provider_shows_empty():
    w = make(None)
    w.open_panel("memories")
    assert i18n.t("ui.memories.empty") in texts(w)
    w.panel.handle_event(key(pygame.K_DELETE))


def test_scroll_and_arrows_keep_working():
    w = make(FakeProvider())
    w.open_panel("memories")
    w.frame(1.0)
    w.panel.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3))
    w.panel.handle_event(key(pygame.K_DOWN))
    w.frame(1.0)


def _mind_texts(mv):
    out = []
    viz_draw._text_hook = out.append
    try:
        mv.draw(pygame.Surface((640, 480)), Snapshot(look=LOOK))
    finally:
        viz_draw._text_hook = None
    return out


def test_mind_view_memory_summary_draws():
    mv = MindView()
    mv.memory_summary = FakeProvider().summary
    out = " | ".join(_mind_texts(mv))
    assert "refletiu sobre musica" in out and "7" in out


def test_mind_view_memory_summary_raises_is_safe():
    def boom():
        raise RuntimeError("x")
    mv = MindView()
    mv.memory_summary = boom
    _mind_texts(mv)


def test_window_wires_summary_into_mind_view():
    w = make(FakeProvider())
    w.open_panel("mind")
    assert w.panel.memory_summary()["episodes"] == 7


class SemanticProvider(FakeProvider):
    def __init__(self, semantic):
        super().__init__()
        self._semantic = semantic

    def summary(self):
        s = dict(super().summary())
        if self._semantic is not None:
            s["semantic"] = self._semantic
        return s


def test_memories_semantic_line_on_and_words_no_digits():
    for sem, want in (("on", "ui.memories.semantic_on"), ("words", "ui.memories.semantic_off"), (None, "ui.memories.semantic_off")):
        w = make(SemanticProvider(sem))
        w.open_panel("memories")
        out = texts(w)
        assert i18n.t(want) in out
        assert not any(re.search(r"\d", s) for s in out)
