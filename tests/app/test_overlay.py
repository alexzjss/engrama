import pygame
import pytest

from engrama import balance
from engrama.app import i18n
from engrama.app.desktop import COLORKEY, FakeDesktop, NullDesktop
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window
from engrama.app.ui.overlay import SCALE, Strip, strip_from_work_area
from engrama.config import Config

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}
WORK = (0, 0, 1280, 680)   # 1280x720 screen with a 40 px taskbar at the bottom


def snap(**kw):
    kw.setdefault("look", LOOK)
    kw.setdefault("stage", "adult")
    return Snapshot(**kw)


class FakeGrowler:
    def growl(self, pitch, kind):
        pass


class CountingDesktop(FakeDesktop):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.cursor_calls = 0
        self.fg_calls = 0

    def cursor(self):
        self.cursor_calls += 1
        return self.cur

    def foreground_rect(self):
        self.fg_calls += 1
        return self.fg


def make(s=None, desktop=None):
    posts, holder, saves = [], {"s": s or snap()}, []
    w = Window(lambda: holder["s"], lambda k, d=None: posts.append((k, d)), growler=FakeGrowler())
    w.desktop = desktop if desktop is not None else FakeDesktop(work=WORK)
    w.config = Config()
    w.config.perception_asked = True
    w.save_config = lambda: saves.append(w.config.display_mode)
    w.saves = saves
    return w, posts, holder


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def motion(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(1, 0), buttons=(1, 0, 0))


def overlay_window(s=None, desktop=None):
    w, posts, h = make(s, desktop)
    assert w.set_mode("overlay")
    w.frame(0.0)
    return w, posts, h


def tick(w, t0, n, step=0.1):
    for i in range(1, n + 1):
        w.frame(t0 + i * step)
    return t0 + n * step


def creature_center(w):
    return w.overlay._creature_screen_rect().center


def click_creature(w):
    c = creature_center(w)
    w.handle_event(down(c))
    w.handle_event(up(c))


def inside(rect, area):
    x, y, ww, hh = rect
    ax, ay, aw, ah = area
    return x >= ax and y >= ay and x + ww <= ax + aw and y + hh <= ay + ah


# ------------------------------------------------------------------ strip
@pytest.mark.parametrize("area", [(0, 0, 1920, 1040),        # bar at the bottom
                                  (0, 48, 1920, 1032),       # bar on top
                                  (64, 0, 1856, 1080),       # bar on the left
                                  (0, 0, 1856, 1080),        # bar on the right
                                  (0, 0, 120, 90)])          # tiny area, smaller than the sprite
