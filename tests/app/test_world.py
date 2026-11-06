import random

from engrama.app.ui.world import (Surface, Walker, edge_surfaces_for, flee_target, temper_of, visible_edges)

AREA = (0, 0, 1920, 1040)
STRIP = Surface(40, 1880, 1040, "strip")


def tops(windows, headroom=100, min_len=90):
    return [(round(s.x0), round(s.x1), s.y) for s in visible_edges(windows, AREA, headroom, min_len)]


def test_single_window_edge_is_inset():
    assert tops([(200, 400, 800, 500)]) == [(204, 996, 400)]


def test_edges_without_headroom_or_outside_are_dropped():
    assert tops([(0, 40, 1920, 1000)]) == []            # maximised: the body would be off screen
    assert tops([(200, 1035, 800, 500)]) == []          # at the floor already
    assert tops([(200, 400, 40, 500)]) == []            # too short to stand on


def test_occlusion_splits_and_removes_segments():
    front = (500, 300, 200, 600)       # topmost, its y range covers row 400
    back = (200, 400, 800, 500)
    assert tops([front, back]) == [(504, 696, 300), (204, 496, 400), (704, 996, 400)]


def test_window_below_the_edge_row_does_not_occlude():
    front = (500, 600, 200, 300)       # starts under the back window's edge row
    back = (200, 400, 800, 500)
    assert tops([front, back])[-1] == (204, 996, 400)


def test_fully_covered_edge_disappears():
    assert tops([(100, 300, 1000, 600), (200, 400, 400, 500)]) == [(104, 1096, 300)]


def test_edge_surfaces_for_uses_sprite_height():
    assert edge_surfaces_for([(200, 80, 800, 500)], AREA, 96) == []            # 80 < headroom 96
    assert len(edge_surfaces_for([(200, 200, 800, 500)], AREA, 96)) == 1


def test_temper():
    assert temper_of("arisco", {}) == "skittish"
    assert temper_of("", {"independencia": 80, "sociabilidade": 10}) == "skittish"
    assert temper_of("brincalhao", {}) == "playful"
    assert temper_of("curioso", {}) == "curious"
    assert temper_of("", {"curiosidade": 90}) == "curious"
    assert temper_of("base", {}) == "calm"


def test_flee_target_goes_away_from_cursor():
    s = Surface(100, 500, 400)
    assert flee_target(300, 250, s) == 500 and flee_target(300, 350, s) == 100


def settle(w, surfaces, secs=3.0, dt=0.05, target=None, speed=40):
    for _ in range(int(secs / dt)):
        w.update(dt, surfaces, target, speed)


def test_walks_on_the_strip_and_stops_at_target():
    w = Walker()
    w.place(500, 1040)
    settle(w, [STRIP], 1.0, target=700)
    assert 530 < w.x < 550 and w.y == 1040
    settle(w, [STRIP], 10.0, target=700)
    assert w.x == 700


def test_falls_when_the_ledge_disappears_and_lands_on_the_strip():
    ledge = Surface(200, 600, 500, "edge")
    w = Walker()
    w.place(400, 500)
    w.update(0.05, [STRIP, ledge], None, 0)
    assert w.state == "walk" and w.y == 500
    settle(w, [STRIP], 2.0)
    assert w.state == "walk" and w.y == 1040 and w.x == 400


def test_falls_through_gaps_but_lands_on_a_lower_ledge():
    top, low = Surface(200, 600, 300, "edge"), Surface(300, 500, 700, "edge")
    w = Walker()
    w.place(400, 300)
    settle(w, [STRIP, low], 2.0)
    assert w.y == 700
    settle(w, [STRIP], 2.0)
    assert w.y == 1040
    assert top.y == 300


def test_hops_up_to_a_window_edge_and_sits_there():
    ledge = Surface(600, 1000, 600, "edge")
    w = Walker(random.Random(1))
    w.place(300, 1040)
    w.goal = ledge
    states = set()
    for _ in range(400):
        w.update(0.05, [STRIP, ledge], None, 120)
        states.add(w.state)
    assert "jump" in states and w.state == "walk" and w.y == 600 and ledge.x0 <= w.x <= ledge.x1
    assert w.goal is None


def test_walks_off_an_edge_to_reach_a_lower_goal():
    ledge = Surface(600, 1000, 600, "edge")
    w = Walker()
    w.place(900, 600)
    w.goal = STRIP
    for _ in range(400):
        w.update(0.05, [STRIP, ledge], None, 150)
    assert w.y == 1040 and w.goal is None


def test_unreachable_goal_is_dropped():
    far = Surface(300, 500, 20, "edge")      # 1020 px up: beyond any hop
    w = Walker()
    w.place(200, 1040)
    w.goal = far
    w.update(0.05, [STRIP, far], None, 40)
    assert w.goal is None


def test_choose_goal_prefers_the_active_window_sometimes_and_needs_company():
    w = Walker(random.Random(3))
    w.place(300, 1040)
    assert w.choose_goal([STRIP]) is None
    ledge = Surface(600, 1000, 600, "edge")
    picks = {w.choose_goal([STRIP, ledge], prefer=ledge) for _ in range(5)}
    assert picks == {ledge}


def test_jump_to_a_vanished_ledge_ends_in_a_fall():
    ledge = Surface(600, 1000, 600, "edge")
    w = Walker()
    w.place(700, 1040)
    w.goal = ledge
    w.update(0.05, [STRIP, ledge], None, 0)
    assert w.state == "jump"
    for _ in range(40):
        w.update(0.05, [STRIP], None, 0)
    assert w.state == "walk" and w.y == 1040
