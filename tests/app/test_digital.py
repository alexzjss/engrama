import re
import pygame
import pytest
from engrama import balance, vocab
from engrama.app import i18n
from engrama.app.art import digital_fx
from engrama.app.digital import DigitalRequests
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, menus

H = 3600.0
LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}
KEY = (255, 0, 255)


class FakeGrowler:
    muted = False

    def growl(self, pitch, kind):
        pass

    def set_muted(self, m):
        pass


def make(snap=None):
    posts = []
    w = Window(lambda: snap or Snapshot(look=LOOK), lambda k, d=None: posts.append((k, d)), growler=FakeGrowler())
    return w, posts


def test_only_ask_attention_opens():
    d = DigitalRequests(1)
    for a in vocab.ACTIONS:
        if a != "ask_attention":
            assert d.on_action_start(a, 10 * H) == ""
    assert d.open == ""


def test_rate_and_gap():
    d = DigitalRequests(7)
    n = 0
    for i in range(1000):
        if d.on_action_start("ask_attention", i * 3 * H):
            n += 1
    assert abs(n / 1000 - balance.DIGITAL_REQUEST_P) <= 0.05
    d = DigitalRequests(7)
    while not d.on_action_start("ask_attention", 0.0):
        d = DigitalRequests(d._rng.random() * 1e6)
    d.tick(balance.DIGITAL_REQUEST_TTL_S + 1)
    assert d.open == ""
    for k in range(50):   # inside the 2 h gap nothing opens
        assert d.on_action_start("ask_attention", 3600.0 + k) == ""


def test_open_blocks_and_expires():
    d = DigitalRequests(2)
    t = 0.0
    while not d.on_action_start("ask_attention", t):
        t += 3 * H
    assert d.open in vocab.DIGITAL_IDS
    assert d.on_action_start("ask_attention", t + 10 * H * 0) == ""
    d.tick(t + balance.DIGITAL_REQUEST_TTL_S - 1)
    assert d.open
    d.tick(t + balance.DIGITAL_REQUEST_TTL_S)
    assert d.open == ""


def test_fulfill_right_and_wrong():
    d = DigitalRequests(3)
    t = 0.0
    while not d.on_action_start("ask_attention", t):
        t += 3 * H
    want = d.open
    other = next(i for i in vocab.DIGITAL_IDS if i != want)
    assert d.fulfill(other, t + 1) is False and d.open == want
    assert d.fulfill(want, t + 2) is True and d.open == ""
    assert d.fulfill(want, t + 3) is False


def test_state_roundtrip():
    a = DigitalRequests(5)
    a.on_action_start("ask_attention", 0.0)
    b = DigitalRequests(99)
    b.load_state_dict(a.state_dict())
    assert b.state_dict() == a.state_dict()
    seq_a = [a.on_action_start("ask_attention", 3 * H * i) for i in range(1, 30)]
    seq_b = [b.on_action_start("ask_attention", 3 * H * i) for i in range(1, 30)]
    assert seq_a == seq_b
    DigitalRequests(1).load_state_dict({})


def test_f1_opens_panel_and_pick_posts():
    w, posts = make()
    got = []
    w.on_digital = got.append
    w.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
    assert w.panel_name == "digital" and isinstance(w.panel, menus.DigitalMenu)
    w.frame()
    w.panel.on_pick("defrag")
    assert ("pet", {"digital": "defrag"}) in posts and got == ["defrag"]
    assert w.digital_fx and w.digital_fx[0] == "defrag"
    assert w.panel is None
    w.frame()


def test_request_bubble_and_fx_frames():
    w, _ = make(Snapshot(look=LOOK, digital_request="cache"))
    w.digital_fx = ("cooler", 0.0)
    w.frame()
    w.digital_fx = ("cooler", 0.0)
    w.frame()


@pytest.mark.parametrize("did", vocab.DIGITAL_IDS)
def test_icons_and_effects_no_colorkey(did):
    ic = digital_fx.icon(did)
    assert ic.get_size() == (10, 10)
    assert any(ic.get_at((x, y)).a for x in range(10) for y in range(10))
    for age in (0.0, 0.3, 0.7, 1.2, 1.7, 1.99):
        s = pygame.Surface((200, 200))
        s.fill((20, 20, 20))
        assert digital_fx.draw_effect(s, did, age, pygame.Rect(60, 60, 80, 80)) is True
        px = pygame.surfarray.array3d(s)
        assert not ((px[:, :, 0] == 255) & (px[:, :, 1] == 0) & (px[:, :, 2] == 255)).any()
    assert digital_fx.draw_effect(pygame.Surface((50, 50)), did, 2.5, pygame.Rect(0, 0, 10, 10)) is False
    for y in range(10):
        for x in range(10):
            c = ic.get_at((x, y))
            assert (c.r, c.g, c.b) != KEY


@pytest.mark.parametrize("lang", ["pt", "en"])
def test_texts_have_no_digits(lang):
    prev = i18n.get_lang()
    i18n.set_lang(lang)
    try:
        texts = [i18n.t("ui.menu.digital")]
        for d in vocab.DIGITAL_IDS:
            texts += [i18n.t(f"digital.{d}"), i18n.t(f"digital.ask.{d}")]
        for t in texts:
            assert not t.startswith("digital.") and not re.search(r"\d", t), t
    finally:
        i18n.set_lang(prev)
