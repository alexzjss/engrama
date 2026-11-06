from engrama.osapi.x11 import filter_x11_windows

N = "_NET_WM_WINDOW_TYPE_NORMAL"


def e(rect, **kw):
    d = {"rect": rect, "desktop": 0, "states": [], "types": [N], "pid": 5}
    d.update(kw)
    return d


def test_filter_keeps_visible_normal_windows_in_order():
    ents = [e((0, 0, 500, 400)), e((10, 10, 300, 300), desktop=0xFFFFFFFF), e((1, 1, 300, 300), desktop=2),
            e((1, 1, 300, 300), states=["_NET_WM_STATE_HIDDEN"]),
            e((1, 1, 300, 300), states=["_NET_WM_STATE_SKIP_TASKBAR"]),
            e((0, 0, 1920, 30), types=["_NET_WM_WINDOW_TYPE_DOCK"]),
            e((1, 1, 300, 300), pid=77), e((1, 1, 10, 10)), e(None), {"nope": 1}]
    assert filter_x11_windows(ents, 0, own_pid=77) == [(0, 0, 500, 400), (10, 10, 300, 300)]


def test_untyped_windows_are_kept():
    assert filter_x11_windows([e((0, 0, 100, 100), types=[])], None) == [(0, 0, 100, 100)]
