import hashlib
import re
from types import SimpleNamespace
import pygame
from engrama.app import i18n
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud
from engrama.config import Config

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}
SOURCES = ("process", "active_window", "idle", "time", "system_load")


class FakeGrowler:
    muted = False

    def growl(self, pitch, kind):
        pass

    def set_muted(self, m):
        pass


class FakeProvider:
    def __init__(self, err=""):
        self.calls = []
        self.err = err

    def silenced_themes(self):
        return ["musica"]

    def unsilence_theme(self, name):
        self.calls.append(("unsilence", name))

    def clear_app_categories(self):
        self.calls.append(("clear", None))

    def hotkey_error(self):
        return self.err


def make(snap=None, asked=False, posts=None):
    snap = snap or Snapshot(look=LOOK)
    w = Window(lambda: snap, lambda k, d=None: posts.append(k) if posts is not None else None,
               growler=FakeGrowler())
    w.config = Config(perception_asked=asked)
    w.saves = 0
    w.save_config = lambda: setattr(w, "saves", w.saves + 1)
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


def test_first_use_opens_until_answered_and_saves():
    w = make()
    w.frame(1.0)
    assert w.panel_name == "first_use"
    for i in range(5):
        w.handle_event(key(pygame.K_y if i % 2 == 0 else pygame.K_n))
    assert w.panel is None
    assert w.config.perception_asked is True
    assert w.config.permissions == {"process": True, "active_window": False, "idle": True, "time": False,
                                    "system_load": True}
    assert w.saves >= 1
    w.frame(2.0)
    assert w.panel is None


def test_close_without_answer_means_not_now():
    w = make()
    w.frame(1.0)
    w.handle_event(key(pygame.K_y))
    w.handle_event(key(pygame.K_ESCAPE))
    assert w.panel is None
    assert w.config.perception_asked is True
    assert w.config.permissions["process"] is True
    assert not any(w.config.permissions[s] for s in SOURCES[1:])


def test_first_use_is_modal_but_f9_works():
    posts = []
    w = make(posts=posts)
    eyes = []
    w.set_eyes_closed = eyes.append
    w.frame(1.0)
    r = w.scene.creature_rect
    w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(r.centerx * 4, r.centery * 4), button=1))
    w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="oi"))
    w.handle_event(key(pygame.K_F7))
    assert w.panel_name == "first_use"
    assert not any(p in ("pet", "click") for p in posts)
    assert w.chat.input_text == "" if hasattr(w.chat, "input_text") else True
    w.handle_event(key(pygame.K_F9))
    assert eyes == [True]
    w.frame(2.0)  # simulation keeps going
    assert w.panel_name == "first_use"


def test_f9_uses_config_state_then_snapshot():
    w = make(asked=True)
    eyes = []
    w.set_eyes_closed = eyes.append
    w.config.eyes_closed = True
    w.handle_event(key(pygame.K_F9))
    assert eyes == [False]
    w2 = Window(lambda: Snapshot(look=LOOK, eyes_closed=True), lambda k, d=None: None, growler=FakeGrowler())
    w2.set_eyes_closed = eyes.append
    w2.frame(1.0)
    w2.handle_event(key(pygame.K_F9))
    assert eyes[-1] is False


def test_toggle_permission_saves_config():
    w = make(asked=True)
    w.frame(1.0)
    w.handle_event(key(pygame.K_F8))
    assert w.panel_name == "permissions"
    w.frame(1.0)
    assert w.config.permissions["process"] is False
    w.handle_event(key(pygame.K_RETURN))
    assert w.config.permissions["process"] is True
    assert w.saves == 1
    w.handle_event(key(pygame.K_DOWN))
    w.handle_event(key(pygame.K_SPACE))
    assert w.config.permissions["active_window"] is True
    for _ in range(4):
        w.handle_event(key(pygame.K_DOWN))
    w.frame(1.0)
    w.handle_event(key(pygame.K_RETURN))
    assert w.config.perception_interval_s == 60.0


def test_blocklist_add_remove():
    w = make(asked=True)
    w.open_panel("permissions")
    w.frame(1.0)
    for _ in range(6):
        w.handle_event(key(pygame.K_DOWN))
    w.frame(1.0)
    w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="banco"))
    w.handle_event(key(pygame.K_RETURN))
    assert w.config.perception_blocklist == ["banco"]
    w.frame(1.0)
    w.handle_event(key(pygame.K_DOWN))
    w.handle_event(key(pygame.K_DELETE))
    assert w.config.perception_blocklist == []


def test_unsilence_theme_calls_provider():
    w = make(asked=True)
    prov = FakeProvider()
    w.perception_provider = prov
    w.open_panel("permissions")
    w.frame(1.0)
    assert "musica" in texts(w)
    theme_idx = next(i for i, (k, _) in enumerate(w.panel._kinds) if k == "theme")
    clear_idx = next(i for i, (k, _) in enumerate(w.panel._kinds) if k == "clear")
    w.panel.sel = theme_idx
    w.handle_event(key(pygame.K_RETURN))
    w.panel.sel = clear_idx
    w.handle_event(key(pygame.K_RETURN))
    assert prov.calls == [("unsilence", "musica"), ("clear", None)]


def test_no_digits_in_permissions_panel_normal_mode():
    w = make(asked=True)
    w.config.perception_blocklist = ["app42"]
    w.perception_provider = FakeProvider()
    w.open_panel("permissions")
    w.frame(1.0)
    out = texts(w)
    assert out
    assert not [t for t in out if re.search(r"\d", t)]
    for lang in ("pt", "en"):
        i18n.set_lang(lang)
        try:
            out = texts(w)
            assert not [t for t in out if re.search(r"\d", t)]
        finally:
            i18n.set_lang("pt")
    w.dev = True
    assert any(re.search(r"\d", t) for t in texts(w))


def test_first_use_texts_have_no_digits():
    w = make()
    w.frame(1.0)
    assert not [t for t in texts(w) if re.search(r"\d", t)]


def _hash(snap):
    w = Window(lambda: snap, lambda k, d=None: None, growler=FakeGrowler())
    w.scene.draw(w.low, snap, 1.0)
    return hashlib.md5(pygame.image.tobytes(w.low, "RGB")).hexdigest()


def test_eyes_closed_drawn_changes_frame():
    base = dict(look=LOOK, stage="baby", action="idle")
    assert _hash(Snapshot(**base)) != _hash(Snapshot(**base, eyes_closed=True))


def test_dropfile_calls_handler():
    w = make(asked=True)
    got = []
    w.on_file_drop = lambda p: got.append(p)
    w.handle_event(pygame.event.Event(pygame.DROPFILE, file="C:/x/a.txt"))
    assert got == ["C:/x/a.txt"]
    w.on_file_drop = lambda p: False
    w.handle_event(pygame.event.Event(pygame.DROPFILE, file="C:/x/b.bin"))
    assert i18n.t("ui.file.refused") in texts(w)
    w.on_file_drop = None
    w.handle_event(pygame.event.Event(pygame.DROPFILE, file="C:/x/c.txt"))  # no crash


def test_hotkey_failed_notice():
    w = make(asked=True)
    w.perception_provider = FakeProvider(err="boom")
    w.open_panel("permissions")
    assert i18n.t("ui.perm.hotkey_failed") in texts(w)
    w.perception_provider = FakeProvider(err="")
    assert i18n.t("ui.perm.hotkey_failed") not in texts(w)
