from engrama.kernel.actions import ACTION_SPECS, available
from engrama.kernel.fallback import fallback_action
from engrama.vocab import ACTIONS


def test_one_spec_per_action():
    assert tuple(ACTION_SPECS) == ACTIONS


def test_available_rules():
    assert available("egg", False, False) == ("idle",)
    assert available("egg", False, True) == ("idle",)
    assert available("baby", False, True) == ("hide",)
    assert available("baby", True, False) == ("sleep",)
    baby = available("baby", False, False)
    assert "hide" not in baby and "idle" in baby and "show_something" not in baby
    assert "show_something" in available("child", False, False)


def test_fallback_priorities():
    full = available("child", False, False)
    assert fallback_action({"sono": 85, "tedio": 90}, full) == "sleep"
    assert fallback_action({"sono": 10, "tedio": 70}, full) == "play_alone"
    assert fallback_action({"sono": 10, "tedio": 10}, full) == "idle"
    assert fallback_action({"sono": 99}, ("hide",)) == "hide"
    assert fallback_action({"sono": 99}, ("idle",)) == "idle"
