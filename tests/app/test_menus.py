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


# ---------------------------------------------------------------- MVP polish: toolbar, panel chrome, name, help
def test_toolbar_click_toggles_panel_and_switches_between_panels():
    from engrama.app.ui.toolbar import BUTTONS
    w = make()
    w.frame(1.0)
    for bid, _key, _f in BUTTONS:
        w.handle_event(click(w.toolbar._rects[bid].center))
        assert w.panel_name == bid          # also while another panel is open: the toolbar switches
    w.handle_event(click(w.toolbar._rects[BUTTONS[-1][0]].center))
    assert w.panel is None


def test_panel_closes_on_x_and_on_click_outside_but_first_use_is_modal():
    from engrama.app.ui import menus
    w = make()
    w.open_panel("food")
    w.frame(1.0)
    w.handle_event(click(menus.close_rect(w.screen).center))
    assert w.panel is None
    w.open_panel("food")
    w.handle_event(click((5, 200)))
    assert w.panel is None
    w.open_panel("first_use")
    w.handle_event(click((5, 200)))
    assert w.panel_name == "first_use"


def test_toolbar_tooltip_only_on_hover():
    w = make()
    w.frame(1.0)
    assert not any("F4" in s for s in texts(w))
    w.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=w.toolbar._rects["food"].center))
    assert any("F4" in s for s in texts(w))


def test_item_labels_never_overflow_their_cell_in_both_languages():
    from engrama import vocab
    from engrama.app.ui import menus
    w = make()
    rect = pygame.Rect(10, 10, menus.FoodMenu.CELL[0] - 8, menus.FoodMenu.CELL[1] - 8)
    names = [f"food.{f}" for f in (*vocab.FOOD_IDS, vocab.MEDICINE_ID)] + [f"digital.{d}" for d in vocab.DIGITAL_IDS]
    seen = []
    hud.add_text_hook(seen.append)
    try:
        for lang in ("pt", "en"):
            i18n.set_lang(lang)
            for k in names:
                menus.draw_cell_label(w.screen, i18n.t(k), rect)
    finally:
        hud.remove_text_hook(seen.append)
        i18n.set_lang("pt")
    assert len(seen) >= 2 * len(names)
    assert all(hud.font(18).size(s)[0] <= rect.w for s in seen), [s for s in seen if hud.font(18).size(s)[0] > rect.w]


def test_hatch_asks_for_a_name_once_and_the_hud_shows_it():
    saved = []
    w = make()
    w.config.creature_name = ""
    w.save_config = lambda: saved.append(w.config.creature_name)
    w.on_host_event("hatch", {})
    w.frame(1.0)
    assert w.panel_name == "name"
    for ch in "Mika7":
        w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    w.handle_event(key(pygame.K_RETURN))
    assert w.panel is None and w.config.creature_name == "Mika" and saved == ["Mika"]   # digits never enter a name
    w.on_host_event("hatch", {})
    w.frame(1.1)
    assert w.panel is None
    assert "Mika" in texts(w)


def test_persona_prompt_carries_the_name_only_when_set():
    from engrama.services.language.persona import PersonaState, build_messages
    for lang in ("pt", "en"):
        named = build_messages(PersonaState(stage="adult", name="Mika"), [], "oi", lang)[0]["content"]
        plain = build_messages(PersonaState(stage="adult"), [], "oi", lang)[0]["content"]
        assert "Mika" in named and "te deu o nome" not in plain and "named you" not in plain


def test_mind_view_is_fullscreen_so_a_click_inside_does_not_close_it():
    w = make()
    w.open_panel("mind")
    w.frame(1.0)
    w.handle_event(click((5, 200)))
    assert w.panel_name == "mind"
    w.handle_event(click(w.toolbar._rects["mind"].center))
    assert w.panel is None