def test_strip_keeps_creature_inside_area(area):
    sp = 160
    st = strip_from_work_area(area, sp)
    x, y, w, h = area
    assert isinstance(st, Strip) and st.floor_y == y + h
    assert x <= st.x0 <= st.x1 <= x + w
    assert st.x0 - min(sp // 2, w // 2) >= x and st.x1 + min(sp // 2, w // 2) <= x + w


# ------------------------------------------------------------------ mode switching
def test_f11_toggles_and_saves_mode():
    w, _, _ = make()
    w.frame(0.0)
    w.handle_event(key(pygame.K_F11))
    assert w.mode == "overlay" and w.config.display_mode == "overlay" and w.saves == ["overlay"]
    assert w.screen.get_size() == w.overlay.size and ("make_overlay", 0) in w.desktop.calls
    w.frame(0.1)
    w.handle_event(key(pygame.K_F11))
    assert w.mode == "terrarium" and w.config.display_mode == "terrarium" and w.saves == ["overlay", "terrarium"]
    assert ("restore", 0) in w.desktop.calls
    assert w.screen.get_size() == w.size
    w.frame(0.2)


def test_unavailable_warns_and_stays_in_terrarium():
    w, _, _ = make(desktop=NullDesktop())
    assert w.set_mode("overlay") is False
    assert w.mode == "terrarium" and w.saves == []
    assert w._notice[0] == i18n.t("ui.overlay.unavailable")
    w.handle_event(key(pygame.K_F11))
    assert w.mode == "terrarium"
    w.frame(1.0)


def test_unknown_mode_rejected():
    w, _, _ = make()
    assert w.set_mode("xyz") is False and w.mode == "terrarium"


def test_settings_panel_switches_mode():
    w, _, _ = make()
    w.open_panel("settings")
    w.frame(0.0)
    item = [i for i, (k, _r) in enumerate(w.panel._rows) if k == "overlay"]
    assert item, "overlay row missing when the desktop is available"
    w.panel.handle_event(down(w.panel._rows[item[0]][1].center))
    assert w.mode == "overlay" and w.config.display_mode == "overlay"
    # not offered when the overlay cannot work
    w2, _, _ = make(desktop=NullDesktop())
    w2.open_panel("settings")
    w2.frame(0.0)
    assert all(k != "overlay" for k, _r in w2.panel._rows)


# ------------------------------------------------------------------ fullscreen
def test_fullscreen_hides_and_returns():
    w, _, h = overlay_window()
    h["s"] = snap(fullscreen=True)
    w.frame(0.1)
    assert w.desktop.calls[-1] == ("show", 0, False) and w.overlay.hidden
    n = len(w.desktop.calls)
    w.frame(0.2)
    assert len(w.desktop.calls) == n   # nothing repeated while hidden
    h["s"] = snap(fullscreen=False)
    w.frame(0.3)
    assert ("show", 0, True) in w.desktop.calls and not w.overlay.hidden


# ------------------------------------------------------------------ clicks and mini-menu
def test_click_outside_creature_does_nothing():
    w, posts, _ = overlay_window()
    w.handle_event(down((2, 2)))
    w.handle_event(up((2, 2)))
    assert not w.overlay.menu_open and [p for p in posts if p[0] != "user_active"] == [] and w.panel is None


def test_click_on_creature_opens_menu_and_items_post():
    w, posts, _ = overlay_window()
    click_creature(w)
    assert w.overlay.menu_open
    w.frame(0.1)
    rects = dict(w.overlay._menu_rects)
    assert set(rects) == {"food", "remedio", "digital", "talk", "terrarium"}
    assert not [p for p in posts if p[0] != "user_active"]

    w.handle_event(down(rects["remedio"].center))
    assert ("food", {"food": "remedio"}) in posts and not w.overlay.menu_open

    click_creature(w)
    w.frame(0.2)
    w.handle_event(down(dict(w.overlay._menu_rects)["food"].center))
    assert w.panel_name == "food"
    w.frame(0.3)
    w.handle_event(key(pygame.K_RETURN))
    assert any(p[0] == "food" and p[1]["food"] != "remedio" for p in posts) and w.panel is None

    click_creature(w)
    w.frame(0.4)
    w.handle_event(down(dict(w.overlay._menu_rects)["digital"].center))
    assert w.panel_name == "digital"
    w.frame(0.5)
    w.handle_event(key(pygame.K_RETURN))
    assert any(p[0] == "pet" and p[1] and "digital" in p[1] for p in posts)

    w.frame(0.6)
    click_creature(w)
    w.frame(0.7)
    w.handle_event(down(dict(w.overlay._menu_rects)["terrarium"].center))
    assert w.mode == "terrarium"


def test_menu_hides_medicine_for_egg_and_egg_click_posts_click():
    w, posts, _ = overlay_window(snap(stage="egg"))
    x0 = w.overlay.x
    tick(w, 0.0, 10)
    assert w.overlay.x == x0   # the egg stays still
    c = creature_center(w)
    w.handle_event(down(c))
    assert ("click", None) in posts and not w.overlay.menu_open


def test_menu_for_egg_has_no_medicine():
    w, _, _ = overlay_window(snap(stage="egg"))
    keys = [k for k, _l in w.overlay._menu_items(w._snap)]
    assert "remedio" not in keys and "food" in keys


def test_talk_opens_chat_and_text_reaches_it_only_then():
    w, posts, _ = overlay_window()
    w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="oi"))
    assert w.chat.text == ""             # chat is deaf while the box is closed
    click_creature(w)
    w.frame(0.1)
    w.handle_event(down(dict(w.overlay._menu_rects)["talk"].center))
    assert w.overlay.chat_open
    w.frame(0.2)
    w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="oi"))
    assert w.chat.text == "oi"
    w.handle_event(key(pygame.K_ESCAPE))
    assert not w.overlay.chat_open


@pytest.mark.parametrize("stage", ["baby", "adult", "final"])
def test_window_with_menu_chat_or_panel_stays_inside_area(stage):
    w, _, _ = overlay_window(snap(stage=stage))
    ov = w.overlay
    ov.x = ov.strip.x1            # right edge of the strip
    w.frame(0.1)
    click_creature(w)
    w.frame(0.2)
    assert inside(ov.rect, WORK)
    ov.menu_open, ov.chat_open = False, True
    w.frame(0.3)
    assert inside(ov.rect, WORK)
    ov.chat_open = False
    w.open_panel("food")
    w.frame(0.4)
    assert inside(ov.rect, WORK) and w.screen.get_size() == (ov.rect[2], ov.rect[3])
    ov.x = ov.strip.x0
    w.frame(0.5)
    assert inside(ov.rect, WORK)


