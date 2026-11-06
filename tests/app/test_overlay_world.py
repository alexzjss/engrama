"""M17: the overlay creature walks on the desktop world (fake window geometry, no OS)."""
from engrama import balance
from engrama.app.desktop import FakeDesktop, Desktop, NullDesktop
from engrama.app.ui.overlay import TIGHT_H, TIGHT_W

from tests.app.test_overlay import WORK, overlay_window, snap, tick

WIN = (400, 300, 500, 300)     # top edge at y = 300, plenty of room above for the 96 px body


def world(wins, **kw):
    desk = FakeDesktop(work=WORK, wins=wins)
    s = snap(action="wander", **kw)
    w, posts, holder = overlay_window(s, desk)
    t = tick(w, 0.0, 6)                    # poll windows and cursor
    return w, desk, holder, t


def test_desktop_windows_default_is_empty_and_geometry_only():
    assert Desktop().windows() == [] and NullDesktop().windows() == []
    assert FakeDesktop(wins=[(1, 2, 3, 4)]).windows() == [(1, 2, 3, 4)]


def test_surfaces_are_the_visible_window_tops():
    w, desk, _, _ = world([WIN])
    ov = w.overlay
    assert [(round(s.x0), round(s.x1), s.y) for s in ov.surfaces] == [(404, 896, 300)]
    assert ov.feet == WORK[1] + WORK[3]


def test_hops_onto_a_window_and_the_overlay_follows_it_up():
    w, desk, _, t = world([WIN])
    ov = w.overlay
    ov.walker.goal = ov.surfaces[0]
    t = tick(w, t, 40)
    assert ov.feet == 300 and not ov.airborne
    assert ov.rect[1] + ov.rect[3] == 300            # window bottom sits on the ledge
    assert 404 <= ov.x <= 896


def test_falls_back_to_the_strip_when_the_window_goes_away():
    w, desk, _, t = world([WIN])
    ov = w.overlay
    ov.walker.goal = ov.surfaces[0]
    t = tick(w, t, 40)
    assert ov.feet == 300
    desk.wins = []
    t = tick(w, t, 40)
    assert ov.feet == WORK[1] + WORK[3] and not ov.airborne


def test_sleeping_creature_goes_down_to_a_corner_of_the_floor():
    w, desk, holder, t = world([WIN])
    ov = w.overlay
    ov.walker.goal = ov.surfaces[0]
    t = tick(w, t, 40)
    assert ov.feet == 300
    holder["s"] = snap(action="sleep", asleep=True)
    t = tick(w, t, 400)
    st = ov.strip
    assert ov.feet == st.floor_y
    assert min(ov.x - st.x0, st.x1 - ov.x) < 2


def test_windows_are_polled_at_most_twice_a_second():
    class Counting(FakeDesktop):
        n = 0

        def windows(self):
            Counting.n += 1
            return super().windows()

    desk = Counting(work=WORK, wins=[WIN])
    w, _, _ = overlay_window(snap(action="wander"), desk)
    Counting.n = 0
    tick(w, 0.0, 100)                                 # 10 s of frames
    assert Counting.n <= 10 * balance.WINDOWS_POLL_HZ + 2


def test_skittish_creature_runs_from_a_near_cursor():
    desk = FakeDesktop(work=WORK)
    w, _, _ = overlay_window(snap(action="wander", branch="arisco"), desk)
    ov = w.overlay
    tick(w, 0.0, 3)
    x0 = ov.x
    desk.cur = (int(x0) - 40, int(ov.feet) - 40)      # cursor right next to it, on the left
    tick(w, 0.3, 10)
    assert ov.x > x0 + 20


def test_playful_creature_follows_the_cursor():
    desk = FakeDesktop(work=WORK)
    w, _, _ = overlay_window(snap(action="wander", branch="brincalhao"), desk)
    ov = w.overlay
    tick(w, 0.0, 3)
    x0 = ov.x
    desk.cur = (int(x0) + 120, int(ov.feet) - 40)
    tick(w, 0.3, 15)
    assert ov.x > x0 + 20


def test_window_stays_tight_when_clicks_cannot_pass_through():
    class Opaque(FakeDesktop):
        click_through = False

    w, _, _ = overlay_window(snap(action="idle"), Opaque(work=WORK))
    ov = w.overlay
    sp = ov._sprite_px(w._snap)
    assert ov.size == ((sp + TIGHT_W) // 4 * 4, (sp + TIGHT_H) // 4 * 4)
    ov.menu_open = True
    w.frame(5.0)
    assert ov.size[1] > sp + TIGHT_H                  # the menu needs room


def test_click_through_desktops_keep_the_roomy_window():
    w, _, _ = overlay_window(snap(action="idle"), FakeDesktop(work=WORK))
    ov = w.overlay
    assert ov.size[0] >= 300


def test_leave_and_enter_reset_the_world():
    w, desk, _, t = world([WIN])
    ov = w.overlay
    ov.walker.goal = ov.surfaces[0]
    tick(w, t, 40)
    w.set_mode("terrarium")
    assert w.set_mode("overlay")
    assert ov.feet == WORK[1] + WORK[3] and ov.surfaces == []
