import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = Path(__file__).resolve().parents[1] / ".pytest_tmp"


# Long-running work first. With pytest-xdist the wall time of the suite is bounded below by the longest
# single unit (a test, or an xdist_group that must stay on one worker); if that unit starts last it
# runs alone while the other workers idle. Longest first, then the other slow tests, then the rest
# (stable sort: the order inside each band is the collection order).
_LONGEST_FIRST = ("rebirth-attentive", "rebirth-neglect", "m2-individuation", "test_200_days_under_8_min", "m2-stable")


def _priority(item) -> int:
    group = item.get_closest_marker("xdist_group")
    keys = ([group.args[0]] if group and group.args else []) + [item.name]
    for rank, name in enumerate(_LONGEST_FIRST):
        if name in keys:
            return rank
    return len(_LONGEST_FIRST) if item.get_closest_marker("slow") else len(_LONGEST_FIRST) + 1


def pytest_collection_modifyitems(config, items):
    items.sort(key=_priority)
