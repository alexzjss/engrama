import numpy as np
from engrama import balance as B
from engrama.mind.contracts import Blackboard
from engrama.modules.drives.needs import NeedDrives
from engrama.vocab import NEED_KEYS


def run(needs):
    bb = Blackboard(); bb.write("body.needs", needs)
    NeedDrives({}, np.random.default_rng(0)).step(bb, 1.0)
    return bb.read("drives")


def test_drives_monotonic_and_midpoint():
    mid = np.array([B.DRIVE_MIDPOINTS[k] for k in NEED_KEYS])
    assert np.allclose(run(mid), 0.5)
    lo, hi = run(mid - 0.1), run(mid + 0.1)
    assert np.all(lo < 0.5) and np.all(hi > 0.5)
