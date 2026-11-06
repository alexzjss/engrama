import json

from engrama.osapi import hyprland as h

MON = {"id": 0, "x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1.0, "reserved": [60, 10, 10, 10],
       "focused": True, "activeWorkspace": {"id": 2}, "specialWorkspace": {"id": 0}}


def client(at, size, ws=2, **kw):
    d = {"mapped": True, "hidden": False, "at": list(at) if at else at, "size": list(size) if size else size,
         "workspace": {"id": ws}, "floating": False, "monitor": 0, "class": "app", "title": "SECRET", "pid": 10,
         "focusHistoryID": 1}
    d.update(kw)
    return d


def test_work_area_subtracts_reserved_and_scale():
    assert h.parse_work_area([MON]) == (60, 10, 1850, 1060)
    half = dict(MON, scale=2.0, width=3840, height=2160, reserved=[0, 0, 0, 0])
    assert h.parse_work_area([half]) == (0, 0, 1920, 1080)
    assert h.parse_work_area([]) is None
    assert h.parse_work_area([dict(MON, width="x")]) is None


def test_windows_keep_only_visible_current_workspace_and_geometry():
    cl = [client((100, 100), (800, 600)),
          client((10, 10), (500, 400), ws=3),                     # other workspace
          client((10, 10), (500, 400), hidden=True),
          client((10, 10), (500, 400), mapped=False),
          client((10, 10), (500, 400), pid=99),                   # ours
          client((10, 10), (500, 400), **{"class": "Engrama-Overlay"}),
          client((10, 10), (5, 5)),                                # tiny
          client((300, 50), (200, 200), floating=True, focusHistoryID=0)]
    out = h.parse_windows(cl, [MON], own_pid=99, own_class="engrama-overlay")
    assert out == [(300, 50, 200, 200), (100, 100, 800, 600)]      # floating first; rectangles only
    assert all(isinstance(r, tuple) and len(r) == 4 for r in out)


def test_windows_include_shown_special_workspace_and_bad_rows_are_skipped():
    mon = dict(MON, specialWorkspace={"id": -98})
    cl = [client((1, 1), (400, 300), ws=-98), {"at": "x"}, client((5, 5), None)]
    assert h.parse_windows(cl, [mon]) == [(1, 1, 400, 300)]
    assert h.parse_windows(cl, []) == []


class FakeSock:
    """One connection per request: each request consumes the next reply."""

    def __init__(self, replies):
        self.replies, self.sent = list(replies), []

    def __call__(self, path):
        outer = self
        reply = outer.replies.pop(0) if outer.replies else b""
        state = {"left": [reply]}

        class S:
            def settimeout(self, t):
                pass

            def sendall(self, b):
                outer.sent.append(b.decode())

            def recv(self, n):
                return state["left"].pop(0) if state["left"] else b""

            def close(self):
                pass
        return S()


ENV = {"HYPRLAND_INSTANCE_SIGNATURE": "sig"}


def test_windows_and_cursor_over_ipc():
    conn = FakeSock([json.dumps([MON]).encode(), json.dumps([client((1, 1), (400, 300))]).encode()])
    assert h.windows(ENV, conn) == [(1, 1, 400, 300)]
    assert h.cursor_pos(ENV, FakeSock([b'{"x": 5, "y": 7}'])) == (5, 7)
    assert h.cursor_pos(ENV, FakeSock([b"garbage"])) is None
    assert h.windows(ENV, FakeSock([b""])) == []


def test_rules_fall_back_to_legacy_syntax():
    conn = FakeSock([b"ok"])
    assert h.apply_overlay_rules("engrama-overlay", ENV, conn) is True
    assert conn.sent[0].startswith("eval hl.window_rule") and "engrama-overlay" in conn.sent[0]
    legacy = FakeSock([b"error: no eval"] + [b"ok"] * 8)
    assert h.apply_overlay_rules("engrama-overlay", ENV, legacy) is True
    assert any(s.startswith("keyword windowrulev2 noinitialfocus") for s in legacy.sent)
    assert h.apply_overlay_rules("bad class;rm", ENV, FakeSock([])) is False


def test_move_window_tries_lua_then_legacy():
    lua = FakeSock([b"ok"])
    assert h.move_window("engrama-overlay", 10, 20, ENV, lua)
    assert "hl.dsp.window.move" in lua.sent[0] and "x = 10" in lua.sent[0]
    old = FakeSock([b"error: x", b"ok"])
    assert h.move_window("engrama-overlay", 10, 20, ENV, old)
    assert old.sent[1] == "dispatch movewindowpixel exact 10 20,class:engrama-overlay"
    assert not h.move_window("", 1, 1, ENV, FakeSock([]))