def test_window_clipped_to_small_work_area():
    w, _, _ = make(desktop=FakeDesktop(work=(100, 50, 360, 300)))
    assert w.set_mode("overlay")
    w.open_panel("food")
    w.frame(0.0)
    w.frame(0.1)
    assert inside(w.overlay.rect, (100, 50, 360, 300))


def test_odd_work_areas_bar_on_top_and_side():
    for area in ((0, 48, 1280, 672), (64, 0, 1216, 720)):
        w, _, _ = make(desktop=FakeDesktop(work=area))
        assert w.set_mode("overlay")
        for t in range(1, 6):
            w.frame(t * 0.1)
        ov = w.overlay
        assert inside(ov.rect, area) and ov.rect[1] + ov.rect[3] == area[1] + area[3]


# ------------------------------------------------------------------ drawing
def test_background_is_exactly_colorkey_outside_creature():
    w, _, _ = overlay_window()
    tick(w, 0.0, 5)
    scr = w.screen
    assert scr.get_at((0, 0))[:3] == COLORKEY and scr.get_at((scr.get_width() - 1, 5))[:3] == COLORKEY
    cr = w.overlay._creature_screen_rect().inflate(160, 160)
    bad = 0
    for x in range(0, scr.get_width(), 3):
        for y in range(0, scr.get_height(), 3):
            if not cr.collidepoint(x, y) and scr.get_at((x, y))[:3] != COLORKEY:
                bad += 1
    assert bad == 0
    # something other than the key is painted where the creature stands
    cx, cy = creature_center(w)
    colours = {tuple(scr.get_at((cx + dx, cy + dy)))[:3] for dx in range(-20, 21, 4) for dy in range(-20, 21, 4)}
    assert colours - {COLORKEY}


