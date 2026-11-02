import re

from engrama.services.memory.opinions import innate_lean, stance_word
from engrama.services.memory.store import MemoryStore

CLOCK_T = 1_800_000_000.0


def make(tmp_path):
    return MemoryStore(tmp_path / "memory.sqlite", now_fn=lambda: CLOCK_T)


def test_lean_is_deterministic_and_frozen(tmp_path):
    assert innate_lean(7, "jogo") == innate_lean(7, "jogo")
    store = make(tmp_path)
    store.update_opinion("jogo", lambda t: innate_lean(7, t, {"curiosidade": 90}), 0.0)
    before = store.opinion("jogo")["lean"]
    assert before == innate_lean(7, "jogo", {"curiosidade": 90})
    store.update_opinion("jogo", lambda t: innate_lean(7, t, {"curiosidade": 10}), 0.0)
    assert store.opinion("jogo")["lean"] == before


def test_different_seeds_can_disagree():
    leans = [innate_lean(s, "jogo") for s in range(50)]
    assert any(v > 0.3 for v in leans)
    assert any(v < -0.3 for v in leans)


def test_does_not_converge_to_user(tmp_path):
    store = make(tmp_path)
    store.bump_topic("jogo", 1.0)  # strong user affinity must not enter the stance
    for _ in range(100):
        store.update_opinion("jogo", lambda t: -0.9, 0.2)
    assert store.opinion("jogo")["stance"] < 0


def test_stance_word_has_no_digits():
    for lang in ("pt", "en"):
        for s in (-1.0, -0.6, -0.3, 0.0, 0.3, 0.7, 1.0):
            assert not re.search(r"\d", stance_word(s, lang))
