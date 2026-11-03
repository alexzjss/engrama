"""M9 F5: the 'Busca por significado' block of the models panel (download, model choice, on/off)."""
import re

import pygame

from engrama.app import i18n
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


class FakeGrowler:
    muted = False

    def growl(self, pitch, kind):
        pass

    def set_muted(self, m):
        self.muted = m


class FakeConfig:
    model = "qwen3:1.7b"
    recommended_models = ("qwen3:1.7b", "qwen3:0.6b")
    embed_model = "embeddinggemma"
    semantic_recall = True
    recommended_embed_models = ("embeddinggemma", "nomic-embed-text", "bge-m3")
    ui_lang = None


class FakeLang:
    def __init__(self, status="ready", installed=None, embed_status="ready"):
        self.status = status
        self._installed = installed
        self.embed_status = embed_status
        self.pulled, self.embed_models, self.toggles = [], [], []

    def installed_models(self):
        return self._installed

    def pull(self, name, on_progress):
        self.pulled.append(name)

    def set_embed_model(self, name):
        self.embed_models.append(name)

    def set_semantic_recall(self, on):
        self.toggles.append(on)


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


def test_embed_block_shows_missing_and_download():
    lang = FakeLang(installed={"qwen3:1.7b"})
    w = make(lang)
    w.open_panel("models")
    w.frame(1.0)
    out = texts(w)
    assert i18n.t("ui.models.embed_title") in out
    assert i18n.t("ui.models.embed_hint") in out
    assert i18n.t("ui.models.embed_missing") in out
    w.panel.handle_event(click(w.panel._embed_dl_rect.center))
    assert lang.pulled == ["embeddinggemma"]


def test_embed_installed_accepts_latest_tag():
    lang = FakeLang(installed={"embeddinggemma:latest"})
    w = make(lang)
    w.open_panel("models")
    w.frame(1.0)
    assert i18n.t("ui.models.embed_missing") not in texts(w)


def test_embed_select_and_toggle_save_config():
    lang = FakeLang(installed={"embeddinggemma"})
    w = make(lang)
    w.open_panel("models")
    w.frame(1.0)
    w.panel.handle_event(click(w.panel._embed_model_rect.center))
    assert lang.embed_models == ["nomic-embed-text"]
    assert w.config.embed_model == "nomic-embed-text" and w.saves == 1
    w.panel.handle_event(click(w.panel._embed_sw_rect.center))
    assert lang.toggles == [False] and w.config.semantic_recall is False and w.saves == 2
    w.frame(1.0)
    assert i18n.t("ui.models.embed_off") in texts(w)
    w.panel.handle_event(click(w.panel._embed_sw_rect.center))
    assert lang.toggles == [False, True] and w.config.semantic_recall is True and w.saves == 3


def test_embed_keyboard_focus_moves_and_returns_to_chat_list():
    lang = FakeLang(installed={"embeddinggemma"})
    w = make(lang)
    w.open_panel("models")
    w.frame(1.0)
    w.panel.handle_event(click(w.panel._embed_model_rect.center))   # focus on the embed block
    assert w.panel.embed_focus is True
    w.panel.handle_event(key(pygame.K_RIGHT))
    assert lang.embed_models == ["nomic-embed-text", "bge-m3"]
    w.panel.handle_event(key(pygame.K_DOWN))                      # download row
    w.panel.handle_event(key(pygame.K_DOWN))                      # switch row
    w.panel.handle_event(key(pygame.K_RETURN))
    assert lang.toggles == [False]
    w.panel.handle_event(key(pygame.K_DOWN))                      # past the last embed row: back to chat
    assert w.panel.embed_focus is False


def test_chat_models_flow_still_wraps_without_embed_focus():
    lang = FakeLang(installed={"qwen3:0.6b"})
    w = make(lang)
    w.open_panel("models")
    w.frame(1.0)
    w.panel.sel = 2                                              # custom row (last)
    w.panel.handle_event(key(pygame.K_DOWN))
    assert w.panel.sel == 0 and w.panel.embed_focus is False
    assert lang.embed_models == [] and lang.toggles == []


def test_embed_block_without_language_disabled():
    w = make(None)
    w.open_panel("models")
    out = texts(w)
    assert i18n.t("ui.ollama.missing") in out
    assert i18n.t("ui.models.embed_title") in out
    w.panel.handle_event(click((5, 5)))
    w.panel.handle_event(key(pygame.K_TAB))
    assert w.config.embed_model == "embeddinggemma" and w.saves == 0


def test_embed_block_no_digits_in_its_texts_beyond_model_names():
    w = make(FakeLang(installed={"embeddinggemma"}))
    w.open_panel("models")
    w.frame(1.0)
    out = [s for s in texts(w) if s not in ("embeddinggemma", "nomic-embed-text", "bge-m3", "qwen3:1.7b", "qwen3:0.6b")]
    assert not any(re.search(r"\d", s) for s in out)
