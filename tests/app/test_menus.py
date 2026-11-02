import re
import pygame
from engrama.app import i18n
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


class FakeGrowler:
    def __init__(self):
        self.muted = False

    def growl(self, pitch, kind):
        pass

    def set_muted(self, m):
        self.muted = m


class FakeConfig:
    model = "qwen3:1.7b"
    recommended_models = ("qwen3:1.7b", "qwen3:0.6b", "gemma3:1b")
    ui_lang = None


class FakeLang:
    def __init__(self, status="ready", installed=None, fail=False):
        self.status = status
        self._installed = installed
        self.fail = fail
        self.cb = None
        self.pulled = []

    def installed_models(self):
        return self._installed

    def pull(self, name, on_progress):
        self.pulled.append(name)
        self.cb = on_progress
        if self.fail:
            on_progress(-1, "error: boom")


def make(language=None):
    w = Window(lambda: Snapshot(look=LOOK), lambda k, d=None: None, language=language, growler=FakeGrowler())
    w.config = FakeConfig()
    w.saves = 0

    def save():
        w.saves += 1
    w.save_config = save
    return w


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


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


def test_select_model_saves_config():
    w = make(FakeLang(installed={"qwen3:0.6b"}))
    w.open_panel("models")
    w.frame(1.0)
    w.panel.handle_event(click(w.panel._rows[1].center))
    assert w.config.model == "qwen3:0.6b" and w.saves == 1
    w.panel.handle_event(key(pygame.K_DOWN))
    w.panel.handle_event(key(pygame.K_RETURN))
    assert w.config.model == "gemma3:1b" and w.saves == 2
    w.panel.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="foo:2b"))
    w.panel.handle_event(key(pygame.K_RETURN))
    assert w.config.model == "foo:2b"
    assert any("installed" in s or "instalado" in s for s in texts(w))


def test_pull_shows_progress_and_handles_failure():
    lang = FakeLang()
    w = make(lang)
    w.open_panel("models")
    w.frame(1.0)
    w.panel.handle_event(click(w.panel._dl_rect.center))
    assert lang.pulled == ["qwen3:1.7b"]
    lang.cb(40, "pulling")
    assert w.panel._pct == 40
    assert any("ui.ollama.pulling" == s or "model" in s or "modelo" in s for s in texts(w))
    lang.cb(100, "done")
    w.frame(2.0)
    lang2 = FakeLang(fail=True)
    w2 = make(lang2)
    w2.open_panel("models")
    w2.frame(1.0)
    w2.panel.handle_event(key(pygame.K_TAB))
    assert w2.panel._pct == -1
    assert i18n.t("ui.models.failed") in texts(w2)


def test_ui_lang_switch_changes_strings():
    prev = i18n.get_lang()
    try:
        i18n.set_lang("pt")
        w = make()
        w.open_panel("settings")
        w.frame(1.0)
        before = texts(w)
        w.panel.handle_event(click(w.panel._rows[0][1].center))
        assert i18n.get_lang() == "en" and w.config.ui_lang == "en" and w.saves == 1
        after = texts(w)
        assert before != after and i18n.t("ui.menu.settings") in after
    finally:
        i18n.set_lang(prev)


def test_mute_toggles_growler():
    w = make()
    w.open_panel("settings")
    w.frame(1.0)
    w.panel.handle_event(click(w.panel._rows[1][1].center))
    assert w.growler.muted is True
    w.panel.handle_event(key(pygame.K_DOWN))
    w.panel.handle_event(key(pygame.K_SPACE))  # rest row
    assert w.rest_manual is True
    w.panel.sel = 1
    w.panel.handle_event(key(pygame.K_RETURN))
    assert w.growler.muted is False
    # no digits in normal mode; time-scale row only in dev
    assert not any(re.search(r"\d", s) for s in texts(w))
    w.dev = True
    scales = []
    w.set_time_scale = scales.append
    w.frame(1.0)
    assert len(w.panel._rows) == 4
    w.panel.handle_event(click(w.panel._rows[3][1].center))
    assert scales == [10.0]


def test_models_panel_when_ollama_missing():
    for lang in (FakeLang(status="missing"), None):
        w = make(lang)
        w.open_panel("models")
        assert i18n.t("ui.ollama.missing") in texts(w)
        w.panel.download()
        w.panel.handle_event(key(pygame.K_TAB))
        if lang is not None:
            assert lang.pulled == []