def test_creature_never_painted_with_colorkey():
    w, _, h = overlay_window()
    for stage in ("baby", "child", "adult", "perfect", "final"):
        for action in ("idle", "wander", "play_alone", "sleep"):
            h["s"] = snap(stage=stage, action=action, asleep=action == "sleep")
            w.frame(1.0)
            low = pygame.Surface(w.overlay.low.get_size())
            low.fill((0, 0, 0))   # draw on black: any COLORKEY pixel left is the creature's own
            w.overlay.scene.draw(low, h["s"], 1.0, background=False, ground=low.get_height(), pos_x=low.get_width() // 2)
            assert pygame.mask.from_threshold(low, COLORKEY, (1, 1, 1, 255)).count() == 0


def test_frames_render_for_all_stages_dead_and_hide():
    w, _, h = overlay_window()
    for stage in ("egg", "baby", "child", "adult", "perfect", "final"):
        for action in ("idle", "wander", "explore", "sleep", "hide", "ask_attention", "play_alone", "show_something"):
            h["s"] = snap(stage=stage, action=action, asleep=action == "sleep", digital_request="ram")
            tick(w, 0.0, 3)
            assert inside(w.overlay.rect, WORK)
    w.farewell_text = "adeus"
    skipped = []
    w.on_farewell_skip = lambda: skipped.append(1)
    h["s"] = snap(dead=True)
    t = 0.0
    for _ in range(25):
        t = tick(w, t, 1)
    assert w.scene is not w.overlay.scene
    w.handle_event(down((5, 5)))
    assert skipped == [1]


# ------------------------------------------------------------------ polling and placement
def test_place_only_when_rect_changes():
    w, _, _ = overlay_window()
    tick(w, 0.0, 20)
    places = [c for c in w.desktop.calls if c[0] == "place"]
    n = len(places)
    tick(w, 5.0, 30)
    assert len([c for c in w.desktop.calls if c[0] == "place"]) == n
    w.overlay.x += 60
    w.frame(9.0)
    assert len([c for c in w.desktop.calls if c[0] == "place"]) == n + 1


def test_cursor_polled_at_most_poll_hz_and_only_in_overlay():
    d = CountingDesktop(work=WORK, cur=(10, 10))
    w, _, _ = make(desktop=d)
    for i in range(30):
        w.frame(i * 0.05)
    assert d.cursor_calls == 0           # terrarium never looks at the cursor
    assert w.set_mode("overlay")
    d.cursor_calls = 0
    for i in range(1, 121):               # 6 s at 20 fps
        w.frame(10.0 + i * 0.05)
    assert 0 < d.cursor_calls <= 6 * balance.CURSOR_POLL_HZ + 1


def test_wander_walks_inside_strip_and_faces_direction():
    w, _, h = overlay_window(snap(action="wander"))
    ov = w.overlay
    xs = []
    t = 0.0
    for _ in range(200):
        t = tick(w, t, 1)
        xs.append(ov.x)
        assert ov.strip.x0 <= ov.x <= ov.strip.x1
    assert max(xs) - min(xs) > 100
    step = max(abs(b - a) for a, b in zip(xs, xs[1:]))
    assert step <= balance.OVERLAY_WALK_PX_S * 0.1 + 1e-6


def test_idle_stays_put():
    w, _, _ = overlay_window(snap(action="idle"))
    x = w.overlay.x
    tick(w, 0.0, 30)
    assert w.overlay.x == x


def test_hide_slides_to_edge_showing_half():
    w, _, h = overlay_window(snap(action="hide"))
    tick(w, 0.0, 400)
    ov = w.overlay
    assert ov.x in (WORK[0], WORK[0] + WORK[2]) and inside(ov.rect, WORK)
    h["s"] = snap(action="idle")
    tick(w, 50.0, 400)
    assert ov.strip.x0 <= ov.x <= ov.strip.x1


def test_nap_clock_goes_to_strip_end_before_sleeping():
    w, _, h = overlay_window(snap(action="sleep", asleep=True))
    w.variant = "nap_clock"
    w._variant_key = (w._snap.action, w._snap.stage)
    tick(w, 0.0, 400)
    assert w.overlay.x == w.overlay.strip.x1


def test_chase_follows_cursor_within_strip():
    d = FakeDesktop(work=WORK, cur=(300, 600))
    w, _, h = overlay_window(snap(action="explore"), d)
    w.variant = "chase"
    w._variant_key = ("explore", "adult")
    tick(w, 0.0, 300)
    assert abs(w.overlay.x - 300) < 2
    d.cur = (-4000, 600)
    tick(w, 30.0, 400)
    assert w.overlay.x == w.overlay.strip.x0
    d.cur = (99999, 600)
    tick(w, 60.0, 600)
    assert w.overlay.x == w.overlay.strip.x1


def test_look_cursor_flips_sprite_toward_cursor():
    d = FakeDesktop(work=WORK, cur=(0, 600))
    w, _, _ = overlay_window(snap(action="idle"), d)
    w.variant = "look_cursor"
    w._variant_key = ("idle", "adult")
    tick(w, 0.0, 5)
    assert w.overlay.facing == -1
    d.cur = (WORK[2], 600)
    tick(w, 5.0, 5)
    assert w.overlay.facing == 1


def test_peek_needs_permission():
    fg = (700, 100, 400, 300)
    d = CountingDesktop(work=WORK, cur=None, fg=fg)
    w, _, h = overlay_window(snap(action="explore", pad=(0.5, 0.0, 0.0)), d)
    assert w.config.permissions["active_window"] is False
    seen = set()
    for i in range(60):
        h["s"] = snap(action="explore" if i % 2 == 0 else "idle", pad=(0.5, 0.0, 0.0))
        w.frame(i * 0.5)
        seen.add(w.variant)
    assert "peek" not in seen and d.fg_calls == 0   # never even asks the OS for the foreground window

    w.config.permissions["active_window"] = True
    seen.clear()
    for i in range(80):
        h["s"] = snap(action="explore" if i % 2 == 0 else "idle")
        w.frame(100 + i * 0.5)
        seen.add(w.variant)
    assert "peek" in seen and d.fg_calls > 0

    # and it walks to the centre of the foreground window
    h["s"] = snap(action="explore")
    w.variant = "peek"
    w._variant_key = ("explore", "adult")
    tick(w, 500.0, 400)
    assert abs(w.overlay.x - (fg[0] + fg[2] / 2)) < 2


# ------------------------------------------------------------------ variants in the terrarium
def test_terrarium_picks_variant_on_action_change():
    w, _, h = make(snap(action="idle", pad=(0.6, 0, 0)))
    seen = []
    for i in range(60):
        h["s"] = snap(action="play_alone" if i % 2 else "idle", pad=(0.6, 0, 0))
        w.frame(i * 0.1)
        seen.append(w.variant)
    assert w.variant_n == 60
    assert set(seen) - {""}                              # something other than "no variant" shows up
    assert not set(seen) & {"nap_clock", "chase", "look_cursor", "peek"}   # overlay-only variants stay out
    n = w.variant_n
    w.frame(10.0)
    w.frame(10.1)
    assert w.variant_n == n                              # same action: no re-roll


def test_leave_resets_and_enter_again_works():
    w, _, _ = overlay_window()
    assert w.set_mode("terrarium")
    assert w.set_mode("overlay")
    w.frame(1.0)
    assert w.screen.get_size() == w.overlay.size
    w.set_mode("terrarium")
    assert w.screen.get_size() == w.size
