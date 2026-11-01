import numpy as np
from engrama.mind.contracts import Blackboard
from engrama.mind.helpers import read_traits, default_traits
from engrama.vocab import TRAIT_KEYS


def test_read_traits_fallback_and_value():
    bb = Blackboard()
    assert read_traits(bb) == default_traits()
    assert default_traits()["paciencia"] == 0.7
    bb.write("traits", np.linspace(0, 1, len(TRAIT_KEYS)))
    tr = read_traits(bb)
    assert tr[TRAIT_KEYS[0]] == 0.0 and tr[TRAIT_KEYS[-1]] == 1.0
