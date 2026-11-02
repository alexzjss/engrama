import queue
import pygame
from engrama.app import i18n
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud
from engrama.services.language.lang import detect_lang
from engrama.services.language.persona import valence
from engrama.services.language.service import Reply

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


class FakeGrowler:
    def __init__(self):
        self.calls = []

    def growl(self, pitch, kind):
        self.calls.append(kind)


class FakeLang:
    def __init__(self, status="ready"):
        self.status = status
        self.replies = queue.Queue()
        self.requests = []

    def request(self, text):
        self.requests.append(text)


def make(status="ready"):
    posts, lang, g = [], FakeLang(status), FakeGrowler()
    w = Window(lambda: Snapshot(look=LOOK), lambda k, d=None: posts.append((k, d)), language=lang, growler=g,
               valence_fn=lambda s: valence(s, detect_lang(s)))
    return w, posts, lang, g


def type_text(w, s):
    w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=s))


def enter(w, mod=0):
    w.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=mod))


def messages(posts):
    return [d for k, d in posts if k == "message"]


def test_send_posts_message_event_with_valence():
    w, posts, lang, _ = make()
    type_text(w, "eu te amo")
    enter(w)
    type_text(w, "você é chato")
    enter(w)
    m = messages(posts)
    assert m[0]["valence"] > 0 and m[1]["valence"] < 0
    assert lang.requests == ["eu te amo", "você é chato"]


def test_reply_becomes_bubble():
    w, _, lang, _ = make()
    lang.replies.put(Reply("oi amigo", "pt", "llm"))
    w.frame(1.0)
    assert w.chat.bubble == "oi amigo" and w.chat.bubble_until == 1.0 + 4 + 0.3 * 2
    w.frame(1.0 + 4.7)
    seen = []
    hud.add_text_hook(seen.append)
    try:
        w.frame(2.0)
        assert "oi amigo" in seen
        seen.clear()
        w.frame(10.0)
        assert seen.count("oi amigo") == 1  # only in the history line, no bubble
    finally:
        hud.remove_text_hook(seen.append)


def test_babble_reply_also_bubbles():
    w, _, lang, _ = make()
    lang.replies.put(Reply("grr", "pt", "babble"))
    w.frame(1.0)
    assert w.chat.bubble == "grr"


def test_long_and_emoji_input_safe():
    w, posts, lang, _ = make()
    type_text(w, "a" * 600)
    enter(w)
    assert len(lang.requests[0]) == 500
    lang.replies.put(Reply("oi \U0001F600 você", "pt", "llm"))
    w.frame(1.0)
    assert "\U0001F600" not in w.chat.bubble and "oi" in w.chat.bubble


def test_empty_enter_does_nothing():
    w, posts, lang, _ = make()
    enter(w)
    type_text(w, "   ")
    enter(w)
    assert lang.requests == [] and messages(posts) == []


def test_status_line_shows_ollama_missing():
    w, _, _, _ = make("missing")
    seen = []
    hud.add_text_hook(seen.append)
    try:
        w.frame(1.0)
    finally:
        hud.remove_text_hook(seen.append)
    assert i18n.t("ui.ollama.missing") in seen


def test_talk_growl_on_reply():
    w, _, lang, g = make()
    lang.replies.put(Reply("oi", "pt", "llm"))
    w.frame(1.0)
    assert "talk" in g.calls


def test_shift_enter_newline_and_backspace():
    w, _, lang, _ = make()
    type_text(w, "ab")
    enter(w, pygame.KMOD_SHIFT)
    assert w.chat.text == "ab\n" and lang.requests == []
    w.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE))
    assert w.chat.text == "ab"


class BusyLang(FakeLang):
    busy = False


def _thinking_frame(busy, replies=False):
    lang = BusyLang()
    lang.busy = busy
    w = Window(lambda: Snapshot(look=LOOK, stage="baby"), lambda k, d=None: None, language=lang,
               growler=FakeGrowler())
    seen = []
    hud.add_text_hook(seen.append)
    try:
        w.frame(1.0)
        w.frame(1.0)
    finally:
        hud.remove_text_hook(seen.append)
    return w, pygame.image.tostring(w.screen, "RGB"), seen


def test_thinking_bubble_drawn_while_busy_without_digits():
    _, idle_img, _ = _thinking_frame(False)
    _, busy_img, seen = _thinking_frame(True)
    assert busy_img != idle_img
    assert not any(c.isdigit() for s in seen for c in s)


def test_thinking_dots_animate_and_yield_to_speech():
    lang = BusyLang()
    lang.busy = True
    w = Window(lambda: Snapshot(look=LOOK, stage="baby"), lambda k, d=None: None, language=lang,
               growler=FakeGrowler())
    calls = []
    orig = w.chat._draw_thinking
    w.chat._draw_thinking = lambda *a: (calls.append(a[-1]), orig(*a))
    w.frame(1.0)
    w.frame(1.4)
    assert len(calls) == 2
    w.chat.bubble, w.chat.bubble_until = "oi", 1e9
    w.frame(1.5)
    assert len(calls) == 2          # a speech bubble replaces the dots
    lang.busy = False
    w.chat.bubble_until = 0.0
    w.frame(1.6)
    assert len(calls) == 2
